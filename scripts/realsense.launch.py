"""Translate framework camera configuration to native ROS node inputs."""
import os
from pathlib import Path
import re

import yaml
from launch import LaunchDescription
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    path = Path(os.environ['REALSENSE_ROS_CONFIG']).resolve()
    if not path.is_relative_to(Path('/workspace/config')):
        raise ValueError('Camera parameter file must be inside /workspace/config')
    with path.open() as stream:
        parameters = yaml.safe_load(stream)
    if not isinstance(parameters, dict):
        raise ValueError('Camera configuration must be a parameter mapping')
    name = parameters.pop('camera_name', 'front')
    namespace = parameters.pop('camera_namespace', 'camera')
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name):
        raise ValueError('Invalid camera_name')
    if not isinstance(namespace, str) or not re.fullmatch(r'/?[A-Za-z_][A-Za-z0-9_/]*', namespace):
        raise ValueError('Invalid camera_namespace')
    serial = os.environ['REALSENSE_SERIAL']
    if not re.fullmatch(r'[A-Za-z0-9_.:-]+', serial):
        raise ValueError('Invalid SDK serial')
    parameters['camera_name'] = name
    parameters['serial_no'] = ParameterValue(serial, value_type=str)
    return LaunchDescription([Node(
        package='realsense2_camera', executable='realsense2_camera_node',
        namespace=namespace, name=name, parameters=[parameters], output='screen',
    )])
