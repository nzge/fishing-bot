#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
import math

class PositionTestPublisher(Node):
    def __init__(self):
        super().__init__('position_test_publisher')
        
        self.trajectory_pub = self.create_publisher(
            JointTrajectory,
            '/position_trajectory_controller/joint_trajectory',
            10
        )
        
        # 10Hz control loop step to update smooth trajectory points
        self.timer = self.create_timer(0.1, self.timer_callback)
        self.start_time = self.get_clock().now()
        
        # Operational limits for safety profile
        self.max_amplitude = 0.5  # radians (~28 degrees)
        self.frequency = 0.2     # Hz (slow cycles to preserve internal motor gears)
        
        self.get_logger().info("Dynamixel position validation node initialized.")

    def timer_callback(self):
        current_time = self.get_clock().now()
        elapsed_time = (current_time - self.start_time).nanoseconds / 1e9
        
        # Calculate smooth sinusoidal target configuration
        target_position = self.max_amplitude * math.sin(2.0 * math.pi * self.frequency * elapsed_time)
        
        msg = JointTrajectory()
        msg.joint_names = ['Joint_1']
        
        point = JointTrajectoryPoint()
        point.positions = [target_position]
        point.time_from_start.sec = 0
        point.time_from_start.nanosec = int(1e8) # Command arriving 100ms smoothly from start
        
        msg.points.append(point)
        self.trajectory_pub.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = PositionTestPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()