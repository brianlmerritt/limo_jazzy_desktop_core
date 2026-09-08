#!/usr/bin/env python3
"""Forward-only gate with a default-on, 1 Hz scan/TF consistency check.

Native ROS parameters only; deployment supplies expected laser extrinsics.
This is a diagnostic interlock, not certified collision or cliff protection.
"""
import json
import math
import time
import signal

import rclpy
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from rclpy.qos import qos_profile_sensor_data, QoSProfile, DurabilityPolicy
from geometry_msgs.msg import Twist
from nav_msgs.msg import OccupancyGrid
from sensor_msgs.msg import LaserScan, Imu
from std_msgs.msg import String
from tf2_ros import Buffer, TransformListener

from navigation_guard_core import (DEFAULT_POLICY, validate_policy, alignment_state, action_scale,
                                   angle_difference, forward_command, scan_map_score)


def yaw(q):
    return math.atan2(2 * (q.w*q.z + q.x*q.y), 1 - 2*(q.y*q.y + q.z*q.z))


def transform_point(t, x, y):
    q = t.rotation
    return ((1-2*(q.y*q.y+q.z*q.z))*x + 2*(q.x*q.y-q.z*q.w)*y + t.translation.x,
            2*(q.x*q.y+q.z*q.w)*x + (1-2*(q.x*q.x+q.z*q.z))*y + t.translation.y)


class NavigationGuard(Node):
    def __init__(self):
        super().__init__('navigation_guard')
        defaults = {'check_lidar_orientation': True, 'expected_laser_xyz': [0.103, 0.0, -0.034],
                    'expected_laser_rpy': [0.0, 0.0, math.pi],
                    'alignment_policy_json': json.dumps(DEFAULT_POLICY)}
        for name, value in defaults.items():
            self.declare_parameter(name, value)
        self.enabled = self.get_parameter('check_lidar_orientation').value
        self.xyz = self.get_parameter('expected_laser_xyz').value
        self.rpy = self.get_parameter('expected_laser_rpy').value
        if not isinstance(self.enabled, bool) or any(len(v) != 3 or not all(math.isfinite(x) for x in v)
                                                    for v in [self.xyz, self.rpy]):
            raise ValueError('Invalid guard parameters')
        # This platform uses an upright planar scanner. Refuse an unsupported mount.
        if abs(self.rpy[0]) > 1e-6 or abs(self.rpy[1]) > 1e-6:
            raise ValueError('Guard expects an upright planar laser mount')
        self.buffer = Buffer()
        self.listener = TransformListener(self.buffer, self)
        self.data = {}
        self.command = None
        self.policy = validate_policy(json.loads(self.get_parameter('alignment_policy_json').value))
        self.scale = 0.0
        self.last_pose = None
        self.last_check = 0.0
        self.ready = False
        self.reason = 'waiting for data'
        self.create_subscription(Twist, 'cmd_vel_smoothed', self.receive_command, 10)
        self.create_subscription(LaserScan, 'scan', lambda m: self.receive('scan', m), qos_profile_sensor_data)
        self.create_subscription(Imu, 'imu', lambda m: self.receive('imu', m), qos_profile_sensor_data)
        self.create_subscription(OccupancyGrid, 'map', lambda m: self.receive('map', m),
                                 QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.output = self.create_publisher(Twist, 'cmd_vel_guarded', 10)
        self.status = self.create_publisher(String, 'navigation_guard/status',
                                           QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.create_timer(1.0, self.check_alignment)
        self.create_timer(0.05, self.forward)

    def receive(self, key, msg):
        self.data[key] = (time.monotonic(), msg)

    def receive_command(self, msg):
        self.command = (time.monotonic(), msg)

    def stamp_age(self, msg):
        return (self.get_clock().now().nanoseconds -
                (msg.header.stamp.sec * 10**9 + msg.header.stamp.nanosec)) / 1e9

    def sensor_error(self):
        now = time.monotonic()
        for key in ('scan', 'imu'):
            if key not in self.data or now - self.data[key][0] > 0.5:
                return 'missing/stale ' + key
            if not -0.1 <= self.stamp_age(self.data[key][1]) <= 0.5:
                return 'invalid timestamp: ' + key
        return None

    def alignment_evidence(self):
        # Evaluate mount/odometry and scan-map evidence independently so one
        # disagreement does not hide the other. No TF is published by this node.
        scan = self.data['scan'][1]
        stamp = rclpy.time.Time.from_msg(scan.header.stamp)
        orientation_ok = None
        map_state = 'unavailable'
        details = {}
        try:
            mount = self.buffer.lookup_transform('base_link', scan.header.frame_id, stamp).transform
            pos, q = mount.translation, mount.rotation
            expected = [0.0, 0.0, math.sin(self.rpy[2]/2), math.cos(self.rpy[2]/2)]
            dot = abs(sum(a*b for a, b in zip([q.x, q.y, q.z, q.w], expected)))
            mount_ok = (math.dist([pos.x, pos.y, pos.z], self.xyz) <= 0.01 and
                        2*math.acos(min(1.0, dot)) <= math.radians(2))
            pose = self.buffer.lookup_transform('odom', 'base_link', stamp).transform
            now = time.monotonic()
            current = (pose.translation.x, pose.translation.y, yaw(pose.rotation), now)
            odom_ok = True
            if self.last_pose:
                x, y, a, previous = self.last_pose
                dt = now - previous
                odom_ok = (math.hypot(current[0]-x, current[1]-y) <= 0.15*dt + 0.10 and
                           abs(angle_difference(current[2], a)) <= 0.35*dt + 0.10)
            self.last_pose = current
            orientation_ok = mount_ok and odom_ok
            details.update(mount_ok=mount_ok, odometry_continuous=odom_ok)
        except Exception as exc:
            details['orientation_error'] = str(exc)
        try:
            if 'map' not in self.data:
                raise ValueError('waiting for map')
            if not math.isfinite(scan.angle_min) or not math.isfinite(scan.angle_increment) or scan.angle_increment <= 0 or len(scan.ranges) < 30:
                raise ValueError('invalid scan geometry')
            tf = self.buffer.lookup_transform('map', scan.header.frame_id, stamp).transform
            points = [transform_point(tf, r*math.cos(scan.angle_min+i*scan.angle_increment),
                                      r*math.sin(scan.angle_min+i*scan.angle_increment))
                      for i, r in enumerate(scan.ranges) if i % 2 == 0 and math.isfinite(r)
                      and max(scan.range_min, 0.25) <= r <= min(scan.range_max, 7.0)]
            m = self.data['map'][1]
            if m.header.frame_id != 'map' or not math.isfinite(m.info.resolution) or m.info.resolution <= 0 or len(m.data) != m.info.width*m.info.height:
                raise ValueError('invalid map')
            origin = m.info.origin
            known, score = scan_map_score(points, m.data, m.info.width, m.info.height, m.info.resolution,
                                         (origin.position.x, origin.position.y, yaw(origin.orientation)))
            details.update(known_endpoints=known, matched_fraction=round(score, 3))
            map_state = 'insufficient' if known < 30 else ('match' if score >= 0.55 else 'mismatch')
        except Exception as exc:
            details['map_error'] = str(exc)
        details.update(map_evidence=map_state, orientation_ok=orientation_ok)
        return alignment_state(map_state, orientation_ok), details

    def check_alignment(self):
        health_error = self.sensor_error()
        state, details = 'disabled', {}
        action = 'continue'
        if health_error:
            state, action = 'sensor_unavailable', 'hold'
        elif self.enabled:
            state, details = self.alignment_evidence()
            action = self.policy[state]
        self.scale = action_scale(action)
        self.ready = self.scale > 0
        self.reason = health_error or state
        self.last_check = time.monotonic()
        self.status.publish(String(data=json.dumps({'ready': self.ready, 'reason': self.reason,
                                                   'check_lidar_orientation': self.enabled,
                                                   'latched': False, 'state': state, 'action': action,
                                                   'speed_scale': self.scale, **details})))

    def forward(self):
        now = time.monotonic()
        result = Twist()
        fresh = self.sensor_error() is None
        if self.ready and fresh and now-self.last_check < 1.5 and self.command and now-self.command[0] < 0.3:
            msg = self.command[1]
            values = [msg.linear.x, msg.linear.y, msg.linear.z, msg.angular.x, msg.angular.y, msg.angular.z]
            if forward_command(values):
                result.linear.x = msg.linear.x * self.scale
                result.angular.z = msg.angular.z * self.scale
        self.output.publish(result)


def main():
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    def terminate(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, terminate)
    node = NavigationGuard()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.output.publish(Twist())
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
