#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import String
from nav_msgs.msg import Odometry
import math

class MoveAndDisplayOdom(Node):
    def __init__(self):
        super().__init__('move_and_display_odom')

        # Publisher to move the robot
        self.vel_pub = self.create_publisher(Twist, '/cmd_vel', 40)

        # Publisher to send "run" to Arduino
        self.cmd_pub = self.create_publisher(String, '/arduino_command', 10)

        # Subscriber to receive odometry
        self.odom_sub = self.create_subscription(Odometry, '/odom', self.odom_callback, 10)

        # Initialize the starting position
        self.start_x = None
        self.start_y = None

        # Distance traveled tracking
        self.distance_travelled = 0.0

        # Movement command
        self.move_cmd = Twist()
        self.move_cmd.linear.x = 0.05    # Move at 0.2 m/s
        self.move_cmd.linear.y = 0.0
        self.move_cmd.angular.z = -0.05  # Move at 0.2 m/s

        # Flag to send "run" command to Arduino
        self.sent = False

        # Set up the timer to keep moving the robot
        self.create_timer(0.025, self.move_forward)  # Move forward every 0.1s

    def move_forward(self):
        # Publish the move command to move the robot forward
        self.vel_pub.publish(self.move_cmd)

    def odom_callback(self, msg):
        # Get current position from odometry message
        current_x = msg.pose.pose.position.x
        current_y = msg.pose.pose.position.y

        if self.start_x is None and self.start_y is None:
            # First time: set starting position
            self.start_x = current_x
            self.start_y = current_y
        else:
            # Calculate the distance traveled from the start
            self.distance_travelled = math.sqrt((current_x - self.start_x) ** 2 + (current_y - self.start_y) ** 2)

            # Log the current position and distance
            self.get_logger().info(f'Current Position: x={current_x}, y={current_y}')
            self.get_logger().info(f'Distance travelled: {self.distance_travelled:.2f} meters')

            tolerance = 0.03

            # Stop the robot if it has moved ≥ 0.50 meters and send the input command to Arduino
            if self.distance_travelled >= 0.50 - tolerance and not self.sent:
                # Stop the robot
                self.move_cmd.linear.x = 0.0
                self.move_cmd.angular.z = 0.0
                self.vel_pub.publish(self.move_cmd)

                # Send "run" to Arduino
                msg = String()
                msg.data = "run"
                self.cmd_pub.publish(msg)

                # Set flag to avoid sending "run" again
                self.sent = True

                # Log that the robot stopped and the command was sent
                self.get_logger().info(f'Stopped at {self.distance_travelled:.2f} meters. Sent "run" to Arduino.')

def main(args=None):
    rclpy.init(args=args)
    node = MoveAndDisplayOdom()
    rclpy.spin(node)  # Keep the node running

    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
