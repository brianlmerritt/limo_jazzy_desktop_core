"""Require a recently processed camera frame, not only a live node."""
import json
import os
import time
import rclpy
from std_msgs.msg import String
rclpy.init()
node = rclpy.create_node('vision_preflight')
received = []
node.create_subscription(String, '/' + os.environ['LIMO_ROS_NAMESPACE'] + '/vision/people',
                         lambda msg: received.append(json.loads(msg.data)), 10)
deadline = time.monotonic()+60
while time.monotonic() < deadline:
    rclpy.spin_once(node, timeout_sec=.2)
    if received and 0 <= node.get_clock().now().nanoseconds/1e9-received[-1]['stamp'] < 1:
        print('PASS: fresh ROS camera inference from ' + received[-1]['model'])
        node.destroy_node()
        rclpy.shutdown()
        raise SystemExit(0)
node.destroy_node()
rclpy.shutdown()
raise SystemExit('No fresh vision results within 60 seconds; inspect docker compose logs vision')
