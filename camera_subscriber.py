import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2


class CameraSubscriber(Node):
    def __init__(self):
        super().__init__('camera_subscriber')

        # Create a subscription to the image topic
        self.subscription = self.create_subscription(
            Image,
            'camera/image_raw',  # Must match the topic from the TurtleBot
            self.image_callback,
            10)
        
        self.bridge = CvBridge()
        self.get_logger().info("Camera subscriber node started")

    def image_callback(self, msg):
        try:
            # Convert ROS Image message to OpenCV format
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")

            # Display the frame
            cv2.imshow("TurtleBot Camera Stream", frame)

            # Press 'q' to exit
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.get_logger().info("Exiting camera stream...")
                rclpy.shutdown()

        except Exception as e:
            self.get_logger().error(f"Failed to process image: {e}")

    def destroy_node(self):
        super().destroy_node()
        cv2.destroyAllWindows()
        self.get_logger().info("Camera subscriber node shutting down")


def main(args=None):
    rclpy.init(args=args)
    node = CameraSubscriber()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Keyboard interrupt detected, shutting down")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
