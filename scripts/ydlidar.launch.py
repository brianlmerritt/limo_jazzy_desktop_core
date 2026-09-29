"""Translate framework device selection to driver and scan-adapter interfaces."""
import os
from launch import LaunchDescription
from launch.actions import EmitEvent, RegisterEventHandler
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch_ros.actions import Node


def generate_launch_description():
    namespace = os.environ.get('LIMO_ROS_NAMESPACE', '')
    driver = Node(package='ydlidar_ros2_driver', executable='ydlidar_ros2_driver_node',
                  namespace=namespace, output='screen',
                  parameters=[os.environ['YDLIDAR_ROS_CONFIG'],
                              {'port': os.environ['YDLIDAR_CONTAINER_PATH'],
                               'baudrate': int(os.environ['YDLIDAR_BAUD'])}],
                  remappings=[('scan', 'scan_raw'), ('/scan', 'scan_raw'), ('/point_cloud', 'point_cloud')])
    adapter = Node(package='limo_scan_adapter', executable='scan_sanitizer',
                   namespace=namespace, output='screen')
    nodes = [driver, adapter]
    return LaunchDescription(nodes + [RegisterEventHandler(OnProcessExit(
        target_action=node, on_exit=[EmitEvent(event=Shutdown(reason='LiDAR pipeline exited'))]))
        for node in nodes])
