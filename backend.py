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
import tf2_ros
import tf2_geometry_msgs
from geometry_msgs.msg import PoseWithCovarianceStamped
from std_msgs.msg import String
from geometry_msgs.msg import Twist
import remconsub
map_filename = None
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy



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


def run_ros_package():
    """triggers SLAM and the motions"""
    try:
        #subprocess.Popen([shutil.which('xterm'), '-e', 'ros2', 'run', 'turtlebot3_teleop', 'teleop_keyboard'])

        subprocess.Popen([shutil.which('xterm'), "-e", "ros2", "launch", "turtlebot3_cartographer", "cartographer.launch.py"],
                         stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL, start_new_session=True)

    except subprocess.CalledProcessError as e:
        print("Error running ROS package:", e)


def run_ros_package2(save_path):
    """saves map in current directory and closes stuff"""
    try:
        print("Checking if ROS map server is ready...")
        time.sleep(5)
        #save_path = os.path.expanduser("~/map")
        subprocess.run([shutil.which('xterm'), "-e", "ros2", "run", "nav2_map_server", "map_saver_cli", "-f", save_path],
                         stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL, check=True)
    except subprocess.CalledProcessError as e:
        print("Error running ROS package:", e)


def start_navigation_server(map_path):
    print(map_path)
    """ Starts the TurtleBot3 Navigation Server with a specific map using subprocess. """
    try:
        subprocess.Popen(
                [shutil.which('xterm'), '-e', 'ros2', 'launch', 'nav2_bringup', 'localization_launch.py',
                'map:=map1.yaml']
                )
        time.sleep(5)
        subprocess.Popen(
                [shutil.which('xterm'), '-e', 'ros2', 'launch', 'turtlebot3_navigation2', 'navigation2.launch.py',
                'map:=map1.yaml', 'use_sim_time:=False']
            )
        # Wait before setting initial pose
        time.sleep(5)

        # Set Initial Pose Automatically
        subprocess.Popen([
            shutil.which('xterm'), '-e', 'python3', 'initial_pose.py'
        ])

    except Exception as e:
        print(f"Error starting Navigation Server: {e}")

class BallDetector(Node):
    def __init__(self, map_path):   #self, remhandle, map_path
        super().__init__('ball_detector')
        #self.remhandle = remhandle
        #start_navigation_server(map_path)
        # Subscribe to TurtleBot's camera feed
        self.current_goal_handle = None
        
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
            print('Hi')
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")

            # Process frame with YOLO
            results = self.model(frame, device="cpu")
            detections = results[0]

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
                for (x1, y1, x2, y2, confidence) in detected_balls:
                    x_center, y_center = (x1 + x2) // 2, (y1 + y2) // 2
                    box_width = x2 - x1
                    box_height = y2 - y1

                    aspect_ratio = box_width / box_height
                    is_valid_ratio = 0.7 <= aspect_ratio <= 1.3

                    yaw_angle = math.degrees(math.atan2((x_center - CX), self.FOCAL_LENGTH))

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
                        break  
            else:
                if not self.rotating:  # **Ensure only one rotation at a time**
                    self.rotating = True  
                    self.create_timer(5.0, self.rotate_and_reset)  

            cv2.imshow("Ball Detection", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.get_logger().info("Exiting camera stream...")
                rclpy.shutdown()
            #if self.remhandle.result is not None:
                #raise RemotePressError()
            

        except Exception as e:
            self.get_logger().error(f"Error processing image: {e}")

    def rotate_robot(self, degrees):
        """ Rotate the TurtleBot by a given angle (in degrees). """
        twist_msg = Twist()
        angular_speed = 0.07  # Adjust rotation speed
        duration = abs(degrees) / 20  # 10 degrees per second

        twist_msg.angular.z = angular_speed if degrees > 0 else -angular_speed
        self.vel_publisher.publish(twist_msg)

        self.get_logger().info(f"Rotating {degrees} degrees...")
        time.sleep(duration)

        # Stop rotation
        twist_msg.angular.z = 0.0
        self.vel_publisher.publish(twist_msg)

    def rotate_and_reset(self):
        """ Rotate the robot and then reset the flag after 5 seconds. """
        self.rotate_robot(10)
        self.create_timer(5.0, self.reset_rotation_flag)

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

    def send_navigation_goal(self, x_real, y_real):
        """ Sends goal coordinates to TurtleBot for navigation. """

        """goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = "map"
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = x_real
        goal_msg.pose.pose.position.y = y_real
        goal_msg.pose.pose.orientation.w = 1.0  

        self.get_logger().info(f"Sending TurtleBot to ({x_real:.2f}, {y_real:.2f})m")
        self.nav_client.send_goal_async(goal_msg)"""

        try:

            if self.current_pose is None:
                self.get_logger().warn("Waiting for AMCL pose...")
                for _ in range(60):  # Try for 10 seconds
                    rclpy.spin_once(self, timeout_sec=1.0)
                    #if self.current_pose is not None:
                        #break
                
                if self.current_pose is None:
                    self.get_logger().error("AMCL pose not received after timeout, cannot calculate goal.")
                    return
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

            # Create and send goal
            goal_msg = NavigateToPose.Goal()
            goal_msg.pose.header.frame_id = "map"
            goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
            goal_msg.pose.pose.position.x = x_map
            goal_msg.pose.pose.position.y = y_map
            goal_msg.pose.pose.orientation.w = 1.0  

            self.get_logger().info(f"Sending TurtleBot to ({x_map:.2f}, {y_map:.2f})m in the map frame")
            self.get_logger().info(f"Robot pose ({x_current:.2f}, {y_current:.2f})")
            self.nav_client.send_goal_async(goal_msg)
            send_goal_future = self.nav_client.send_goal_async(goal_msg)
            send_goal_future.add_done_callback(self.goal_response_callback)

        except Exception as e:
            self.get_logger().error(f"Error transforming coordinates: {e}")


    def goal_response_callback(self, future):
        """ Handle goal response and result """
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error("Goal was rejected!")
            return
        
        self.get_logger().info("Goal accepted!")
        self.current_goal_handle = goal_handle
        
        # Wait for completion
        get_result_future = goal_handle.get_result_async()
        get_result_future.add_done_callback(self.goal_completed_callback)

    def goal_completed_callback(self, future):
        """ Handle completed navigation goal """
        result = future.result()
        self.get_logger().info("Goal Completed! Ready for next goal.")
        
        # Clear current goal handle so a new goal can be sent
        self.current_goal_handle = None

def main(map_path, args=None):
    #rem_handle = RemoteHandler()
    #rem_handle.start()
    #node = BallDetector(rem_handle, map_path)
    start_navigation_server(map_path)
    node = BallDetector(map_path)    
    mode = "off"
    #node.warmup_out()
    rclpy.spin(node)
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
