iimport tkinter as tk
from tkinter import filedialog, Canvas, messagebox
from PIL import Image, ImageTk, ImageDraw
import json
import subprocess
import os
import time
from ultralytics import YOLO
import cv2
import numpy as np

class NoGoZoneApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Court Help No-Go Zone Implementation")
        self.root.state("zoomed")
        
        # Create a frame for control buttons on the right side
        self.control_frame = tk.Frame(self.root)
        self.control_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)
        
        self.no_go_button = tk.Button(self.control_frame, text="Draw No-Go Zone", fg="red", command=self.set_no_go_mode)
        self.no_go_button.pack(fill=tk.X, pady=2)
        self.no_go_button.bind("<Enter>", lambda e: self.show_tooltip("Click to draw a no-go zone (red rectangle)."))
        self.no_go_button.bind("<Leave>", lambda e: self.hide_tooltip())
        
        self.home_zone_button = tk.Button(self.control_frame, text="Draw Home Zone", fg="blue", command=self.set_home_zone_mode)
        self.home_zone_button.pack(fill=tk.X, pady=2)
        self.home_zone_button.bind("<Enter>", lambda e: self.show_tooltip("Click to draw a home zone (blue rectangle)."))
        self.home_zone_button.bind("<Leave>", lambda e: self.hide_tooltip())
        
        self.delete_all_button = tk.Button(self.control_frame, text="Delete All Zones", command=self.delete_all_zones)
        self.delete_all_button.pack(fill=tk.X, pady=2)
        self.delete_all_button.bind("<Enter>", lambda e: self.show_tooltip("Click to delete all zones from the map."))
        self.delete_all_button.bind("<Leave>", lambda e: self.hide_tooltip())
        
        self.edit_zone_button = tk.Button(self.control_frame, text="Edit Zones (Move/Resize)", command=self.enable_edit_mode)
        self.edit_zone_button.pack(fill=tk.X, pady=2)
        self.edit_zone_button.bind("<Enter>", lambda e: self.show_tooltip("Click to enable edit mode. Drag to move, resize by dragging edges."))
        self.edit_zone_button.bind("<Leave>", lambda e: self.hide_tooltip())
        
        self.canvas = Canvas(self.root, bg='white')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Create a frame for load and save buttons at the bottom
        self.bottom_frame = tk.Frame(self.root)
        self.bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        
        self.load_map_button = tk.Button(self.bottom_frame, text="Load Map", command=self.load_map)
        self.load_map_button.pack(side=tk.LEFT, padx=5)
        self.load_map_button.bind("<Enter>", lambda e: self.show_tooltip("Click to load a map image."))
        self.load_map_button.bind("<Leave>", lambda e: self.hide_tooltip())
        
        self.save_button = tk.Button(self.bottom_frame, text="Save Map with Zones", command=self.save_map_with_zones)
        self.save_button.pack(side=tk.RIGHT, padx=5)
        self.save_button.bind("<Enter>", lambda e: self.show_tooltip("Click to save the map with added zones."))
        self.save_button.bind("<Leave>", lambda e: self.hide_tooltip())

        self.save_map_button = tk.Button(self.bottom_frame, text="Save Map", command=self.run_ros_package2)
        self.save_map_button.pack(side=tk.RIGHT, padx=5)
        self.save_map_button.bind("<Enter>", lambda e: self.show_tooltip("Click to save the created map."))
        self.save_map_button.bind("<Leave>", lambda e: self.hide_tooltip())

        self.configure_button = tk.Button(self.bottom_frame, text="Configure", command=self.run_ros_pachage)
        self.configure_button.pack(side=tk.RIGHT, padx=5)
        self.configure_button.bind("<Enter>", lambda e: self.show_tooltip("Click to start the robot configuration process."))
        self.configuree_button.bind("<Leave>", lambda e: self.hide_tooltip())

        self.done_button = tk.Button(self.bottom_frame, text="Done", command=self.start_recognsion)
        self.done_button.pack(side=tk.LEFT, padx=5)
        self.done_button.bind("<Enter>", lambda e: self.show_tooltip("Click to start the robot."))
        self.done_button.bind("<Leave>", lambda e: self.hide_tooltip())
        
        self.tooltip = tk.Label(self.root, text="", bg="yellow", fg="black", relief=tk.SOLID, borderwidth=1)
        self.tooltip.pack_forget()
        
        self.rectangles = []  # Stores rectangle objects
        self.no_go_zones = []  # Stores coordinates of no-go zones
        self.home_zone = None  # Stores the home zone center coordinate
        self.home_rectangle = None  # Stores the home zone rectangle object
        
        self.start_x = None
        self.start_y = None
        self.rect = None
        self.map_image = None
        self.tk_map = None
        self.mode = "no_go"
        self.selected_rectangle = None
        self.selected_corner = None
        self.edit_mode = False
        self.dragging = False
        self.resizing = False
        
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<ButtonPress-3>", self.on_right_click)  # Right-click to delete zones
        self.canvas.bind("<Motion>", self.on_motion)  # Detect hovering over corners

    def show_warning(self, message):
        """ Show a warning popup with an 'OK' button. """
        messagebox.showwarning("Warning", message)

    def check_map_loaded(self):
        """ Check if a map is loaded before allowing actions. """
        if self.map_image is None:
            self.show_warning("Please load a map before performing this action.")
            return False
        return True

    def show_tooltip(self, text):
        self.tooltip.config(text=text)
        self.tooltip.place(x=10, y=10)
    
    def hide_tooltip(self):
        self.tooltip.place_forget()
        
    def set_no_go_mode(self):
        if not self.check_map_loaded():
            return
        self.mode = "no_go"
        self.edit_mode = False
        
    def set_home_zone_mode(self):
        if not self.check_map_loaded():
            return
        self.mode = "home"
        self.edit_mode = False
        
    def enable_edit_mode(self):
        if not self.check_map_loaded():
            return
        self.edit_mode = True
    
    def delete_all_zones(self):
        if not self.check_map_loaded():
            return
        for rect in self.rectangles:
            self.canvas.delete(rect)
        self.rectangles.clear()
        self.no_go_zones.clear()
        if self.home_rectangle:
            self.canvas.delete(self.home_rectangle)
            self.home_rectangle = None
            self.home_zone = None
        
    def load_map(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.bmp;*.pgm")])
        if file_path:
            self.map_image = Image.open(file_path)
            self.map_image = self.map_image.resize((self.canvas.winfo_width(), self.canvas.winfo_height()))
            self.tk_map = ImageTk.PhotoImage(self.map_image)
            self.canvas.create_image(self.canvas.winfo_width() // 2, self.canvas.winfo_height() // 2, anchor=tk.CENTER, image=self.tk_map)

        
    def on_motion(self, event):
        for rect in self.rectangles:
            x1, y1, x2, y2 = self.canvas.coords(rect)
            if abs(event.x - x1) < 5 or abs(event.x - x2) < 5 or abs(event.y - y1) < 5 or abs(event.y - y2) < 5:
                self.canvas.config(cursor="plus")  # Resize cursor
                return
            elif x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self.canvas.config(cursor="fleur")  # Move cursor
                return
        self.canvas.config(cursor="")
        
    def on_press(self, event):
        if not self.check_map_loaded():
            return
        if self.edit_mode:
            for rect in reversed(self.rectangles):
                x1, y1, x2, y2 = self.canvas.coords(rect)
                if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                    self.selected_rectangle = rect
                    self.start_x, self.start_y = event.x, event.y
                    self.dragging = True
                    return
        else:
            if self.mode == "no_go":
                self.start_x, self.start_y = event.x, event.y
                rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, fill="black", outline="black")
                self.rectangles.append(rect)
                self.no_go_zones.append((self.start_x, self.start_y, self.start_x, self.start_y))
            elif self.mode == "home":
                if self.home_rectangle:
                    self.canvas.delete(self.home_rectangle)
                self.home_zone = (event.x, event.y)
                self.home_rectangle = self.canvas.create_oval(event.x-10, event.y-10, event.x+10, event.y+10, fill="blue", outline="blue")

    def on_drag(self, event):
        if self.edit_mode and self.selected_rectangle:
            x1, y1, x2, y2 = self.canvas.coords(self.selected_rectangle)
            if self.resizing:
                self.canvas.coords(self.selected_rectangle, x1, y1, event.x, event.y)
            elif self.dragging:
                step_x = event.x - self.start_x
                step_y = event.y - self.start_y
                self.canvas.move(self.selected_rectangle, step_x, step_y)
                self.start_x = event.x
                self.start_y = event.y
        elif not self.edit_mode and self.mode == "no_go":
            self.canvas.coords(self.rectangles[-1], self.start_x, self.start_y, event.x, event.y)
        
    def on_release(self, event):
        self.selected_rectangle = None
        self.dragging = False
        
    def on_right_click(self, event):
        for rect in self.rectangles:
            x1, y1, x2, y2 = self.canvas.coords(rect)
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self.canvas.delete(rect)
                self.rectangles.remove(rect)
                self.no_go_zones.remove((x1, y1, x2, y2))
                return
        
    def save_map_with_zones(self):
        if not self.check_map_loaded():
            return
        
        if not self.rectangles and self.home_zone is None:
            self.show_warning("No changes have been made to the map. Add at least one zone before saving.")
            return
        
        annotated_map = self.map_image.copy()
        draw = ImageDraw.Draw(annotated_map)
        
        for rect in self.rectangles:
            x1, y1, x2, y2 = self.canvas.coords(rect)
            draw.rectangle([x1, y1, x2, y2], fill="black", outline="black")
        
        if self.home_zone:
            x, y = self.home_zone
            draw.ellipse([x-10, y-10, x+10, y+10], fill="blue", outline="blue")
        
        file_path = filedialog.asksaveasfilename(defaultextension=".pgm", filetypes=[("PGM Files", "*.pgm")])
        if file_path:
            annotated_map.save(file_path)
        
        # Generate YAML file
        yaml_content = f"""image: {file_path}
resolution: 0.05
origin: [0.0, 0.0, 0.0]
occupied_thresh: 0.65
free_thresh: 0.196
negate: 0
"""
        yaml_path = file_path.replace(".pgm", ".yaml")
        with open(yaml_path, "w") as yaml_file:
            yaml_file.write(yaml_content)
        print("Map and YAML file saved.")

    def run_ros_package(self):
        try:
            subprocess.Popen(['xterm', '-e', 'ros2', 'run', 'turtlebot3_teleop', 'teleop_keyboard'])

            subprocess.Popen(["xterm", "-e", "ros2", "launch", "turtlebot3_cartographer", "cartographer.launch.py"])

        except subprocess.CalledProcessError as e:
            print("Error running ROS package:", e)


    def run_ros_package2(self):
        try:
            print("Checking if ROS map server is ready...")
            time.sleep(5)
            save_path = os.path.expanduser("~/map")
            subprocess.run(["xterm", "-e", "ros2", "run", "nav2_map_server", "map_saver_cli", "-f", save_path], check=True)
        except subprocess.CalledProcessError as e:
            print("Error running ROS package:", e)

    def start_recognision(self):
        try:
            model = YOLO('yolov9e-seg.pt')  # Path to YOLO model
        except Exception as e:
            print(f"Error loading YOLO: {e}")
            return

        cap = cv2.VideoCapture(0)
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

        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    root = tk.Tk()
    app = NoGoZoneApp(root)
    root.mainloop()
