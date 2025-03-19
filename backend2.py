from ultralytics import YOLO
import subprocess
import os
import time
import cv2
import numpy as np
import threading
import rclpy
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import shutil
import math

import tf_transformations
import tf2_ros
import tf2_geometry_msgs
from geometry_msgs.msg import PoseWithCovarianceStamped
from std_msgs.msg import String
from geometry_msgs.msg import Twist
import remconsub
from std_msgs.msg import Float32MultiArray
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

home_zone = None
map_filename = None


"""
class RemotePressError(Exception):
    pass


class RemoteHandler(threading.Thread):
    def __init__(self, remotefile="BENQ_REMOTE", pin=29, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.result = None
        self.ketchup_blast = remconsub.RemoteControlSubscriber(self.reunite)
        
    def run(self):
        rclpy.spin(self.ketchup_blast)

    def join(self):
        threading.Thread.join(self)

    def reunite(self, msg):
        self.result = msg
        

    def reset(self):
        self.result = None
    """


def run_ros_package():
    """Triggers SLAM and the motions without opening a new terminal."""
    try:
        subprocess.Popen(
            ["ros2", "launch", "turtlebot3_cartographer", "cartographer.launch.py"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setpgrp  # For Linux/Unix systems
        )
    except subprocess.CalledProcessError as e:
        print("Error running ROS package:", e)


def run_ros_package2(save_path):
    """Saves map in current directory and closes stuff without opening a new terminal."""
    try:
        print("Checking if ROS map server is ready...")
        time.sleep(5)
        subprocess.run(
            ["ros2", "run", "nav2_map_server", "map_saver_cli", "-f", save_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
    except subprocess.CalledProcessError as e:
        print("Error running ROS package:", e)


def start_navigation_server(map_path):
    print(map_path)
    """Starts the TurtleBot3 Navigation Server with a specific map in the background."""
    try:
        subprocess.Popen(
            ["ros2", "launch", "nav2_bringup", "localization_launch.py", "map:=map2.yaml"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setpgrp
        )
        time.sleep(5)
        
        subprocess.Popen(
            ["ros2", "launch", "turtlebot3_navigation2", "navigation2.launch.py", "map:=map2.yaml", "use_sim_time:=False"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setpgrp
        )
        # Wait before setting initial pose
        time.sleep(5)
        
        subprocess.Popen(
            ["python3", "initial_pose.py"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setpgrp
        )
        
    except Exception as e:
        print(f"Error starting Navigation Server: {e}")

class BallDetector(Node):
    def __init__(self, map_path, home_zone):   #self, remhandle, map_path
        super().__init__('ball_detector')
        #self.remhandle = remhandle
        #start_navigation_server(map_path)
        # Subscribe to TurtleBot's camera feed
        self.current_goal_handle = None
        self.home_zone = home_zone
        
        self.subscription = self.create_subscription(
            Image,
            'camera/image_raw',
            self.image_callback,
            10)
        self.bridge = CvBridge()
        self.model = YOLO('yolo11s.pt')  # Load YOLO model
        """
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)"""

        self.current_pose = None


        self.pose_subscriber = self.create_subscription(
            PoseWithCovarianceStamped,
            '/amcl_pose',
            self.pose_callback,
            10
        )

        
        #self.rotor_publisher = self.create_publisher(String, 'rotor/speed_control', 10)

        #self.cam_status_publisher = self.create_publisher(String, 'camera/change_status', 10)

        # Parameters for distance estimation
        self.FOCAL_LENGTH = 800  # Requires calibration
        self.REAL_DIAMETER = 0.040  # Ball diameter in meters
        self.CAMERA_HEIGHT = 0.13  
        self.CAMERA_FORWARD = 0.15 
        self.rotating = False 

        self.cumulative_rotation = 0       # Total degrees rotated in search mode
        self.search_rotation_angle =10      # Rotate 90° each time when no ball detected
        self.mode = "search" 

        # ROS 2 Navigation Client
        self.nav_client = ActionClient(self, NavigateToPose, '/navigate_to_pose')
        self.vel_publisher = self.create_publisher(Twist, '/cmd_vel', 10)
        
        self.get_logger().info("Ball detector node started")
    '''
    def cam_on(self):
        self.cam_status_publisher.publish("on")

    def cam_off(self):
        self.cam_status_publisher.publish("off")
    
    def motor_on(self):
        self.rotor_publisher.publish("22")
    
    def motor_off(self):
        self.rotor_publisher.publish("0")
    
    def warmup_out(self):
        self.cam_on()
        self.motor_on()
    
    def cooldown_out(self):
        self.cam_off()
        self.motor_off()'''

    def pose_callback(self, msg):
        """ Update the robot's current pose from AMCL. """
        self.current_pose = msg.pose.pose

    def image_callback(self, msg):
        try:
            # Convert ROS Image message to OpenCV format
            if self.mode != "search":
                return

            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")

            # Process frame with YOLO
            results = self.model(frame, device="cpu")
            detections = results[0]

            cv2.imshow("Ball Detection", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.get_logger().info("Exiting camera stream...")
                rclpy.shutdown()

            CX, CY = frame.shape[1] // 2, frame.shape[0] // 2
            detected_balls = []

            for box in detections.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                confidence = box.conf[0].item()
                class_id = int(box.cls[0].item())
                class_name = detections.names[class_id]

                if class_name in ["orange", "sports ball"] and confidence > 0.3:
                    detected_balls.append((x1, y1, x2, y2, confidence))
            if detected_balls:
                #self.rotating = False
                self.mode = "navigating"
                self.cumulative_rotation = 0.0
                self.rotating = False
                for (x1, y1, x2, y2, confidence) in detected_balls:
                    x_center, y_center = (x1 + x2) // 2, (y1 + y2) // 2
                    box_width = x2 - x1
                    box_height = y2 - y1

                    aspect_ratio = box_width / box_height
                    is_valid_ratio = 0.7 <= aspect_ratio <= 1.3

                    #yaw_angle = math.degrees(math.atan2((x_center - CX), self.FOCAL_LENGTH))
                    yaw_angle = math.degrees(math.atan2((CX - x_center), self.FOCAL_LENGTH))


                    if is_valid_ratio:
                        pixel_size = max(box_width, box_height)
                        Z = self.calculate_distance(self.FOCAL_LENGTH, self.REAL_DIAMETER, pixel_size)

                        X_robot, Y_robot, Z_robot, _ = self.calculate_robot_position(
                            x_center, y_center, pixel_size, frame.shape[1], frame.shape[0]
                        )

                        X, Y = self.calculate_xy(Z, yaw_angle)

                        self.get_logger().info(f"Ball detected at: X={X:.3f}m, Y={Y:.3f}m, Z={Z:.3f}m, Angle={yaw_angle:.1f}°")

                        # Send Navigation Goal
                        self.send_navigation_goal(X, Y)
                        return  
            else:
                '''if self.rotation_count < 4:
                    if not self.rotating:
                        self.rotating = True
                        self.get_logger().info(f"Rotating... {self.rotation_count * 90}° completed")
                        self.create_timer(5.0, self.rotate_and_reset)
                    self.rotation_count += 1
                else:
                    self.get_logger().info("No balls found after full rotation. Returning to home zone.")
                    self.send_home_goal(self.home_zone)
                    self.rotation_count = 0'''
                if not self.rotating:
                    self.mode = "rotating"
                    self.rotating = True
                    self.create_timer(5.0, self.rotate_and_reset)

            
            #if self.remhandle.result is not None:
                #raise RemotePressError()
            

        except Exception as e:
            self.get_logger().error(f"Error processing image: {e}")

    def rotate_robot(self, degrees):
        twist_msg = Twist()
        angular_speed = 0.3  # rad/s, adjust as needed
        angle_radians = math.radians(degrees)
        
        # Set angular velocity in the desired direction:
        twist_msg.angular.z = angular_speed if degrees > 0 else -angular_speed
        self.vel_publisher.publish(twist_msg)
        
        #duration = abs(angle_radians) / angular_speed
        self.get_logger().info(f"Rotating {degrees} degrees (seconds)...")
        #time.sleep(duration)
        time.sleep(abs(angle_radians) / angular_speed)
        
        # Stop rotation
        twist_msg.angular.z = 0.0
        self.vel_publisher.publish(twist_msg)

    def rotate_and_reset(self):
        """ Rotate the robot and then reset the flag after 5 seconds. """
        if not self.rotating:
            return
        # Rotate by a fixed angle (e.g., 90 degrees)
        self.rotate_robot(self.search_rotation_angle)
        self.cumulative_rotation += self.search_rotation_angle
        self.get_logger().info(f"Cumulative rotation: {self.cumulative_rotation}°")
        
        if self.cumulative_rotation >= 360:
            self.get_logger().info("Full 360° rotation reached. Switching to home mode.")
            self.mode = "go_home"
            self.send_home_goal(home_zone)
            self.cumulative_rotation = 0
        else:
            self.create_timer(3.0, self.reset_rotation_flag)

    def reset_rotation_flag(self):
        """ Reset the rotation flag so the robot can turn again. """
        self.rotating = False

    def calculate_distance(self, focal_length, real_diameter, pixel_size):
        """Calculate distance from the camera to the detected object."""
        if pixel_size <= 0:
            return None
        return (focal_length * real_diameter) / pixel_size
    

    def calculate_robot_position(self, x_center, y_center, pixel_size, frame_width, frame_height):
        """Calculate the robot's position relative to the detected ball."""
        Z_cam = (self.FOCAL_LENGTH * self.REAL_DIAMETER) / pixel_size  

        C_X, C_Y = frame_width // 2, frame_height // 2
        X_cam = ((x_center - C_X) * Z_cam) / self.FOCAL_LENGTH  

        X_robot = Z_cam - self.CAMERA_FORWARD
        Y_robot = X_cam
        Z_robot = self.CAMERA_HEIGHT  

        yaw_angle = math.degrees(math.atan2(X_cam, Z_cam))

        return X_robot, Y_robot, Z_robot, yaw_angle

    def calculate_xy(self, z, theta_degrees):
        """Convert Z distance and yaw angle to X, Y coordinates."""
        theta_radians = np.radians(theta_degrees)
        x = z * np.cos(theta_radians)
        y = z * np.sin(theta_radians)
        return x, y
    
    def send_home_goal(self, home_zone):
        """ Converts pixel-based home zone coordinates to real-world map coordinates and sends them as a goal. """
        if home_zone is None:
            self.get_logger().error("Home zone is not set! Cannot navigate home.")
            return
        
        x_current = self.current_pose.position.x
        y_current = self.current_pose.position.y
        qx = self.current_pose.orientation.x
        qy = self.current_pose.orientation.y
        qz = self.current_pose.orientation.z
        qw = self.current_pose.orientation.w

            # Convert quaternion to yaw angle
        yaw = math.atan2(2.0 * (qw * qz + qx * qy), 1.0 - 2.0 * (qy * qy + qz * qz))


        # Convert pixel-based home zone to real-world map coordinates (if needed)
        px, py = home_zone  # Received from frontend (assumed in pixels)
        map_resolution = 0.05  # Example: meters per pixel
        map_origin = (-3.0, -4.0)  # Origin in meters (update according to your map)
        image_height = 155  # Example map height in pixels

        wx = map_origin[0] + (px * map_resolution)
        wy = map_origin[1] + ((image_height - py) * map_resolution)

        self.get_logger().info(f"Returning to Home: {wx:.2f}, {wy:.2f}")
        self.get_logger().info(f"Current Pose: {self.current_pose.position.x}, {self.current_pose.position.y}")

        # Create the home goal message
        goal_msg_home = NavigateToPose.Goal()
        goal_msg_home.pose.header.frame_id = "map"
        goal_msg_home.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg_home.pose.pose.position.x = wx
        goal_msg_home.pose.pose.position.y = wy
        # For a stationary goal, you can set a neutral orientation.
        yaw_to_goal = math.atan2(wx - y_current, wy - x_current)
        quat = tf_transformations.quaternion_from_euler(0, 0, yaw_to_goal)
        # You might want to set it explicitly to face forward:
        goal_msg_home.pose.pose.orientation.x = quat[0]
        goal_msg_home.pose.pose.orientation.y = quat[1]
        goal_msg_home.pose.pose.orientation.z = quat[2]
        goal_msg_home.pose.pose.orientation.w = quat[3]

        self.get_logger().info("Sending home goal...")

        # Send the goal and block until it completes
        send_goal_future = self.nav_client.send_goal_async(goal_msg_home)
        rclpy.spin_until_future_complete(self, send_goal_future)
        goal_handle = send_goal_future.result()
        if not goal_handle.accepted:
            self.get_logger().error("Home goal was rejected!")
            return

        self.get_logger().info("Home goal accepted. Waiting for result...")
        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)
        result = result_future.result()
        self.get_logger().info("Home goal reached. Stopping robot.")

    def send_navigation_goal(self, x_real, y_real):

        try:

            if self.current_pose is None:
                self.get_logger().warn("Waiting for AMCL pose...")
                for _ in range(60):
                    rclpy.spin_once(self, timeout_sec=1.0)
                    #if self.current_pose is not None:
                        #break
                
                if self.current_pose is None:
                    self.get_logger().error("AMCL pose not received after timeout, cannot calculate goal.")
                    return
                
            self.get_logger().info(f"Current Pose: {self.current_pose.position.x}, {self.current_pose.position.y}")
            x_current = self.current_pose.position.x
            y_current = self.current_pose.position.y
            qx = self.current_pose.orientation.x
            qy = self.current_pose.orientation.y
            qz = self.current_pose.orientation.z
            qw = self.current_pose.orientation.w

            # Convert quaternion to yaw angle
            yaw = math.atan2(2.0 * (qw * qz + qx * qy), 1.0 - 2.0 * (qy * qy + qz * qz))

            # Transform relative coordinates into the map frame
            x_map = x_current + (x_real * math.cos(yaw) - y_real * math.sin(yaw))
            y_map = y_current + (x_real * math.sin(yaw) + y_real * math.cos(yaw))


            yaw_to_goal = math.atan2(y_map - y_current, x_map - x_current)

            # Convert yaw to quaternion for ROS2 navigation goal
            #yaw_to_goal = math.atan2(y_real, x_real)

            # Convert yaw to quaternion
            quat = tf_transformations.quaternion_from_euler(0, 0, yaw_to_goal)

            #self.rotate_robot(math.degrees(yaw_to_goal))
            # Create and send goal
            goal_msg = NavigateToPose.Goal()
            goal_msg.pose.header.frame_id = "map"
            goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
            goal_msg.pose.pose.position.x = x_map
            goal_msg.pose.pose.position.y = y_map
            goal_msg.pose.pose.orientation.x = quat[0]
            goal_msg.pose.pose.orientation.y = quat[1]
            goal_msg.pose.pose.orientation.z = quat[2]
            goal_msg.pose.pose.orientation.w = quat[3]
            self.mode = "navigating"

            self.get_logger().info(f"Sending TurtleBot to ({x_map:.2f}, {y_map:.2f})m in the map frame")
            self.get_logger().info(f"Robot pose ({x_current:.2f}, {y_current:.2f})")
            send_goal_future = self.nav_client.send_goal_async(goal_msg)
            send_goal_future.add_done_callback(self.goal_response_callback)

        except Exception as e:
            self.get_logger().error(f"Error transforming coordinates: {e}")


    def goal_response_callback(self, future):
        """ Handle goal response and result """
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error("Goal was rejected!")
            self.mode = "search"
            return
        
        self.get_logger().info("Goal accepted!")
        self.current_goal_handle = goal_handle
        get_result_future = goal_handle.get_result_async()
        get_result_future.add_done_callback(self.goal_completed_callback)

    def goal_completed_callback(self, future):
        """ Handle completed navigation goal """
        result = future.result()
        self.get_logger().info("Goal Completed! Ready for next goal.")
        
        # Clear current goal handle so a new goal can be sent
        self.current_goal_handle = None
        self.rotating = False
        self.mode = "search"

def main(map_path, home_zone, args=None):
    #rem_handle = RemoteHandler()
    #rem_handle.start()
    #node = BallDetector(rem_handle, map_path)
    start_navigation_server(map_path)
    node = BallDetector(map_path, home_zone)  
    mode = "off"
    #node.warmup_out()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Keyboard interrupt, shutting down")
    finally:
        node.destroy_node()
        rclpy.shutdown()
    """try:
        while True:
            if mode == "off":
                node.cooldown_out()
                while rem_handle.result is None:
                    pass
                mode = rem_handle.result
                rem_handle.reset()
            elif mode == "on":
                node.warmup_out()
                while rem_handle.result is None:
                    pass
                mode = rem_handle.result
                rem_handle.reset()
            elif mode == "collect":
                node.warmup_out()
                try:
                    rclpy.spin(node)
                except RemotePressError:
                    mode = rem_handle.result
                    rem_handle.reset()
            else:
                raise NotImplementedError("Unimplemented mode called")
            
    except KeyboardInterrupt:
        node.get_logger().info("Keyboard interrupt, shutting down")
    finally:
        node.destroy_node()
        rem_handle.join()
    """