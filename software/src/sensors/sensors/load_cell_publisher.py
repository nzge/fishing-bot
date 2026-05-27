#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64
import math

class LoadCellPublisher(Node):
    def __init__(self):
        super().__init__('load_cell_publisher')
        
        # Create a publisher that targets the '/tension' topic [cite: 24, 152]
        # Using standard Float64 for simple prototyping [cite: 70]
        self.publisher_ = self.create_publisher(Float64, '/tension', 10)
        
        # Set loop frequency to 80Hz to match high-frequency data requirements [cite: 776]
        self.timer_period = 1.0 / 80.0  # 80 Hz [cite: 776]
        self.timer = self.create_timer(self.timer_period, self.timer_callback)
        
        # Internal tracking variable to mimic a living environment
        self.time_counter = 0.0
        self.get_logger().info('Load Cell Publisher Node initialized running at 80Hz.')

    def timer_callback(self):
        msg = Float64()
        
        # --- PLACEHOLDER FOR HARDWARE OR SIMULATION DISTURBANCE ---
        # For testing, we mimic a 1D tension signal containing a 10N bias 
        # and a sinusoidal fluctuation to simulate minor water wave action[cite: 306, 689].
        base_tension = 10.0 
        wave_disturbance = 2.0 * math.sin(2.0 * math.pi * 1.0 * self.time_counter)
        
        msg.data = base_tension + wave_disturbance
        # -----------------------------------------------------------
        
        # Publish the tension to the network graph [cite: 24, 100]
        self.publisher_.publish(msg)
        
        # Log to the terminal console at lower frequency so it doesn't flood your window
        if int(self.time_counter * 80) % 40 == 0:
            self.get_logger().info(f'Publishing Line Tension: {msg.data:.2f} Newtons')
            
        self.time_counter += self.timer_period

def main(args=None):
    rclpy.init(args=args)
    node = LoadCellPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()