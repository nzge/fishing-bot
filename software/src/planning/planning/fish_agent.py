import rclpy
from rclpy.node import Node
import math
import time
from fishing_interfaces.msg import FishingTension

class FishAgent(Node):
    def __init__(self):
        super().__init__('fish_agent')
        self.pub = self.create_publisher(FishingTension, '/fishing_arm/tension', 10)
        self.timer = self.create_timer(0.05, self.timer_cb) # 20Hz
        self.start_time = time.time()

    def timer_cb(self):
        elapsed = time.time() - self.start_time
        # Simulate fish "tug" as a sine wave
        tension = 5.0 + 2.0 * math.sin(elapsed) 
        
        msg = FishingTension()
        msg.tension_newtons = tension
        msg.target_tension_newtons = 5.0
        self.pub.publish(msg)

def main():
    rclpy.init()
    node = FishAgent()
    rclpy.spin(node)