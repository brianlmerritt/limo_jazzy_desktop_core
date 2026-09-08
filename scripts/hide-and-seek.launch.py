"""First-game framework overlay; explore_lite alone owns navigation goals."""
import os
import re
from pathlib import Path
from launch import LaunchDescription
from launch.actions import RegisterEventHandler, EmitEvent
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch_ros.actions import Node


def generate_launch_description():
    namespace = os.environ.get('LIMO_ROS_NAMESPACE', '')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', namespace):
        raise ValueError('Nonempty robot namespace required')
    config = Path(__file__).resolve().parent.parent / 'config/robot/explore.yaml'
    game = Node(package='limo_hide_and_seek', executable='coordinator', namespace=namespace,
                parameters=[{'autostart': True}], output='screen')
    explorer = Node(package='explore_lite', executable='explore', name='explore_node',
                    namespace=namespace, parameters=[str(config)],
                    remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')], output='screen')
    actions = []
    for node in (game, explorer):
        actions.extend([node, RegisterEventHandler(OnProcessExit(target_action=node,
                        on_exit=[EmitEvent(event=Shutdown(reason='Game component exited'))]))])
    return LaunchDescription(actions)
