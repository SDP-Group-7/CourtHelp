import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import subprocess
import shutil

from grove.grove_i2c_motor_driver import MotorDriver

from grove.grove_optical_rotary_encoder import GroveOpticalRotaryEncoder


class RotorSubscriber(Node):
    def __init__(self, pin=10):
        super().__init__('remote_control_publisher')
        
        self.motor = MotorDriver()
        self.encoder = GroveOpticalRotaryEncoder(pin)
        self.cam_on = False
        self.cam_process = None
        
        self.rotor_subscriber = self.create_subscription(String, 'rotor/speed_control', self.set_speed, 10)
        self.rotor_subscriber

        self.camset_subscriber = self.create_subscription(String, 'camera/change_status', self.set_cam_status, 10)
        self.camset_subscriber

    def set_speed(self, msg):
        self.motor.set_speed(float(msg.data))

    def set_cam_status(self, msg):
        if msg.data == "on" and not self.cam_on:
            self.cam_process = subprocess.Popen([shutil.which("python3"), "~/CourtHelp/camera_publisher.py"])
        elif msg.data == "off" and self.cam_on:
            self.cam_process.kill()

    def destroy_node(self):
        self.motor.set_speed(0)
        super().destroy_node()
        self.get_logger().info("Remote node shutting down")


def main(args=None):
    rclpy.init(args=args)
    node = RotorSubscriber()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Keyboard interrupt detected, shutting down")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
