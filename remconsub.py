import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class RemoteControlSubscriber(Node):
    def __init__(self, linkf):
        super().__init__('remote_control_publisher')


        self.subscriber = self.create_subscription(String, 'remote_control/button', linkf, 5)
        self.subscriber

    def destroy_node(self):
        super().destroy_node()
        self.get_logger().info("Remote node shutting down")


def main(args=None):
    node = RemoteControlSubscriber()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Keyboard interrupt detected, shutting down")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    rclpy.init(args=args)
    main()
