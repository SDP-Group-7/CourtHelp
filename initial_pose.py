import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseWithCovarianceStamped
import time

class InitialPosePublisher(Node):
    def __init__(self):
        super().__init__('initial_pose_publisher')
        self.publisher = self.create_publisher(PoseWithCovarianceStamped, '/initialpose', 10)
        time.sleep(2)  # Wait for Nav2 to start
        self.set_initial_pose()

    def set_initial_pose(self):
        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = "map"
        msg.pose.pose.position.x = 0.0  # Modify X coordinate
        msg.pose.pose.position.y = 0.0  # Modify Y coordinate
        msg.pose.pose.position.z = 0.0
        msg.pose.pose.orientation.z = 0.0
        msg.pose.pose.orientation.w = 1.0
        msg.pose.covariance = [0.0] * 36  # Default covariance

        self.publisher.publish(msg)
        self.get_logger().info("Initial pose set successfully!")

def main(args=None):
    rclpy.init(args=args)
    node = InitialPosePublisher()
    time.sleep(1)  # Ensure the message is sent
    rclpy.shutdown()

if __name__ == '__main__':
    main()
