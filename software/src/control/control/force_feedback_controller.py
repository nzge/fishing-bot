import rclpy

from control.fishing_controller_node import ForceFeedbackControllerNode


def main(args=None):
    rclpy.init(args=args)
    node = ForceFeedbackControllerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
