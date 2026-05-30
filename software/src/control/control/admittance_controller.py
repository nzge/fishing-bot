import rclpy
from rclpy.node import Node
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from interfaces.msg import FishingTension


class AdmittanceController(Node):
    def __init__(self):
        super().__init__('admittance_controller')

        # Defensive Coding: Parameterization (No Magic Numbers)
        self.declare_parameter('admittance_gain', 0.1)  # 1/Damping
        self.declare_parameter('max_velocity', 1.0)
        self.declare_parameter('safety_tension_limit', 20.0)
        self.declare_parameter('target_tension', 5.0)  # desired line tension setpoint
        self.gain = self.get_parameter('admittance_gain').value
        self.max_velocity = self.get_parameter('max_velocity').value
        self.safety_tension_limit = self.get_parameter('safety_tension_limit').value
        self.target_tension = self.get_parameter('target_tension').value

        # Publishers & Subscribers
        self.pub = self.create_publisher(
            JointTrajectory, '/position_trajectory_controller/joint_trajectory', 10)
        self.sub = self.create_subscription(
            FishingTension, '/fishing_arm/tension', self.tension_cb, 10)

        self.get_logger().info(
            'Admittance Controller Initialized. Waiting for tension data...')

    def tension_cb(self, msg):
        # Safety: clamp on excessive line tension (E-Stop behaviour)
        if abs(msg.tension_newtons) > self.safety_tension_limit:
            self.get_logger().warn(
                f'Tension {msg.tension_newtons:.2f} N exceeds safety limit '
                f'{self.safety_tension_limit:.2f} N. Holding position.')
            return

        # Admittance Law: v = (F_target - F_measured) * gain.
        # The setpoint is OUR parameter; we only consume the measured tension
        # from the sensor (msg.tension_newtons), never a target off the wire.
        error = self.target_tension - msg.tension_newtons
        velocity = error * self.gain

        # Saturate to the configured velocity envelope
        velocity = max(-self.max_velocity, min(self.max_velocity, velocity))

        # Dispatch command to the Controller Manager
        traj = JointTrajectory()
        traj.joint_names = ['Joint_1', 'Joint_2']
        point = JointTrajectoryPoint()
        point.velocities = [velocity, velocity]
        point.time_from_start = rclpy.duration.Duration(seconds=0.1).to_msg()
        traj.points.append(point)

        self.pub.publish(traj)


def main(args=None):
    rclpy.init(args=args)
    node = AdmittanceController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
