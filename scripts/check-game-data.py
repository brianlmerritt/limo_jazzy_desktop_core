"""Passive startup check for the game coordinator."""
import json
import os
import time
import rclpy
from std_msgs.msg import String
rclpy.init()
node = rclpy.create_node('game_preflight')
messages = []
node.create_subscription(String, '/' + os.environ['LIMO_ROS_NAMESPACE'] + '/hide_and_seek/status',
                         lambda m: messages.append(json.loads(m.data)), 10)
deadline = time.monotonic()+15
while time.monotonic() < deadline:
    rclpy.spin_once(node, timeout_sec=.2)
    if messages and messages[-1].get('vision_fresh'):
        print('PASS: game coordinator has fresh vision; state=' + messages[-1]['state'])
        node.destroy_node()
        rclpy.shutdown()
        raise SystemExit(0)
node.destroy_node()
rclpy.shutdown()
raise SystemExit('Game coordinator did not report fresh vision')
