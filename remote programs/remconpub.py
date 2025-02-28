import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import pyIR


class RemoteControlPublisher(Node):
    def __init__(self, remotefile, pin):
        super().__init__('remote_control_publisher')

        self.publisher = self.create_publisher(String, 'remote_control/button', 5)

        self.rec = pyIR.Receiver(pin)
        self.rec.addRemote(pyIR.loadRemote(remotefile))

        self.start_listening()

    def start_listening(self):
        self.publisher.publish(self.rec.listen())
        if True:
            self.start_listening()

    def destroy_node(self):
        super().destroy_node()
        self.get_logger().info("Remote node shutting down")


def main(args=None):
    rclpy.init(args=args)
    node = RemoteControlPublisher("BENQ_remote", 29)
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Keyboard interrupt detected, shutting down")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
