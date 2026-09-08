"""Synthetic game decisions, isolated domain 181; no navigation action client."""
import json
import os
import time
os.environ['ROS_DOMAIN_ID'] = '181'
import rclpy
from rclpy.executors import SingleThreadedExecutor
from std_msgs.msg import String, Bool
from limo_hide_and_seek.coordinator import Coordinator

rclpy.init()
game = Coordinator()
fixture = rclpy.create_node('game_fixture')
executor = SingleThreadedExecutor()
executor.add_node(game)
executor.add_node(fixture)
people = fixture.create_publisher(String, 'vision/people', 10)
enable = fixture.create_publisher(Bool, 'hide_and_seek/enable', 10)
commands = []
events = []
fixture.create_subscription(Bool, 'explore/resume', lambda m: commands.append(m.data), 10)
fixture.create_subscription(String, 'hide_and_seek/events', lambda m: events.append(json.loads(m.data)), 10)

def pump(duration, confidence=None):
    end = time.monotonic()+duration
    while time.monotonic() < end:
        if confidence is not None:
            people.publish(String(data=json.dumps({'stamp': fixture.get_clock().now().nanoseconds/1e9,
                                                    'people': [] if confidence == 0 else [{'confidence': confidence}]})))
        executor.spin_once(timeout_sec=.03)
        time.sleep(.03)

pump(1)
assert commands and commands[-1] is False
assert game.state == 'idle'
enable.publish(Bool(data=True))
pump(1, 0)
assert commands[-1] is True
pump(1.7)
assert commands[-1] is False
pump(1, 0)
assert commands[-1] is True
pump(1, .9)
assert commands[-1] is False and game.state == 'found'
assert any(e['event'] == 'person_found' for e in events)
pump(.5, 0)
assert game.state == 'found'
print('PASS: idle, fresh-data search, stale pause, fresh resume, confirmed find and persistent pause')
executor.shutdown()
game.destroy_node()
fixture.destroy_node()
rclpy.shutdown()
