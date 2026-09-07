"""Read-only preflight for the live namespaced navigation graph."""
import os
import time
import math
import rclpy
from rclpy.qos import qos_profile_sensor_data, QoSProfile, DurabilityPolicy
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import OccupancyGrid, Odometry
from limo_msgs.msg import LimoStatus
from tf2_ros import Buffer, TransformListener

rclpy.init(args=['--ros-args', '-r', '__ns:=/' + os.environ['LIMO_ROS_NAMESPACE'],
                '-r', '/tf:=tf', '-r', '/tf_static:=tf_static'])
node = rclpy.create_node('navigation_preflight')
data = {}
def receive(key, message):
    data[key] = (time.monotonic(), message)
for topic, kind, qos in [
    ('scan', LaserScan, qos_profile_sensor_data),
    ('wheel/odom', Odometry, 10), ('limo_status', LimoStatus, 10),
    ('map', OccupancyGrid, QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))]:
    node.create_subscription(kind, topic, lambda msg, key=topic: receive(key, msg), qos)
buffer = Buffer()
listener = TransformListener(buffer, node)
try:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=.1)
        if len(data) == 4 and buffer.can_transform('map', 'laser_frame', rclpy.time.Time()):
            break
    now = time.monotonic()
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
    prefix = '/' + os.environ['LIMO_ROS_NAMESPACE']
    publishers = node.get_publishers_info_by_topic(prefix + '/cmd_vel')
    subscribers = node.get_subscriptions_info_by_topic(prefix + '/cmd_vel')
    if len(publishers) != 1 or publishers[0].node_name != 'collision_monitor':
        raise RuntimeError('Final cmd_vel must have only the collision monitor publisher')
    if len(subscribers) != 1 or subscribers[0].node_name != 'limo_base_node':
        raise RuntimeError('Final cmd_vel must connect to the chassis')
    # Graph topic names are not rewritten by this node's /tf remappings.
    graph_topics = {name for name, _ in node.get_topic_names_and_types()}
    for topic in ('/cmd_vel', '/scan', '/map', '/tf', '/tf_static'):
        if topic in graph_topics:
            raise RuntimeError('Unexpected unnamespaced topic: ' + topic)
    print('PASS: live scan, odometry, map, chassis status, map-to-laser TF and isolated command routing')
finally:
    node.destroy_node()
    rclpy.shutdown()
