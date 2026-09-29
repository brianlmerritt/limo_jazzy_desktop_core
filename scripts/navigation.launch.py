"""Framework overlay: configure upstream nodes through their native ROS contract."""
import os
import json
import sys
import math
from pathlib import Path
import re

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, ExecuteProcess, RegisterEventHandler, EmitEvent
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from nav2_common.launch import ReplaceString, RewrittenYaml


def launch_setup(context):
    namespace = os.environ.get('LIMO_ROS_NAMESPACE', '')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', namespace):
        raise ValueError('Navigation requires a nonempty LIMO_ROS_NAMESPACE')
    mode = LaunchConfiguration('mode').perform(context)
    if mode not in ('mapping', 'navigation', 'exploration'):
        raise ValueError('mode must be mapping, navigation, or exploration')
    config = Path(__file__).resolve().parent.parent / 'config' / 'robot'
    remaps = [('/tf', 'tf'), ('/tf_static', 'tf_static')]
    if mode == 'exploration':
        # This node starts sending goals immediately. Only an explicit command launches it.
        return [Node(package='explore_lite', executable='explore', name='explore_node',
                     namespace=namespace, parameters=[str(config / 'explore.yaml')],
                     remappings=remaps, output='screen')]
    if mode == 'mapping':
        return [Node(package='slam_toolbox', executable='async_slam_toolbox_node',
                     name='slam_toolbox', namespace=namespace,
                     parameters=[str(config / 'slam.yaml')],
                     remappings=remaps + [('/map', 'map'), ('/map_metadata', 'map_metadata')],
                     output='screen'),
                Node(package='nav2_lifecycle_manager', executable='lifecycle_manager',
                     name='lifecycle_manager_slam', namespace=namespace,
                     parameters=[{'autostart': True, 'node_names': ['slam_toolbox']}],
                     output='screen')]
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from navigation_footprint import footprint_replacements
    footprint = json.loads((config / 'navigation-footprint.json').read_text())
    replacements = footprint_replacements(footprint)
    params = RewrittenYaml(
        source_file=ReplaceString(source_file=str(config / 'navigation.yaml'),
                                  replacements={'<robot_namespace>': namespace, **replacements}),
        root_key=namespace, param_rewrites={}, convert_types=True)
    servers = [
        ('nav2_controller', 'controller_server'),
        ('nav2_smoother', 'smoother_server'),
        ('nav2_planner', 'planner_server'),
        ('nav2_behaviors', 'behavior_server'),
        ('nav2_bt_navigator', 'bt_navigator'),
        ('nav2_velocity_smoother', 'velocity_smoother'),
        ('nav2_collision_monitor', 'collision_monitor'),
    ]
    check = LaunchConfiguration('check_lidar_orientation').perform(context)
    if check not in ('true', 'false'):
        raise ValueError('check_lidar_orientation must be true or false')
    geometry = json.loads((config / 'geometry.json').read_text())['laser']
    if geometry['parent'] != 'base_link' or geometry['child'] != 'laser_frame':
        raise ValueError('Unexpected laser frames')
    for field in ('xyz', 'rpy'):
        if len(geometry[field]) != 3 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in geometry[field]):
            raise ValueError('Invalid laser geometry')
    policy = json.loads((config / 'alignment-policy.json').read_text())
    # Validate at the framework boundary as well as in the native consumer.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from navigation_guard_core import validate_policy
    validate_policy(policy)
    guard = ExecuteProcess(cmd=[sys.executable, str(Path(__file__).with_name('navigation-guard.py')),
        '--ros-args', '-r', '__ns:=/' + namespace, '-r', '/tf:=tf', '-r', '/tf_static:=tf_static',
        '-p', 'check_lidar_orientation:=' + check,
        '-p', 'alignment_policy_json:=' + json.dumps(json.dumps(policy)),
        '-p', 'expected_laser_xyz:=' + json.dumps(geometry['xyz']),
        '-p', 'expected_laser_rpy:=' + json.dumps(geometry['rpy'])], output='screen')
    nodes = [guard, RegisterEventHandler(OnProcessExit(target_action=guard,
        on_exit=[EmitEvent(event=Shutdown(reason='Navigation guard exited'))]))]

    for package, executable in servers:
        routing = [('cmd_vel', 'cmd_vel_nav')] if executable in (
            'controller_server', 'behavior_server', 'velocity_smoother') else []
        nodes.append(Node(package=package, executable=executable, name=executable,
                          namespace=namespace, parameters=[params, {'use_sim_time': False}, *([{'default_nav_to_pose_bt_xml': str(config / 'navigate-forward.xml'), 'default_nav_through_poses_bt_xml': str(config / 'navigate-through-forward.xml')}] if executable == 'bt_navigator' else [])],
                          remappings=remaps + routing, output='screen'))
    nodes.append(Node(package='nav2_lifecycle_manager', executable='lifecycle_manager',
                      name='lifecycle_manager_navigation', namespace=namespace,
                      parameters=[{'autostart': True,
                                   'node_names': [name for _, name in servers]}],
                      output='screen'))
    return nodes


def generate_launch_description():
    return LaunchDescription([DeclareLaunchArgument('mode', default_value='mapping'),
                              DeclareLaunchArgument('check_lidar_orientation', default_value='true'),
                              OpaqueFunction(function=launch_setup)])
