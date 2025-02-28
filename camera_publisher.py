import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2


class Camera1Publisher(Node):
    def __init__(self):
        super().__init__('camera_publisher')

        # Create a publisher for the camera feed
        self.publisher = self.create_publisher(Image, 'camera/image_raw', 10)

        # Initialize OpenCV video capture (Using /dev/video0)
        self.bridge = CvBridge()
        self.cap = cv2.VideoCapture("/dev/video2", cv2.CAP_V4L2)

        # Set camera properties
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 20)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))  # Use MJPG for better performance

        if not self.cap.isOpened():
            self.get_logger().error("Cannot open /dev/video2")
            return

        # Set a timer to publish frames at 10Hz (every 0.1 seconds)
        self.timer = self.create_timer(0.1, self.publish_frame)

    def publish_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            self.get_logger().error("Failed to capture image")
            return

        # Flip the frame (optional)
        frame = cv2.flip(frame, 0)

        # Convert OpenCV image to ROS Image message
        msg = self.bridge.cv2_to_imgmsg(frame, encoding="bgr8")
        self.publisher.publish(msg)

    def destroy_node(self):
        super().destroy_node()
        self.cap.release()
        self.get_logger().info("Camera node shutting down")


def main(args=None):
    rclpy.init(args=args)
    node = Camera1Publisher()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Keyboard interrupt detected, shutting down")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
