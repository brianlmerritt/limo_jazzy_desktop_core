"""Publish platform-owned, configured sensor extrinsics on private TF topics."""
import json
import math
import os
from pathlib import Path
import re
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    namespace = os.environ.get('LIMO_ROS_NAMESPACE', '')
    if namespace and not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', namespace):
        raise ValueError('Invalid LIMO_ROS_NAMESPACE')
    path = Path(__file__).resolve().parent.parent / 'config/robot/geometry.json'
    transforms = json.loads(path.read_text())
    nodes = []
    for name, transform in transforms.items():
        for field in ('parent', 'child'):
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', transform[field]):
                raise ValueError('Invalid frame ID')
        values = transform['xyz'] + transform['rpy']
        if len(transform['xyz']) != 3 or len(transform['rpy']) != 3 or not all(
                isinstance(v, (int, float)) and math.isfinite(v) for v in values):
            raise ValueError('Expected finite xyz/rpy triples')
        arguments = []
        for key, value in zip(('x', 'y', 'z', 'roll', 'pitch', 'yaw'), values):
            arguments.extend(['--' + key, str(value)])
        arguments += ['--frame-id', transform['parent'], '--child-frame-id', transform['child']]
        nodes.append(Node(package='tf2_ros', executable='static_transform_publisher',
                          name=name + '_extrinsics', namespace=namespace, arguments=arguments,
                          remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')]))
    return LaunchDescription(nodes)
