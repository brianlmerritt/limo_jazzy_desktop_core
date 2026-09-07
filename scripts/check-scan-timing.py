"""Passively measure scan delivery and TF availability; sends no commands."""
import argparse
import math
import os
import time

import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
from tf2_ros import Buffer, TransformListener

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--seconds', type=float, default=20.0)
args = parser.parse_args()
if not math.isfinite(args.seconds) or not 1 <= args.seconds <= 300:
    parser.error('--seconds must be between 1 and 300')
namespace = os.environ.get('LIMO_ROS_NAMESPACE', '').strip('/')
if not namespace:
    parser.error('Set LIMO_ROS_NAMESPACE to the robot namespace')
rclpy.init(args=['--ros-args', '-r', '__ns:=/' + namespace,
                '-r', '/tf:=tf', '-r', '/tf_static:=tf_static'])
node = rclpy.create_node('scan_timing_diagnostic')
buffer = Buffer()
listener = TransformListener(buffer, node)
rows = []
pending = []
warmup_end = time.monotonic() + 3.0


def receive(message):
    now = time.monotonic()
    if now < warmup_end:
        return
    stamp = rclpy.time.Time.from_msg(message.header.stamp)
    row = {'arrival': now, 'age': (node.get_clock().now() - stamp).nanoseconds / 1e9}
    for target in ('odom', 'map'):
        row[target] = 0.0 if buffer.can_transform(target, message.header.frame_id, stamp) else None
    rows.append(row)
    pending.append((row, stamp, message.header.frame_id))


node.create_subscription(LaserScan, 'scan', receive, qos_profile_sensor_data)
try:
    deadline = warmup_end + args.seconds
    while time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.01)
        for row, stamp, frame in pending[:]:
            elapsed = time.monotonic() - row['arrival']
            for target in ('odom', 'map'):
                if row[target] is None and buffer.can_transform(target, frame, stamp):
                    row[target] = elapsed
            if elapsed > 0.5 or all(row[t] is not None for t in ('odom', 'map')):
                pending.remove((row, stamp, frame))
    # Exclude the final half-second so every reported scan had its full TF window.
    complete = [r for r in rows if r['arrival'] < deadline - 0.5]
    if len(complete) < 2:
        raise RuntimeError('Insufficient scans received')
    gaps = [b['arrival'] - a['arrival'] for a, b in zip(complete, complete[1:])]
    print(f'Scans: {len(complete)}, rate: {1 / (sum(gaps) / len(gaps)):.2f} Hz, '
          f'max arrival gap: {max(gaps) * 1000:.1f} ms')
    print(f'Scan stamp age: {min(r["age"] for r in complete) * 1000:.1f}..'
          f'{max(r["age"] for r in complete) * 1000:.1f} ms (includes sensor acquisition)')
    for target in ('odom', 'map'):
        print(f'{target} <- laser at scan timestamp: '
              f'{sum(r[target] == 0 for r in complete)} immediate, '
              f'{sum(r[target] is not None and r[target] > 0 for r in complete)} delayed, '
              f'{sum(r[target] is None for r in complete)} unavailable within 0.5 s')
    print('This measures this subscriber; it is not a DDS packet-loss counter.')
finally:
    node.destroy_node()
    rclpy.shutdown()
