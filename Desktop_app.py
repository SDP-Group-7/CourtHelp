import tkinter as tk
import tkinter.ttk as ttk
from tkinter import filedialog, Canvas, messagebox
from PIL import Image, ImageTk, ImageDraw
import backend
import os
import subprocess
import rclpy
from std_msgs.msg import String
import glob
from PIL import ImageOps
import math
from tkinter import filedialog

PANEL_BG="#14213d"
class NoGoZoneApp:
    def __init__(self, root):
        self.root = root
        self.teleop_process = None
        self.root.title("Setting up your CourtHelp robot")
        self.root.state("normal")
        self.control_box_frame = None
        self.preview_frame = None
        self.back_button = None
        self.in_preview_mode = False
        self.linear_speed_level = 0  # Ranges 0-5
        self.angular_speed_level = 0  # Ranges 0-5
        self.MAX_SPEED_LEVEL = 5
        self.current_polygon_points = []
        self.current_polygon_lines = []
        self.no_go_polygons = []
        self.current_shape = []
        self.selected_shape = None

        # for the teleop in desktop
        rclpy.init()
        self.ros_node = rclpy.create_node('teleop_gui')
        self.command_publisher = self.ros_node.create_publisher(String, 'teleop_commands', 10)
        self.status_subscriber = self.ros_node.create_subscription(
            String,
            'teleop_status',
            self.update_status_label,
            10
        )

        # Create a frame for control buttons on the left side
        self.control_frame = tk.Frame(self.root, bg=PANEL_BG)
        self.control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=20, pady=20, ipadx=20, ipady=20)
        button_panel_title = tk.Label(self.control_frame, text="Setting up your robot", bg="yellow", fg="black", relief=tk.FLAT, borderwidth=1, font=('TkDefaultFont', 15))
        button_panel_title.pack(fill=tk.X, pady=5,)

        # Inside __init__ just after creating self.canvas
        self.control_box_frame = tk.Frame(self.root, bg="#EAEAEA", bd=2, relief=tk.RIDGE)
        self.control_box_frame.place(relx=1.0, rely=1.0, anchor="se", x=-60, y=-10, width=280, height=180)
        self.control_box_frame.pack_propagate(False)
        self.control_box_frame.lower()  # Hide it initially

        #for the preview icon
        self.map_preview_frame = tk.Frame(self.root, bg="white")
        self.map_preview_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.custom_step_label(self.control_frame,"Step 1: Configure the Robot")
        self.configure_button = self.custom_button(self.control_frame, text="Configure", command=self.configure_robot, tooltip="Start robot configuration, move the robot using the keys below until you are satisfied with the area it overed. If you already have a map you may skip this step.")

        # Frame for the control buttons
        self.control_box_frame = tk.Frame(self.control_frame, bg=PANEL_BG)
        self.control_box_frame.pack(pady=(10, 10), padx=5)
        self.arrow_font = ('TkDefaultFont', 18, 'bold')

        self.up_button = tk.Button(self.control_box_frame, text="↑", width=4, font=self.arrow_font, command=lambda: self.send_command('forward'))
        self.up_button.grid(row=0, column=1, padx=8, pady=8)

        self.left_button = tk.Button(self.control_box_frame, text="←", width=4, font=self.arrow_font, command=lambda: self.send_command('left'))
        self.left_button.grid(row=1, column=0, padx=8, pady=8)

        self.stop_button = tk.Button(self.control_box_frame, text="STOP", width=4, font=self.arrow_font, command=lambda: self.send_command('stop'))
        self.stop_button.grid(row=1, column=1, padx=8, pady=8)

        self.right_button = tk.Button(self.control_box_frame, text="→", width=4, font=self.arrow_font, command=lambda: self.send_command('right'))
        self.right_button.grid(row=1, column=2, padx=8, pady=8)

        self.down_button = tk.Button(self.control_box_frame, text="↓", width=4, font=self.arrow_font, command=lambda: self.send_command('backward'))
        self.down_button.grid(row=2, column=1, padx=8, pady=8)

        self.status_label = tk.Label(
            self.control_frame,
            text="Speed: 0 | Direction: Stopped",
            fg="white",
            bg=PANEL_BG,
            font=('TkDefaultFont', 12)
        )
        self.status_label = tk.Label(
            self.control_frame,
            fg="white",
            bg=PANEL_BG,
            font=('TkDefaultFont', 12)
        )
        self.set_control_buttons_state("disabled")

        self.canvas = Canvas(self.root, bg='white')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.status_label.pack(fill=tk.X, pady=(10, 5), padx=5)
        self.save_map_button = self.custom_button(self.control_frame, text="Finish Configuration", command=self.finish_configuration, tooltip="Save the map created by the robot")

        self.custom_step_label(self.control_frame, "Step 2: Load Map")
        self.load_map_button = self.custom_button(self.control_frame, text="Load Map", command=self.load_maps, tooltip="This is bring up a browser of all your pgm maps where you can preview them and chose to edit. You may use the back button to go back from editing to the browser")

        self.custom_step_label(self.control_frame,"Step 3: Mark Map")
        self.no_go_button= self.custom_button(self.control_frame, text="Draw No-Go Zone",command=self.set_no_go_mode, tooltip="Click on the map to create a starting point and the subsequent ones too, the shape will automatically be created once the points overlap. Right click a the zone to delete.\n A No-Go Zone is an area the robot is forbidden from entering such as the benches for players, an open door or other obstacles too high or low for the LIDAR sensor to detect.")
        self.home_zone_button = self.custom_button(self.control_frame, text="Draw Home Zone", command=self.set_home_zone_mode, tooltip="Click position to place a Home zone (blue circle). The robot returns to the home zone after collecting all balls. There must be exactly 1 home zone in the map and shall not overlap with no-go zones.") 
        self.delete_all_button = self.custom_button(self.control_frame, text="Delete All Zones", command=self.delete_all_zones, tooltip="Click to delete all No-Go and Home zones from the map.")
        self.edit_zone_button = self.custom_button(self.control_frame, text="Edit Zones (Move/Resize)", command=self.enable_edit_mode, tooltip="Click to enable edit mode. Drag center of No-Go or Home zones to move them and drag their corners for resizing.")
        
        self.custom_step_label(self.control_frame,"Step 4: Save Map")
        self.save_button = self.custom_button(self.control_frame, text="Save Map with Zones", command=self.save_map_with_zones, tooltip="Save your map with added zones.")

        self.custom_step_label(self.control_frame,"Step 5: Start the Robot")
        self.done_button = self.custom_button(self.control_frame, text="Done", command=self.start_robot, tooltip="Start the robot's function")
        
        # Create bottom border
        self.bottom_frame = tk.Frame(self.root)
        self.bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        
        self.tooltip = tk.Label(self.root, text="", bg="yellow", fg="black", relief=tk.SOLID, borderwidth=1, font=('TkDefaultFont', 11))
        self.tooltip.pack_forget()
        
        self.rectangles = []  # Stores rectangle objects
        self.no_go_zones = []  # Stores coordinates of no-go zones
        self.home_zone = None  # Stores the home zone center coordinate
        self.home_rectangle = None  # Stores the home zone rectangle objectself.current_polygon = []
        self.no_go_polygons = []
        
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
        self.cursor_mode="arrow"
        self.canvas.config(cursor=self.cursor_mode)
        
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<ButtonPress-3>", self.on_right_click)
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<B1-Motion>", self.handle_drag_or_draw)

        self.root.after(100, self.ros_spin)

    def custom_button(self, control_frame, text, command, tooltip):
        button = ttk.Button(master=control_frame,
                        text=text,
                        command=command,
                        style='standard.TButton'
                        )
        button.pack(fill=tk.BOTH, ipady=5, pady=3, padx=10)
        button.bind("<Enter>", lambda e: self.show_tooltip(e, tooltip))
        button.bind("<Leave>", lambda e: self.hide_tooltip())
        return button
    
    #set control button state
    def set_control_buttons_state(self, state):
        self.up_button.config(state=state)
        self.left_button.config(state=state)
        self.stop_button.config(state=state)
        self.right_button.config(state=state)
        self.down_button.config(state=state)

    def start_robot(self):
        map_path = filedialog.askopenfilename(
            title="Select Map YAML File",
            filetypes=[("YAML Files", "*.yaml")]
        )
        if map_path:
            backend.main(map_path)
        else:
            self.show_warning("No map selected. Please select a map to start the robot.")

    def handle_drag_or_draw(self, event):
        if self.edit_mode:
            self.on_drag(event)
        elif self.mode == "no_go":
            self.draw_line(event)

    
    def ros_spin(self):
        rclpy.spin_once(self.ros_node, timeout_sec=0.1)
        self.root.after(100, self.ros_spin)
    
    def update_status_label(self, msg):
        self.status_label.config(text=msg.data)
    
    def custom_step_label(self, control_frame, msg):
        step1 = tk.Label(control_frame, text=msg, anchor="w", fg="white",bg=PANEL_BG, relief=tk.FLAT, borderwidth=1, font=('TkDefaultFont', 13))
        step1.pack(fill=tk.X, pady=5, padx=2)

    def send_command(self, command):
        msg = String()
        msg.data = command
        self.command_publisher.publish(msg)
        print(f"Sent command: {command}")

    #start listening to keys for robot movement 
    def start_teleop_listener(self):
        if self.teleop_process is None:
            self.teleop_process = subprocess.Popen(['python3', 'teleop_listener.py'])
            print("Teleop listener started.")
        else:
            print("Teleop listener is already running.")

    def stop_teleop_listener(self):
        if self.teleop_process:
            self.teleop_process.terminate()
            self.teleop_process = None
            print("Teleop listener stopped.")

    def configure_robot(self):
        self.start_teleop_listener()
        self.set_control_buttons_state("normal")
        backend.run_ros_package()

    def finish_configuration(self):
        # Ask user for save location and filename
        file_path = filedialog.asksaveasfilename(
            defaultextension=".yaml",
            filetypes=[("YAML Files", "*.yaml")],
            title="Save Map As"
        )

        if not file_path:
            print("Save canceled.")
            return  # User canceled the save dialog

        # Remove .yaml extension if present (map saver adds its own extensions)
        save_path = file_path.replace(".yaml", "")
        backend.run_ros_package2(save_path)
        self.set_control_buttons_state("disabled")

    def is_inside_no_go_polygon(self, x, y):
        """ Check if a point (x, y) is inside any no-go zone. """
        for polygon in self.no_go_polygons:
            if self.canvas.find_overlapping(x, y, x, y).__contains__(polygon):
                return True
        return False

    def hide_control_box(self):
        if self.control_box:
            self.control_box.destroy()
            self.control_box = None

    def check_no_go_zone_overlap(self, x1, y1, x2, y2):
        """ Check if a no-go zone overlaps with the home zone. """
        if self.home_zone:
            hx, hy = self.home_zone
            if x1 <= hx <= x2 and y1 <= hy <= y2:
                return True
        return False

    def show_warning(self, message):
        """ Show a warning popup with an 'OK' button. """
        messagebox.showwarning("Warning", message)

    def check_map_loaded(self):
        """ Check if a map is loaded before allowing actions. """
        if self.in_preview_mode:
            return False  # Don't block actions in preview mode
        if self.map_image is None:
            self.show_warning("Please load a map before performing this action.")
            return False
        return True

    def show_tooltip(self, event, text):
        widget = event.widget
        x = widget.winfo_rootx() - self.root.winfo_rootx() + widget.winfo_width() + 10
        y = widget.winfo_rooty() - self.root.winfo_rooty()

        self.tooltip.config(text=text)
        self.tooltip.place(x=x, y=y)
    
    def hide_tooltip(self):
        self.tooltip.place_forget()
        
    def set_no_go_mode(self):
        if not self.check_map_loaded():
            return
        self.mode = "no_go"
        self.edit_mode = False
        self.cursor_mode = "cross"
        self.canvas.config(cursor=self.cursor_mode)
        self.current_polygon_points = []
        self.current_polygon_lines = []

    def finish_no_go_zone(self):
        if len(self.current_polygon_points) < 3:
            self.show_warning("A no-go zone needs at least 3 points.")
            return

        # Create the filled polygon
        polygon = self.canvas.create_polygon(
            self.current_polygon_points, fill="black", outline="black"
        )
        self.no_go_zones.append(polygon)
        
        # Reset the mode
        self.mode = None
        self.cursor_mode = "arrow"
        self.canvas.config(cursor=self.cursor_mode)
        self.current_polygon_points = []
        
        # Remove the finish button
        if hasattr(self, 'finish_polygon_button'):
            self.finish_polygon_button.pack_forget()

    def start_drawing(self, event):
        if self.mode != "no_go":
            return
        self.current_shape.append((event.x, event.y))

    def draw_line(self, event):
        if self.mode != "no_go" or not self.current_shape:
            return
        last_point = self.current_shape[-1]
        line = self.canvas.create_line(last_point[0], last_point[1], event.x, event.y, fill="black", width=2)
        self.current_lines.append(line)
        self.current_shape.append((event.x, event.y))
    
    def end_drawing(self, event):
        if len(self.current_shape) < 3:
            return
        first_x, first_y = self.current_shape[0]
        last_x, last_y = self.current_shape[-1]
        if abs(first_x - last_x) < 10 and abs(first_y - last_y) < 10:
            self.fill_no_go_zone()
        if self.is_polygon_closed():
            self.fill_no_go_zone()
            self.current_shape = []  # Reset for new zone
    
    def fill_no_go_zone(self):
        polygon = self.canvas.create_polygon(self.current_shape, fill="black", outline="black")
        self.no_go_polygons.append(polygon)
        for line in self.current_lines:
            self.canvas.delete(line)
        self.current_shape = []
        self.current_lines = []

    def finish_polygon(self):
        if self.home_zone and self.is_polygon_over_home_zone(self.current_polygon_points):
            self.show_warning("Cannot place a No-Go Zone over the Home Zone.")
            self.clear_current_polygon()  # Delete all drawn lines
            return

        polygon = self.canvas.create_polygon(
            self.current_polygon_points, fill="black", outline="black"
        )
        self.no_go_polygons.append(polygon)

        self.clear_current_polygon()
        self.mode = "no_go"
        self.canvas.config(cursor="cross")
        
    def set_home_zone_mode(self):
        if not self.check_map_loaded():
            return
        self.mode = "home"
        self.edit_mode = False
        self.cursor_mode = "circle"
        
    def enable_edit_mode(self):
        if not self.check_map_loaded():
            return
        self.edit_mode = True
        self.cursor_mode = "arrow"
    
    def delete_all_zones(self):
        if not self.check_map_loaded():
            return
        for polygon in self.no_go_polygons:
            self.canvas.delete(polygon)
        self.no_go_polygons.clear()
        if self.home_rectangle:
            self.canvas.delete(self.home_rectangle)
            self.home_rectangle = None
            self.home_zone = None
        self.cursor_mode = "arrow"
        self.canvas.config(cursor=self.cursor_mode)
        
    def load_maps(self):
        self.clear_preview_frame()
        self.map_image = None  # Prevent drawing in canvas during preview
        self.mode = None
        self.edit_mode = False
        self.cursor_mode = "arrow"
        self.canvas.config(cursor=self.cursor_mode)
        
        map_directory = "./"
        pgm_files = [f for f in os.listdir(map_directory) if f.endswith(".pgm")]
        if not pgm_files:
            tk.Label(self.map_preview_frame, text="No maps found.").pack()
            return

        for pgm_file in pgm_files:
            frame = tk.Frame(self.map_preview_frame, bd=1, relief=tk.RAISED)
            frame.pack(padx=5, pady=5, fill=tk.X)
            tk.Label(frame, text=pgm_file).pack(side=tk.LEFT, padx=5)
            tk.Button(frame, text="Preview", command=lambda f=pgm_file: self.show_map_preview(f)).pack(side=tk.RIGHT, padx=5)

    def show_map_preview(self, filename):
        self.in_preview_mode = True
        self.reset_editing_state()
        self.clear_preview_frame()
        map_path = os.path.join("./", filename)
        img = Image.open(map_path)
        img.thumbnail((400, 400))
        self.tk_map = ImageTk.PhotoImage(img)

        tk.Label(self.map_preview_frame, image=self.tk_map).pack(pady=10)
        tk.Button(self.map_preview_frame, text="Edit", command=lambda: self.edit_map(map_path)).pack(side=tk.LEFT, padx=10)
        tk.Button(self.map_preview_frame, text="Back", command=self.load_maps).pack(side=tk.RIGHT, padx=10)

    def edit_map(self, map_path):
        self.in_preview_mode = False
        # Hide and clear the preview frame
        self.clear_preview_frame()
        self.map_preview_frame.pack_forget()

        # Remove any existing back button
        if self.back_button:
            self.back_button.destroy()

        # Load and save the map
        self.map_image = Image.open(map_path)
        self.original_map_size = self.map_image.size

        # Force the canvas to update its size
        self.canvas.update_idletasks()
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        # Resize the map to fit the canvas
        resized_map = self.map_image.resize((canvas_width, canvas_height), Image.ANTIALIAS)
        self.tk_map = ImageTk.PhotoImage(resized_map)

        # Clear previous canvas content and display the map
        self.canvas.delete("all")
        self.canvas.create_image(canvas_width // 2, canvas_height // 2, image=self.tk_map, anchor=tk.CENTER)

        # Add back button ON the canvas, floating at top-left
        self.back_button = tk.Button(self.canvas, text="← Back", command=self.back_to_map_selection)
        self.canvas.create_window(10, 10, anchor="nw", window=self.back_button)

    def back_to_map_selection(self):
        # Clear the canvas
        self.canvas.delete("all")

        # Destroy the back button if it exists
        if self.back_button:
            self.back_button.destroy()
            self.back_button = None

        # Restore the map preview frame
        self.map_preview_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.load_maps()

    def clear_preview_frame(self):
        for widget in self.map_preview_frame.winfo_children():
            widget.destroy()

    def reset_editing_state(self):
        self.delete_all_zones()
        self.canvas.delete("all")
        self.map_image = None
        self.tk_map = None
        self.mode = None
        self.edit_mode = False
        self.cursor_mode = "arrow"
        self.canvas.config(cursor=self.cursor_mode)
        
    def on_motion(self, event):
        if self.edit_mode:
            for polygon_id in self.no_go_polygons:
                coords = self.canvas.coords(polygon_id)
                for i in range(0, len(coords), 2):
                    if abs(event.x - coords[i]) < 10 and abs(event.y - coords[i+1]) < 10:
                        self.canvas.config(cursor="hand2")  # Vertex hover
                        return
                cx = sum(coords[::2]) / (len(coords) // 2)
                cy = sum(coords[1::2]) / (len(coords) // 2)
                if abs(event.x - cx) < 15 and abs(event.y - cy) < 15:
                    self.canvas.config(cursor="fleur")  # Center hover
                    return
            self.canvas.config(cursor="arrow")
        else:
            self.canvas.config(cursor=self.cursor_mode)
        
    def on_press(self, event):
        if self.edit_mode:
            for polygon_id in self.no_go_polygons:
                coords = self.canvas.coords(polygon_id)
                for i in range(0, len(coords), 2):
                    vx, vy = coords[i], coords[i+1]
                    if abs(event.x - vx) < 10 and abs(event.y - vy) < 10:
                        self.selected_shape = (polygon_id, 'vertex', i)
                        return

                cx = sum(coords[::2]) / (len(coords) // 2)
                cy = sum(coords[1::2]) / (len(coords) // 2)
                if abs(event.x - cx) < 15 and abs(event.y - cy) < 15:
                    self.selected_shape = (polygon_id, 'move', event.x, event.y)
                    return
        elif self.mode == "no_go":
            if self.current_polygon_points:
                last_x, last_y = self.current_polygon_points[-1]
                line = self.canvas.create_line(last_x, last_y, event.x, event.y, fill="black")
                self.current_polygon_lines.append(line)
            self.current_polygon_points.append((event.x, event.y))
            if len(self.current_polygon_points) > 2 and self.is_polygon_closed():
                self.finish_polygon()
        elif self.mode == "home":
            if self.is_point_inside_no_go_zone(event.x, event.y):
                self.show_warning("Cannot place the Home Zone inside a No-Go Zone.")
                return
            if self.home_rectangle:
                self.canvas.delete(self.home_rectangle)
            self.home_zone = (event.x, event.y)
            self.home_rectangle = self.canvas.create_oval(
                event.x - 10, event.y - 10, event.x + 10, event.y + 10, fill="blue", outline="blue"
            )

            
    def is_inside_home_zone(self, x, y):
        if self.home_zone:
            hx, hy = self.home_zone
            return (hx-10 <= x <= hx+10 and hy-10 <= y <= hy+10)
        return False
    
    def is_polygon_over_home_zone(self, polygon_coords):
        if not self.home_zone:
            return False

        # Flatten the list if needed
        flat_coords = []
        for point in polygon_coords:
            if isinstance(point, tuple):
                flat_coords.extend(point)
            else:
                flat_coords.append(point)

        hx, hy = self.home_zone
        radius = 10  # Same as your home zone radius

        # Sample around the home zone's circumference
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            point_x = hx + radius * math.cos(rad)
            point_y = hy + radius * math.sin(rad)
            if self.point_in_polygon(point_x, point_y, flat_coords):
                return True

        # Also check the center
        if self.point_in_polygon(hx, hy, flat_coords):
            return True

        return False

    def is_point_inside_no_go_zone(self, x, y):
        for polygon_id in self.no_go_polygons:
            coords = self.canvas.coords(polygon_id)
            if self.point_in_polygon(x, y, coords):
                return True
        return False

    def point_in_polygon(self, x, y, poly_coords):
        num = len(poly_coords)
        j = num - 2
        inside = False
        for i in range(0, num, 2):
            xi, yi = poly_coords[i], poly_coords[i + 1]
            xj, yj = poly_coords[j], poly_coords[j + 1]
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-10) + xi):
                inside = not inside
            j = i
        return inside

    def clear_current_polygon(self):
        for line in self.current_polygon_lines:
            self.canvas.delete(line)
        self.current_polygon_points = []
        self.current_polygon_lines = []

    def is_polygon_closed(self):
        first_x, first_y = self.current_polygon_points[0]
        last_x, last_y = self.current_polygon_points[-1]
        return abs(first_x - last_x) < 10 and abs(first_y - last_y) < 10

    def fill_polygon(self):
        polygon = self.canvas.create_polygon(self.current_polygon, fill="black", outline="black")
        self.no_go_polygons.append(polygon)
        self.current_polygon = []

    def on_drag(self, event):
        if not self.edit_mode or not self.selected_shape:
            return

        polygon_id, mode, *data = self.selected_shape
        coords = self.canvas.coords(polygon_id)

        if mode == 'vertex':
            index = data[0]
            coords[index] = event.x
            coords[index + 1] = event.y
            if self.home_zone and self.is_polygon_over_home_zone(coords):
                self.show_warning("Cannot move a No-Go Zone over the Home Zone.")
                return
            self.canvas.coords(polygon_id, *coords)

        elif mode == 'move':
            start_x, start_y = data
            dx = event.x - start_x
            dy = event.y - start_y
            new_coords = [c + dx if i % 2 == 0 else c + dy for i, c in enumerate(coords)]
            if self.home_zone and self.is_polygon_over_home_zone(new_coords):
                self.show_warning("Cannot move a No-Go Zone over the Home Zone.")
                return
            self.canvas.coords(polygon_id, *new_coords)
            self.selected_shape = (polygon_id, 'move', event.x, event.y)

        
    def on_release(self, event):
        self.selected_shape= None
        
    def on_right_click(self, event):
        for polygon in self.no_go_polygons:
            if self.canvas.find_overlapping(event.x, event.y, event.x, event.y):
                self.canvas.delete(polygon)
                self.no_go_polygons.remove(polygon)
                break

    def save_map_with_zones(self):
        if not self.check_map_loaded():
            return

        if self.home_zone is None:
            self.show_warning("Please mark exactly one Home zone on the map before saving.")
            return

        original_width, original_height = self.original_map_size
        current_width, current_height = self.canvas.winfo_width(), self.canvas.winfo_height()

        scale_x = original_width / current_width
        scale_y = original_height / current_height

        annotated_map = self.map_image.copy().resize((original_width, original_height))
        draw = ImageDraw.Draw(annotated_map)

        for polygon_id in self.no_go_polygons:
            coords = self.canvas.coords(polygon_id)
            if len(coords) < 6:  # Check for at least 3 points
                print(f"Skipping invalid polygon with ID {polygon_id}, not enough points.")
                continue
            scaled_coords = [(x * scale_x, y * scale_y) for x, y in zip(coords[::2], coords[1::2])]
            draw.polygon(scaled_coords, fill="black", outline="black")

        x, y = self.home_zone
        x, y = x * scale_x, y * scale_y
        draw.ellipse([x - 10 * scale_x, y - 10 * scale_y, x + 10 * scale_x, y + 10 * scale_y], fill="blue", outline="blue")

        file_path = filedialog.asksaveasfilename(defaultextension=".pgm", filetypes=[("PGM Files", "*.pgm")])
        if file_path:
            annotated_map.save(file_path)
            map_filename = os.path.basename(file_path)

            yaml_content = f"""image: {map_filename}
resolution: 0.05
origin: [0.0, 0.0, 0.0]
occupied_thresh: 0.65
free_thresh: 0.25
negate: 0
mode: trinary
"""
            yaml_path = file_path.replace(".pgm", ".yaml")
            with open(yaml_path, "w") as yaml_file:
                yaml_file.write(yaml_content)

            print("Map and YAML file saved at:", file_path)
            backend.map_filename = map_filename

if __name__ == "__main__":
    root = tk.Tk()
    app = NoGoZoneApp(root)
    root.mainloop()
    try:
        root.mainloop()
    finally:
        app.stop_teleop_listener()
