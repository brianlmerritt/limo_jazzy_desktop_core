#!/usr/bin/env python3
"""Validate real ROS messages; --motion additionally drives the simulated robot."""
import argparse
import json
import math
from pathlib import Path
import time
import numpy as np
import rclpy
from rclpy.qos import qos_profile_sensor_data
from rclpy.time import Time
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import Image, CameraInfo, LaserScan, PointCloud2, JointState
from sensor_msgs_py import point_cloud2
from tf2_ros import Buffer, TransformListener

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--namespace', default='limo')
parser.add_argument('--output', type=Path, default=Path('/sim-output/ros-check.json'))
parser.add_argument('--motion', action='store_true')
args = parser.parse_args()
rclpy.init()
node = rclpy.create_node('limo_sim_check')
messages, counts, stamps = {}, {}, {}
subscriptions = []


def remember(key, msg):
    messages[key] = msg
    counts[key] = counts.get(key, 0) + 1
    if hasattr(msg, 'header'):
        stamp = msg.header.stamp
        stamps.setdefault(key, []).append(stamp.sec + stamp.nanosec * 1e-9)


def spin_for(seconds, command=None):
    end = time.monotonic() + seconds
    next_pub = 0.0
    while time.monotonic() < end:
        if command is not None and time.monotonic() >= next_pub:
            publisher.publish(command)
            next_pub = time.monotonic() + 0.05
        rclpy.spin_once(node, timeout_sec=0.005)


for name, kind, topic in [
    ('scan', LaserScan, 'scan'), ('cloud', PointCloud2, 'point_cloud'),
    ('rgb', Image, 'camera/front/color/image_raw'), ('depth', Image, 'camera/front/depth/image_raw'),
    ('info', CameraInfo, 'camera/front/color/camera_info'), ('odom', Odometry, 'odom'),
    ('joints', JointState, 'joint_states'), ('clock', Clock, '/clock')]:
    path = topic if topic.startswith('/') else f'/{args.namespace}/{topic}'
    subscriptions.append(node.create_subscription(kind, path, lambda msg, key=name: remember(key, msg), qos_profile_sensor_data))
publisher = node.create_publisher(Twist, f'/{args.namespace}/cmd_vel', 1)
buffer = Buffer()
listener = TransformListener(buffer, node)
report = {'namespace': args.namespace, 'motion_requested': args.motion}
try:
    deadline = time.monotonic() + 45
    while len(messages) < 8 and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.05)
    missing = sorted(set(['scan', 'cloud', 'rgb', 'depth', 'info', 'odom', 'joints', 'clock']) - messages.keys())
    assert not missing, f'Missing ROS topics: {missing}'
    spin_for(3)
    scan = messages['scan']
    ranges = np.asarray(scan.ranges)
    finite = ranges[np.isfinite(ranges) & (ranges > scan.range_min)]
    assert len(ranges) >= 180 and len(finite) > 100, 'Sparse or empty lidar scan'
    assert 0.1 < float(np.median(finite)) < 8.0, 'Lidar does not see room geometry'
    rgb, depth, info = (messages[k] for k in ('rgb', 'depth', 'info'))
    assert rgb.encoding == 'rgb8' and depth.encoding == '32FC1'
    assert (rgb.width, rgb.height) == (info.width, info.height) == (depth.width, depth.height)
    color = np.frombuffer(bytes(rgb.data), dtype=np.uint8).reshape(rgb.height, rgb.step)[:, :rgb.width*3]
    depth_values = np.frombuffer(bytes(depth.data), dtype='<f4').reshape(depth.height, depth.step//4)[:, :depth.width]
    assert color.std() > 5 and color.max() > 50, 'Camera appears blank'
    assert np.count_nonzero(np.isfinite(depth_values) & (depth_values > 0)) > depth_values.size * 0.1
    assert info.k[0] > 0 and info.k[4] > 0 and len(messages['joints'].name) == 4
    tf_frames = [f'{args.namespace}/{name}' for name in ('base_link', 'laser', 'camera_optical_frame')]
    for frame in tf_frames:
        assert buffer.can_transform(f'{args.namespace}/odom', frame, Time()), f'Missing TF to {frame}'
    clock = messages['clock'].clock
    clock_s = clock.sec + clock.nanosec * 1e-9
    for key in ('scan', 'rgb', 'depth', 'odom'):
        assert len(set(stamps[key])) >= 2, f'{key} timestamps are not advancing'
        assert abs(clock_s - stamps[key][-1]) < 2, f'{key} is not stamped with simulation time'
    assert 100 < messages['cloud'].width * messages['cloud'].height <= 800, 'Expected a single planar scan'
    cloud_xyz = point_cloud2.read_points_numpy(messages['cloud'], field_names=('x', 'y', 'z'), skip_nans=True)
    assert float(np.max(np.abs(cloud_xyz[:, 2]))) < 0.015, 'Lidar points are not in the horizontal sensor plane'
    # Validate scan direction against asymmetric blue/left and orange/right boxes.
    # This catches reversed X axes and mirrored azimuths, not just a connected TF.
    pose_msg = messages['odom'].pose.pose
    q = pose_msg.orientation
    yaw = math.atan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))
    origin = np.array([pose_msg.position.x + 0.103*math.cos(yaw),
                       pose_msg.position.y + 0.103*math.sin(yaw)])
    angles = scan.angle_min + np.arange(len(ranges))*scan.angle_increment
    directions = np.stack((np.cos(angles+yaw), np.sin(angles+yaw)), axis=1)
    expected = np.full(len(ranges), np.inf)
    # Axis-aligned box extents in the default collision room.
    obstacles = [(3.95, 4.05, -3, 3), (-4.05, -3.95, -3, 3),
                 (-4, 4, 2.95, 3.05), (-4, 4, -3.05, -2.95),
                 (1.7, 2.3, 0.4, 1.0), (2.55, 3.05, -1.2, -0.6),
                 (-2.1, -1.5, 1.4, 2.0)]
    for xmin, xmax, ymin, ymax in obstacles:
        with np.errstate(divide='ignore', invalid='ignore'):
            t0 = (np.array([xmin, ymin])-origin)/directions
            t1 = (np.array([xmax, ymax])-origin)/directions
        entering = np.minimum(t0, t1).max(axis=1)
        leaving = np.maximum(t0, t1).min(axis=1)
        hits = (leaving >= entering) & (entering > 0)
        expected[hits] = np.minimum(expected[hits], entering[hits])
    usable = np.isfinite(ranges) & np.isfinite(expected) & (ranges > 0.2)
    scan_error = np.abs(ranges[usable]-expected[usable])
    assert len(scan_error) > 200 and np.quantile(scan_error, 0.9) < 0.16, 'Scan directions do not match room landmarks'
    rear = np.abs(angles) > math.radians(123)
    rear_far_fraction = float(np.mean(np.isfinite(ranges[rear]) & (ranges[rear] > 0.2)))
    assert rear_far_fraction < 0.05, 'Rear lidar sector can still see through the robot obstruction'
    report['frame_validation'] = {'scan_p90_error_m': float(np.quantile(scan_error, 0.9)),
                                  'rear_far_return_fraction': rear_far_fraction}
    report.update({'scan_samples': len(ranges), 'finite_scan_samples': len(finite),
                   'scan_median_m': float(np.median(finite)), 'scan_frame': scan.header.frame_id,
                   'camera_resolution': [rgb.width, rgb.height], 'rgb_std': float(color.std()),
                   'depth_median_m': float(np.nanmedian(np.where(np.isfinite(depth_values), depth_values, np.nan))),
                   'point_cloud_points': messages['cloud'].width * messages['cloud'].height,
                   'tf_frames': tf_frames, 'message_counts': counts})
    if args.motion:
        def pose():
            p = messages['odom'].pose.pose
            q = p.orientation
            return np.array([p.position.x, p.position.y]), math.atan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))
        spin_for(1)
        initial, heading = pose()
        cmd = Twist(); cmd.linear.x = 0.2
        spin_for(2, cmd)
        spin_for(1)  # No explicit stop: exercise the simulator's command watchdog.
        after, _ = pose()
        distance = float(np.linalg.norm(after - initial))
        assert 0.20 < distance < 0.65, f'Unexpected commanded travel: {distance:.3f}m'
        projected = float((after-initial) @ np.array([math.cos(heading), math.sin(heading)]))
        assert projected > 0.15, 'Forward command moved in the wrong direction'
        spin_for(1)
        stopped, yaw_before = pose()
        drift = float(np.linalg.norm(stopped - after))
        assert drift < 0.035, f'Watchdog did not stop robot: {drift:.3f}m drift'
        cmd = Twist(); cmd.angular.z = 0.6
        spin_for(2, cmd)
        spin_for(1)
        _, yaw_after = pose()
        turn = math.atan2(math.sin(yaw_after-yaw_before), math.cos(yaw_after-yaw_before))
        assert 0.12 < turn < 1.8, f'Turning failed or has wrong sign: {turn:.3f}rad'
        report['motion'] = {'forward_distance_m': distance, 'watchdog_drift_m': drift, 'turn_radians': turn}
    report['passed'] = True
except Exception as error:
    report['passed'] = False
    report['error'] = str(error)
    raise
finally:
    if args.motion:
        publisher.publish(Twist())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    node.destroy_node()
    rclpy.shutdown()
