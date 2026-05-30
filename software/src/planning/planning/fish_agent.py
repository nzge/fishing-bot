#!/usr/bin/env python3
"""The 'Fish': an environmental disturbance source.

The fish is attached to the far end of the fishing line; the near end is tied
to the rod tip. The fish does NOT talk to the controller. Instead it generates
a pulling force that is applied to the fish body in the MuJoCo simulation. That
force tensions the line tendon, and the load cell at the rod tip *measures* the
resulting tension. The controller only ever reacts to that measured tension.

Output: std_msgs/Float64MultiArray on /fish_effort_controller/commands (effort,
in Newtons, applied to the fish's MuJoCo slide joint). ros2_control's
forward_command_controller forwards it to the 'fish_force' motor.
"""
import math

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray


class FishAgent(Node):
    def __init__(self):
        super().__init__('fish_agent')

        # Disturbance profile lives in config (No Magic Numbers).
        self.declare_parameter('mean_force', 3.0)
        self.declare_parameter('amplitude', 2.0)
        self.declare_parameter('frequency', 0.5)
        self.declare_parameter('publish_frequency', 50.0)

        self.mean_force = self.get_parameter('mean_force').value
        self.amplitude = self.get_parameter('amplitude').value
        self.frequency = self.get_parameter('frequency').value
        self.publish_frequency = self.get_parameter('publish_frequency').value

        self.pub = self.create_publisher(
            Float64MultiArray, '/fish_effort_controller/commands', 10)
        self.timer = self.create_timer(1.0 / self.publish_frequency, self.timer_cb)
        self.start_time = self.get_clock().now()

        self.get_logger().info(
            f'Virtual Fish Agent generated: mean={self.mean_force} N, '
            f'amplitude={self.amplitude} N, frequency={self.frequency} Hz.')

    def timer_cb(self):
        elapsed = (self.get_clock().now() - self.start_time).nanoseconds / 1e9
        # Sine "fight" superimposed on a steady pull along the line.
        force = self.mean_force + self.amplitude * math.sin(
            2.0 * math.pi * self.frequency * elapsed)

        msg = Float64MultiArray()
        msg.data = [float(force)]
        self.pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = FishAgent()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
