from ultralytics import YOLO
import cv2
import numpy as np
import math
import time  # 添加时间控制

try:
    model = YOLO('yolo11s.pt')
except Exception as e:
    print(f"Error loading YOLO: {e}")
    exit()

cap = cv2.VideoCapture(1)

cv2.namedWindow("Ball Detection", cv2.WINDOW_NORMAL)
cv2.setWindowProperty("Ball Detection", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

FOCAL_LENGTH = 870
REAL_DIAMETER = 0.040
CAMERA_HEIGHT = 0.13  # Height from the ground
CAMERA_FORWARD = 0.15  # Distance from robot lidar

TARGET_FPS = 60
FRAME_INTERVAL = 1.0 / TARGET_FPS

def calculate_distance(focal_length, real_diameter, pixel_size):
    if pixel_size <= 0:
        return None
    return (focal_length * real_diameter) / pixel_size

def calculate_robot_position(x_center, y_center, pixel_size, frame_width, frame_height):
    Z_cam = (FOCAL_LENGTH * REAL_DIAMETER) / pixel_size  

    C_X, C_Y = frame_width // 2, frame_height // 2
    X_cam = ((x_center - C_X) * Z_cam) / FOCAL_LENGTH  

    X_robot = Z_cam - CAMERA_FORWARD
    Y_robot = X_cam
    Z_robot = CAMERA_HEIGHT  

    yaw_angle = math.degrees(math.atan2(X_cam, Z_cam))

    return X_robot, Y_robot, Z_robot, yaw_angle

def calculate_xy(z, theta_degrees):
    theta_radians = np.radians(theta_degrees)
    x = z * np.cos(theta_radians)
    y = z * np.sin(theta_radians)
    return x, y

last_frame_time = time.time()

while True:
    current_time = time.time()
    
    if current_time - last_frame_time < FRAME_INTERVAL:
        continue
    
    last_frame_time = current_time

    ret, frame = cap.read()
    if not ret:
        print("Error: Cannot read frame from camera")
        break

    frame_width, frame_height = frame.shape[1], frame.shape[0]

    results = model(frame)
    detections = results[0]

    detected_balls = []

    for box in detections.boxes:
        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
        confidence = box.conf[0].item()
        class_id = int(box.cls[0].item())
        class_name = detections.names[class_id]

        if class_name in ["orange", "sports ball"]:
            detected_balls.append((x1, y1, x2, y2, confidence))

    for (x1, y1, x2, y2, confidence) in detected_balls:
        x_center, y_center = (x1 + x2) // 2, (y1 + y2) // 2
        box_width = x2 - x1
        box_height = y2 - y1

        aspect_ratio = box_width / box_height
        is_valid_ratio = 0.7 <= aspect_ratio <= 1.3

        yaw_angle = math.degrees(math.atan2((x_center - frame_width // 2), FOCAL_LENGTH))

        if is_valid_ratio:
            pixel_size = max(box_width, box_height)
            Z = calculate_distance(FOCAL_LENGTH, REAL_DIAMETER, pixel_size)

            X_robot, Y_robot, Z_robot, _ = calculate_robot_position(
                x_center, y_center, pixel_size, frame_width, frame_height
            )

            X, Y = calculate_xy(Z, yaw_angle)

            # print in terminal
            print(f"Ball detected at: X={X:.3f}m, Y={Y:.3f}m, Z={Z:.3f}m, Angle={yaw_angle:.1f} Degree, Confidence={confidence:.1f}")

            # Label for display
            label = f"Distance:{Z:.2f}m, Angle:{yaw_angle:.1f}, Confidence:{confidence:.1f}"
        else:
            Z = None
            print(f"Ball detected (abnormal aspect ratio): Z unknown, Angle={yaw_angle:.1f} Degree, Confidence={confidence:.1f}")

            label = f"Angle: {yaw_angle:.1f} Degree, Z unknown"

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    cv2.imshow("Ball Detection", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
