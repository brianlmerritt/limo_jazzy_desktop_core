"""Read-only preflight for the live namespaced navigation graph."""
import os
import time
import math
import rclpy
from rclpy.qos import qos_profile_sensor_data, QoSProfile, DurabilityPolicy
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String
import json
from nav_msgs.msg import OccupancyGrid, Odometry
from limo_msgs.msg import LimoStatus
from tf2_ros import Buffer, TransformListener
from navigation_graph_check import routing_errors

rclpy.init(args=['--ros-args', '-r', '__ns:=/' + os.environ['LIMO_ROS_NAMESPACE'],
                '-r', '/tf:=tf', '-r', '/tf_static:=tf_static'])
node = rclpy.create_node('navigation_preflight')
data = {}
def receive(key, message):
    data[key] = (time.monotonic(), message)
for topic, kind, qos in [
    ('navigation_guard/status', String, QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)),
    ('scan', LaserScan, qos_profile_sensor_data),
    ('wheel/odom', Odometry, 10), ('limo_status', LimoStatus, 10),
    ('map', OccupancyGrid, QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))]:
    node.create_subscription(kind, topic, lambda msg, key=topic: receive(key, msg), qos)
buffer = Buffer()
listener = TransformListener(buffer, node)
try:
    prefix = "/" + os.environ["LIMO_ROS_NAMESPACE"]
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=.1)
        if len(data) == 5 and json.loads(data['navigation_guard/status'][1].data).get('ready') and buffer.can_transform('map', 'laser_frame', rclpy.time.Time()) and not routing_errors(node, prefix):
            break
    now = time.monotonic()
    status = data.get('navigation_guard/status')
    if not status or now-status[0] > 2 or not json.loads(status[1].data).get('ready'):
        raise RuntimeError('Navigation guard not ready: ' + (status[1].data if status else 'missing status'))
    errors = routing_errors(node, prefix)
    if errors:
        raise RuntimeError('Navigation routing not ready: ' + '; '.join(errors))

    for key in ('scan', 'wheel/odom', 'limo_status'):
        if key not in data or now-data[key][0] > 1:
            raise RuntimeError('Missing or stale ' + key)
    if 'map' not in data or not data['map'][1].data:
        raise RuntimeError('No map')
    scan = data['scan'][1]
    if not any(math.isfinite(r) and scan.range_min <= r <= scan.range_max for r in scan.ranges):
        raise RuntimeError('No valid scan returns')
    st = data['limo_status'][1]
    if (st.error_code, st.control_mode, st.motion_mode) != (0, 1, 0):
        raise RuntimeError('Chassis not ready for differential navigation')
    transform = buffer.lookup_transform('map', 'laser_frame', rclpy.time.Time())
    stamp = transform.header.stamp
    if (node.get_clock().now().nanoseconds-(stamp.sec*10**9+stamp.nanosec))/1e9 > 1:
        raise RuntimeError('Stale map-to-laser transform')
    print('PASS: live scan, odometry, map, chassis status, map-to-laser TF and isolated command routing')
finally:
    node.destroy_node()
    rclpy.shutdown()
