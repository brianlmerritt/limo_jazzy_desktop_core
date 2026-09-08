"""Run explicitly in the ROS container; isolated DDS domain, fake Nav2 only."""
import os
import sys
import json
import signal
import subprocess
import tempfile
import time

# Never share discovery with the hardware graph.
os.environ['ROS_DOMAIN_ID'] = '174'
game_mode = '--game' in sys.argv
os.environ['LIMO_ROS_NAMESPACE'] = 'exploration_validation'
import rclpy
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import OccupancyGrid
from nav2_msgs.action import NavigateToPose
from std_msgs.msg import String
from rclpy.action import ActionServer
from rclpy.qos import QoSProfile, DurabilityPolicy
from tf2_ros import StaticTransformBroadcaster

rclpy.init(args=['--ros-args', '-r', '__ns:=/exploration_validation',
                '-r', '/tf:=tf', '-r', '/tf_static:=tf_static'])
node = rclpy.create_node('fake_navigation')
goals = []
game_status = []
people_pub = node.create_publisher(String, "vision/people", 10)
node.create_subscription(String, "hide_and_seek/status", lambda m: game_status.append(json.loads(m.data)), 10)
def execute(handle):
    goals.append(handle.request.pose)
    handle.succeed()
    return NavigateToPose.Result()
server = ActionServer(node, NavigateToPose, 'navigate_to_pose', execute)
pub = node.create_publisher(OccupancyGrid, 'map',
                           QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))
broadcaster = StaticTransformBroadcaster(node)
tf = TransformStamped()
tf.header.frame_id = 'map'
tf.child_frame_id = 'base_link'
tf.transform.rotation.w = 1.0
broadcaster.sendTransform(tf)
msg = OccupancyGrid()
msg.header.frame_id = 'map'
msg.info.resolution = .1
msg.info.width = msg.info.height = 60
msg.info.origin.position.x = msg.info.origin.position.y = -3.
msg.info.origin.orientation.w = 1.
msg.data = [0 if 20 <= x < 40 and 20 <= y < 40 else -1
            for y in range(60) for x in range(60)]
with tempfile.TemporaryFile(mode='w+') as log:
    command = [
        'ros2', 'run', 'explore_lite', 'explore', '--ros-args',
        '-r', '__ns:=/exploration_validation', '-r', '/tf:=tf', '-r', '/tf_static:=tf_static',
        '--params-file', '/workspace/config/robot/explore.yaml']
    if game_mode:
        command = ['ros2', 'launch', '/workspace/scripts/hide-and-seek.launch.py']
    process = subprocess.Popen(command,
        stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        deadline = time.monotonic()+20
        while time.monotonic() < deadline and not (goals and (not game_mode or (game_status and game_status[-1]['vision_fresh']))):
            pub.publish(msg)
            people_pub.publish(String(data=json.dumps({'stamp': node.get_clock().now().nanoseconds/1e9, 'people': []})))
            rclpy.spin_once(node, timeout_sec=.1)
            if process.poll() is not None:
                break
        assert goals, 'explore_lite did not send a namespaced goal to fake Nav2'
        if game_mode:
            assert game_status and game_status[-1]['vision_fresh'], 'Game launch did not receive vision'
            print('PASS: full game launch with fake Nav2, synthetic map and fresh vision')
        assert goals[0].header.frame_id == 'map'
        assert not node.get_publishers_info_by_topic('/cmd_vel')
        print('PASS: pinned explore_lite consumed a synthetic map/private TF and sent a namespaced Nav2 goal; isolated domain 174, no hardware commands')
    finally:
        if process.poll() is None:
            # Launch forwards the signal to its children; signalling the whole
            # group as well interrupts their cleanup twice.
            if game_mode:
                process.send_signal(signal.SIGINT)
            else:
                os.killpg(process.pid, signal.SIGINT)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        log.seek(0)
        output = log.read()
        print(output)
        if game_mode:
            assert 'Traceback' not in output and 'process has died' not in output, 'Unclean game shutdown'
        server.destroy()
        node.destroy_node()
        rclpy.shutdown()
