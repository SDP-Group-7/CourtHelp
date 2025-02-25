from ultralytics import YOLO
import subprocess
import os
import time
import cv2
import numpy as np


class VideoCaptureObj:
    """Context manager, used to guarantee that cap gets released"""
    def __enter__(self):
        self.cap = cv2.VideoCapture(0)
        return self.cap

    def __exit__(self):
        cap.release()
        cv2.destroyAllWindows()


def run_ros_package():
    try:
        subprocess.Popen(['xterm', '-e', 'ros2', 'run', 'turtlebot3_teleop', 'teleop_keyboard'])

        subprocess.Popen(["xterm", "-e", "ros2", "launch", "turtlebot3_cartographer", "cartographer.launch.py"])

    except subprocess.CalledProcessError as e:
        print("Error running ROS package:", e)


def run_ros_package2():
    try:
        print("Checking if ROS map server is ready...")
        time.sleep(5)
        save_path = os.path.expanduser("~/map")
        subprocess.run(["xterm", "-e", "ros2", "run", "nav2_map_server", "map_saver_cli", "-f", save_path], check=True)
    except subprocess.CalledProcessError as e:
        print("Error running ROS package:", e)



def start_recognition(self):
    try:
        model = YOLO('yolov9e-seg.pt')  # Path to YOLO model
    except Exception as e:
        print(f"Error loading YOLO: {e}")
        print()
        print()
        raise

    with VideoCaptureObj() as cap:
        FOCAL_LENGTH = 800  # Focal length in pixels (requires camera calibration)
        REAL_DIAMETER = 0.040  # Real world diameter in meters
        previous_position = None

        def calculate_distance(focal_length, real_diameter, pixel_height):
            if pixel_height <= 0:
                return None
            return (focal_length * real_diameter) / pixel_height

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            CX, CY = frame.shape[1] // 2, frame.shape[0] // 2
            results = model(frame)
            detections = results[0]
            TARGET_CLASS_ID = 32
            filtered_boxes = []

            for box in detections.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                confidence = box.conf[0].item()
                class_id = int(box.cls[0].item())

                if class_id == TARGET_CLASS_ID and confidence > 0.4:
                    filtered_boxes.append((x1, y1, x2, y2, confidence))

            for (x1, y1, x2, y2, confidence) in filtered_boxes:
                x_center, y_center = (x1 + x2) // 2, (y1 + y2) // 2
                pixel_height = y2 - y1
                Z = calculate_distance(FOCAL_LENGTH, REAL_DIAMETER, pixel_height)
                X_real = ((x_center - CX) * Z) / FOCAL_LENGTH
                Y_real = ((y_center - CY) * Z) / FOCAL_LENGTH

                if previous_position is not None:
                    dx = X_real - previous_position[0]
                    dy = Y_real - previous_position[1]
                    dz = Z - previous_position[2]

                    theta_xy = np.arctan2(dy, dx)
                    theta_xz = np.arctan2(dz, dx)

                    print(f"Movement direction: θ_xy={np.degrees(theta_xy):.2f}°, θ_xz={np.degrees(theta_xz):.2f}°")

                previous_position = (X_real, Y_real, Z)
                label = f"Ball: {confidence:.2f}, {Z:.2f}m"
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            cv2.imshow("Ball Detection (Live)", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break


if __name__ == "__main__":
    print("no!")
    raise Exception
