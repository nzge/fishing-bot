import rclpy
from rclpy.node import Node
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from fishing_interfaces.msg import FishingTension # Your custom message

class AdmittanceController(Node):
    def __init__(self):
        super().__init__('admittance_controller')
        
        # Parameters
        self.declare_parameter('admittance_gain', 0.1) # 1/Damping
        self.gain = self.get_parameter('admittance_gain').value
        
        # Publishers & Subscribers
        self.pub = self.create_publisher(JointTrajectory, '/fishing_arm_controller/joint_trajectory', 10)
        self.sub = self.create_subscription(FishingTension, '/fishing_arm/tension', self.tension_cb, 10)
        
        self.get_logger().info("Admittance Controller Initialized")

    def tension_cb(self, msg):
        # Admittance Law: v = (F_ext - F_target) * gain
        error = msg.target_tension_newtons - msg.tension_newtons
        velocity = error * self.gain
        
        # Create trajectory command
        traj = JointTrajectory()
        traj.joint_names = ['Joint_1', 'Joint_2']
        point = JointTrajectoryPoint()
        point.velocities = [velocity, velocity]
        point.time_from_start = rclpy.duration.Duration(seconds=0.1).to_msg()
        traj.points.append(point)
        
        self.pub.publish(traj)

def main():
    rclpy.init()
    node = AdmittanceController()
    rclpy.spin(node)
    rclpy.shutdown()