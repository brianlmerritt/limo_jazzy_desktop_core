"""Run explicitly in the ROS container; isolated DDS domain, fake Nav2 only."""
import os
import signal
import subprocess
import tempfile
import time

# Never share discovery with the hardware graph.
os.environ['ROS_DOMAIN_ID'] = '174'
import rclpy
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import OccupancyGrid
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionServer
from rclpy.qos import QoSProfile, DurabilityPolicy
from tf2_ros import StaticTransformBroadcaster

rclpy.init(args=['--ros-args', '-r', '__ns:=/exploration_validation',
                '-r', '/tf:=tf', '-r', '/tf_static:=tf_static'])
node = rclpy.create_node('fake_navigation')
goals = []
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
    process = subprocess.Popen([
        'ros2', 'run', 'explore_lite', 'explore', '--ros-args',
        '-r', '__ns:=/exploration_validation', '-r', '/tf:=tf', '-r', '/tf_static:=tf_static',
        '--params-file', '/workspace/config/robot/explore.yaml'],
        stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        deadline = time.monotonic()+20
        while time.monotonic() < deadline and not goals:
            pub.publish(msg)
            rclpy.spin_once(node, timeout_sec=.1)
            if process.poll() is not None:
                break
        assert goals, 'explore_lite did not send a namespaced goal to fake Nav2'
        assert goals[0].header.frame_id == 'map'
        assert not node.get_publishers_info_by_topic('/cmd_vel')
        print('PASS: pinned explore_lite consumed a synthetic map/private TF and sent a namespaced Nav2 goal; isolated domain 174, no hardware commands')
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGINT)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        log.seek(0)
        print(log.read())
        server.destroy()
        node.destroy_node()
        rclpy.shutdown()
