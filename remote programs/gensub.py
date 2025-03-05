import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from grove.grove_i2c_motor_driver import MotorDriver

from grove.grove_optical_rotary_encoder import GroveOpticalRotaryEncoder


class RotorSubscriber(Node):
    def __init__(self, pin=10):
        super().__init__('remote_control_publisher')
        
        self.motor = MotorDriver()
        self.encoder = GroveOpticalRotaryEncoder(pin)
        
        self.subscriber = self.create_subscription(String, 'rotor/speed_control', self.set_speed, 10)
        self.subscriber

    def set_speed(self, msg):
        self.motor.set_speed(float(msg.data))

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
