import rclpy
from rclpy.node import Node
import cv2
from std_msgs.msg import String


class TestPub(Node):
    def __init__(self):

        # Create a subscription to the image topic
        self.subscription = self.create_publisher(
            String,
            'rotor/speed_control',  # Must match the topic from the TurtleBot
            10)
        self.publisher.publish("22")

    def destroy_node(self):
        super().destroy_node()
        self.get_logger().info("Camera subscriber node shutting down")


def main(args=None):
    rclpy.init(args=args)
    node = TestPub()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Keyboard interrupt detected, shutting down")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
