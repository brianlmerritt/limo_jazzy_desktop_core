#!/usr/bin/env python3
"""Preserve LaserScan geometry; represent invalid measurements as NaN."""
import math


def sanitize_scan(scan):
    if not (math.isfinite(scan.range_min) and math.isfinite(scan.range_max)
            and 0 <= scan.range_min < scan.range_max):
        raise ValueError('LaserScan requires finite ordered nonnegative range limits')
    scan.ranges = [r if math.isfinite(r) and r > 0
                   and scan.range_min <= r <= scan.range_max else math.nan
                   for r in scan.ranges]
    return scan


def main():
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import LaserScan

    rclpy.init()
    node = Node('scan_sanitizer')
    publisher = node.create_publisher(LaserScan, 'scan', qos_profile_sensor_data)

    def receive(msg):
        try:
            publisher.publish(sanitize_scan(msg))
        except ValueError as error:
            node.get_logger().error(str(error), throttle_duration_sec=5.0)

    node.create_subscription(LaserScan, 'scan_raw', receive, qos_profile_sensor_data)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
