"""ROS interface for the simulation; imports run after Isaac's bridge is enabled."""
import math
import time
import numpy as np
import rclpy
from builtin_interfaces.msg import Time
from geometry_msgs.msg import TransformStamped, Twist
from nav_msgs.msg import Odometry
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import CameraInfo, Image, JointState
from tf2_ros import TransformBroadcaster, StaticTransformBroadcaster


def stamp(seconds):
    total_ns = int(round(seconds * 1_000_000_000))
    return Time(sec=total_ns // 1_000_000_000, nanosec=total_ns % 1_000_000_000)


def transform(parent, child, position, quaternion, timestamp):
    msg = TransformStamped()
    msg.header.stamp = timestamp
    msg.header.frame_id = parent
    msg.child_frame_id = child
    msg.transform.translation.x, msg.transform.translation.y, msg.transform.translation.z = map(float, position)
    # Isaac uses wxyz; ROS uses xyzw.
    msg.transform.rotation.w, msg.transform.rotation.x, msg.transform.rotation.y, msg.transform.rotation.z = map(float, quaternion)
    return msg


class LimoBridge:
    def __init__(self, cfg):
        self.cfg = cfg
        self.ns = cfg['namespace']
        rclpy.init()
        self.node = rclpy.create_node('isaac_limo', namespace=self.ns)
        self.last_command = -math.inf
        self.target = (0.0, 0.0)
        self.sub = self.node.create_subscription(Twist, 'cmd_vel', self.on_command, 1)
        self.clock = self.node.create_publisher(Clock, '/clock', 10)
        self.odom = self.node.create_publisher(Odometry, 'odom', 10)
        self.joints = self.node.create_publisher(JointState, 'joint_states', 10)
        self.rgb = self.node.create_publisher(Image, 'camera/front/color/image_raw', 2)
        self.depth = self.node.create_publisher(Image, 'camera/front/depth/image_raw', 2)
        self.info = self.node.create_publisher(CameraInfo, 'camera/front/color/camera_info', 2)
        self.depth_info = self.node.create_publisher(CameraInfo, 'camera/front/depth/camera_info', 2)
        self.tf = TransformBroadcaster(self.node)
        self.static_tf = StaticTransformBroadcaster(self.node)
        self.static_tf.sendTransform([
            transform(self.frame('base_link'), self.frame('laser'), cfg['lidar_position'], [1, 0, 0, 0], Time()),
            transform(self.frame('base_link'), self.frame('camera_link'), cfg['camera_position'], [1, 0, 0, 0], Time()),
            transform(self.frame('camera_link'), self.frame('camera_optical_frame'), [0, 0, 0], [0.5, -0.5, 0.5, -0.5], Time()),
        ])

    def frame(self, name):
        return f'{self.ns}/{name}'

    def on_command(self, msg):
        values = (msg.linear.x, msg.angular.z)
        if not all(math.isfinite(v) for v in values):
            self.target = (0.0, 0.0)
            self.last_command = -math.inf
            return
        self.target = (max(-self.cfg['max_linear_mps'], min(self.cfg['max_linear_mps'], values[0])),
                       max(-self.cfg['max_angular_rps'], min(self.cfg['max_angular_rps'], values[1])))
        self.last_command = time.monotonic()

    def command(self, now):
        rclpy.spin_once(self.node, timeout_sec=0.0)
        return self.target if now - self.last_command <= self.cfg['command_timeout_s'] else (0.0, 0.0)

    def publish_state(self, seconds, pos, quat, linear, angular, names, positions, velocities):
        timestamp = stamp(seconds)
        self.clock.publish(Clock(clock=timestamp))
        msg = Odometry()
        msg.header.stamp = timestamp
        msg.header.frame_id = self.frame('odom')
        msg.child_frame_id = self.frame('base_link')
        msg.pose.pose.position.x, msg.pose.pose.position.y, msg.pose.pose.position.z = map(float, pos)
        msg.pose.pose.orientation.w, msg.pose.pose.orientation.x, msg.pose.pose.orientation.y, msg.pose.pose.orientation.z = map(float, quat)
        # Twist must be expressed in child_frame_id, not the world frame.
        w, x, y, z = quat
        rotation = np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                             [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                             [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
        local_v, local_w = rotation.T @ linear, rotation.T @ angular
        msg.twist.twist.linear.x, msg.twist.twist.linear.y, msg.twist.twist.linear.z = map(float, local_v)
        msg.twist.twist.angular.x, msg.twist.twist.angular.y, msg.twist.twist.angular.z = map(float, local_w)
        # Ground-truth odometry: these are explicitly small, not a hardware noise model.
        msg.pose.covariance = [0.0001 if i % 7 == 0 else 0.0 for i in range(36)]
        msg.twist.covariance = list(msg.pose.covariance)
        self.odom.publish(msg)
        self.tf.sendTransform(transform(msg.header.frame_id, msg.child_frame_id, pos, quat, timestamp))
        joints = JointState()
        joints.header.stamp = timestamp
        joints.name = list(names)
        joints.position = [float(v) for v in positions]
        joints.velocity = [float(v) for v in velocities]
        self.joints.publish(joints)

    def publish_camera(self, seconds, rgb, depth, focal_pixels):
        timestamp = stamp(seconds)
        height, width = rgb.shape[:2]
        for publisher, data, encoding in ((self.rgb, rgb, 'rgb8'), (self.depth, depth, '32FC1')):
            data = np.ascontiguousarray(data)
            msg = Image()
            msg.header.stamp = timestamp
            msg.header.frame_id = self.frame('camera_optical_frame')
            msg.height, msg.width = height, width
            msg.encoding = encoding
            msg.is_bigendian = 0
            msg.step = data.strides[0]
            msg.data = data.tobytes()
            publisher.publish(msg)
        info = CameraInfo()
        info.header = msg.header
        info.height, info.width = height, width
        info.distortion_model = 'plumb_bob'
        info.d = [0.0] * 5
        cx, cy = width / 2.0, height / 2.0
        info.k = [focal_pixels, 0.0, cx, 0.0, focal_pixels, cy, 0.0, 0.0, 1.0]
        info.r = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
        info.p = [focal_pixels, 0.0, cx, 0.0, 0.0, focal_pixels, cy, 0.0, 0.0, 0.0, 1.0, 0.0]
        self.info.publish(info)
        self.depth_info.publish(info)

    def close(self):
        self.node.destroy_node()
        rclpy.shutdown()
