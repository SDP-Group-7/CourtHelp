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
        self.current_preview = None  # Used to store shape preview during drawing
        self.no_go_shapes = []  # Stores finalized no-go zones
        self.active_button = None 
        self.occupied_regions = []  # Stores occupied areas of No-Go Zones
        self.original_no_go_positions = {}
        self.style = ttk.Style()
        self.style.configure("TButton", background="#D9D9D9", foreground="black", font=('TkDefaultFont', 12))  # Default style
        self.style.map("Active.TButton", background=[("active", "#FFD700"), ("!active", "#FFD700")])  # Gold for active

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

        # Create shape selection panel inside the main app
        self.shape_panel = tk.Frame(self.root, bg="#DDD", bd=2, relief=tk.RIDGE)
        self.shape_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)
        tk.Label(self.shape_panel, text="Select Shape", font=("Arial", 12, "bold"), bg="#DDD").pack(pady=5)

        self.shape_buttons = {}  # Dictionary to store buttons

        shapes = ["Oval", "Circle", "Square", "Triangle", "Pentagon"]
        for shape in shapes:
            btn = tk.Button(self.shape_panel, text=shape, state=tk.DISABLED, 
                            command=lambda s=shape: self.select_shape(s))
            btn.pack(fill=tk.X, padx=5, pady=2)
            self.shape_buttons[shape] = btn

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
        self.canvas.bind("<ButtonRelease-1>", self.finalize_shape)
        self.canvas.bind("<ButtonPress-3>", self.on_right_click)
        #self.canvas.bind("<Motion>", self.on_motion)
        #self.canvas.bind("<B1-Motion>", self.update_shape_preview)
        self.canvas.bind("<Motion>", self.on_motion)       # Detect hover over shapes
        self.canvas.bind("<B1-Motion>", self.on_drag)      # Drag to move/resize shapes

        self.root.after(100, self.ros_spin)

    def custom_button(self, control_frame, text, command, tooltip):
        button = ttk.Button(master=control_frame,
                        text=text,
                        command=lambda: self.set_active_button(button, command),  # Wraps command,
                        style="TButton"  # Default style
                        )
        button.pack(fill=tk.BOTH, ipady=5, pady=3, padx=10)
        button.bind("<Enter>", lambda e: self.show_tooltip(e, tooltip))
        button.bind("<Leave>", lambda e: self.hide_tooltip())
        return button
    
    def set_active_button(self, button, command):
        """ Updates button color when clicked and resets others """
        if hasattr(self, "active_button") and self.active_button:
            self.active_button.configure(style="TButton")  # Reset old button

        button.configure(style="Active.TButton")  # Change new button to gold
        self.active_button = button  # Store active button
        command()

    def set_active_control_button(self, button, command):
        """ Updates control button styles when clicked and sends the command. """
        # Reset all buttons to default (gray)
        for btn in [self.up_button, self.left_button, self.stop_button, self.right_button, self.down_button]:
            btn.config(bg="lightgray", fg="black")

        # Set the clicked button to gold
        button.config(bg="#FFD700", fg="black")

        # Send the command to the robot
        self.send_command(command)
    
    #set control button state
    def set_control_buttons_state(self, state):
        self.up_button.config(state=state)
        self.left_button.config(state=state)
        self.stop_button.config(state=state)
        self.right_button.config(state=state)
        self.down_button.config(state=state)

    def select_shape(self, shape):
        """ Sets the selected shape for no-go zones and enables drawing mode. """
        if self.mode != "no_go":
            return  # Prevents selection when in home/edit mode

        self.selected_shape = shape
        self.edit_mode = False
        self.canvas.config(cursor="cross")
        for btn in self.shape_buttons.values():
            btn.config(bg="lightgray", fg="black")

        # Highlight selected shape
        self.shape_buttons[shape].config(bg="#FFD700", fg="black")

    def finalize_shape(self, event):
        if self.current_preview:
            self.canvas.delete(self.current_preview)
        
        final_shape = self.create_shape(self.start_x, self.start_y, event.x, event.y, preview=False)
        
        if final_shape:  # Only add if the shape is valid
            self.no_go_shapes.append(final_shape)
        
        self.current_preview = None

    def start_drawing_shape(self, event):
        self.start_x, self.start_y = event.x, event.y
        if self.current_preview:
            self.canvas.delete(self.current_preview)
        
        self.current_preview = self.create_shape(self.start_x, self.start_y, event.x, event.y, preview=True)

    def update_shape_preview(self, event):
        if self.current_preview:
            self.canvas.delete(self.current_preview)
        self.current_preview = self.create_shape(self.start_x, self.start_y, event.x, event.y, preview=True)

    def create_shape(self, x1, y1, x2, y2, preview=False):
        shape_id = None
        outline_color = "black"
        fill_color = "" if preview else "black"  # No fill for preview
        if self.selected_shape == "Oval":
            shape_id = self.canvas.create_oval(x1, y1, x2, y2, outline=outline_color, fill=fill_color, tags="preview")
        elif self.selected_shape == "Circle":
            size = min(abs(x2 - x1), abs(y2 - y1))
            shape_id = self.canvas.create_oval(x1, y1, x1 + size, y1 + size, outline=outline_color, fill=fill_color, tags="preview")
        elif self.selected_shape == "Square":
            size = min(abs(x2 - x1), abs(y2 - y1))
            shape_id = self.canvas.create_rectangle(x1, y1, x1 + size, y1 + size, outline=outline_color, fill=fill_color, tags="preview")
        elif self.selected_shape == "Triangle":
            shape_id = self.canvas.create_polygon(x1, y2, (x1+x2)//2, y1, x2, y2, outline=outline_color, fill=fill_color, tags="preview")
        elif self.selected_shape == "Pentagon":
            shape_id = self.create_pentagon(x1, y1, x2, y2, preview)
        return shape_id
    
    def create_pentagon(self, x1, y1, x2, y2, preview):
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        radius = min(abs(x2 - x1), abs(y2 - y1)) // 2
        angle = 2 * math.pi / 5
        points = [(cx + radius * math.cos(i * angle), cy + radius * math.sin(i * angle)) for i in range(5)]
        return self.canvas.create_polygon(points, outline="black", fill="black" if not preview else "", tags="preview")

    def start_robot(self):
        map_path = filedialog.askopenfilename(
            title="Select Map YAML File",
            filetypes=[("YAML Files", "*.yaml")]
        )
        if map_path:
            backend.main(map_path, self.home_zone) #'''self.home_zone'''
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
        self.enable_editing_buttons()
        return True
    
    def enable_editing_buttons(self):
        buttons_to_enable = [
            self.no_go_button,
            self.home_zone_button,
            self.delete_all_button,
            self.edit_zone_button
        ]

        for button in buttons_to_enable:
            button.config(state=tk.NORMAL)

        # Also enable shape selection buttons
        self.enable_shapes()

        # Force UI to update
        self.root.update_idletasks()

    def enable_shapes(self):
        """Enable shape selection buttons only if 'Draw No-Go Zone' is active."""
        if self.mode == "no_go":  # Only enable shapes if No-Go mode is active
            for child in self.shape_panel.winfo_children():
                if isinstance(child, tk.Button):
                    child.config(state=tk.NORMAL)

    def show_tooltip(self, event, text):
        widget = event.widget
        x = widget.winfo_rootx() - self.root.winfo_rootx() + widget.winfo_width() + 10
        y = widget.winfo_rooty() - self.root.winfo_rooty()

        self.tooltip.config(text=text)
        self.tooltip.place(x=x, y=y)
    
    def hide_tooltip(self):
        self.tooltip.place_forget()
        
    def set_no_go_mode(self):
        """ Opens a persistent shape selection panel and enables shape drawing mode. """
        if not self.check_map_loaded():
            return
        self.mode = "no_go"
        self.edit_mode = False
        self.selected_shape = None
        self.canvas.config(cursor="cross")

        #for btn in self.shape_buttons.values():
            #btn.config(state=tk.NORMAL, bg="lightgray", fg="black")
        self.enable_shapes()
        
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

    def disable_shapes(self):
        """ Disables shape selection when switching modes. """
        for btn in self.shape_buttons.values():
            btn.config(state=tk.DISABLED, bg="lightgray", fg="black")
        self.selected_shape = None  # Reset selection
        
    def set_home_zone_mode(self):
        if not self.check_map_loaded():
            return
        self.mode = "home"
        self.edit_mode = False
        self.selected_shape = None
        self.canvas.config(cursor="circle")
        
    def enable_edit_mode(self):
        if not self.check_map_loaded():
            return
        self.edit_mode = True
        self.mode = None  # Disable no-go and home zone drawing
        self.selected_shape = None
        self.canvas.config(cursor="arrow")
    
    def delete_all_zones(self):
        """ Deletes all no-go zones and the home zone. """
        if not self.check_map_loaded():
            return
        
        # Delete all no-go zones
        for shape in self.no_go_shapes:
            self.canvas.delete(shape)
        self.no_go_shapes.clear()

        # Delete all no-go polygons
        for polygon in self.no_go_polygons:
            self.canvas.delete(polygon)
        self.no_go_polygons.clear()

        # Delete home zone if it exists
        if self.home_rectangle:
            self.canvas.delete(self.home_rectangle)
            self.home_rectangle = None
            self.home_zone = None

        self.selected_shape = None  # Reset selected shape
        
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
        self.enable_editing_buttons()

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
        self.disable_editing_buttons()
        self.reset_button_highlights()

    
    def reset_button_highlights(self):
        """Resets all buttons to their default color."""
        buttons_to_reset = [
            self.no_go_button,
            self.home_zone_button,
            self.delete_all_button,
            self.edit_zone_button
        ]

        for active_button in buttons_to_reset:
            self.active_button.configure(style="TButton")

    def disable_editing_buttons(self):
        buttons_to_disable = [
            self.no_go_button,
            self.home_zone_button,
            self.delete_all_button,
            self.edit_zone_button
        ]

        for button in buttons_to_disable:
            button.config(state=tk.DISABLED)

        # Also disable shape selection buttons
        self.disable_shapes()

        # Force UI to update
        self.root.update_idletasks()

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
        if not self.edit_mode:
            self.canvas.config(cursor=self.cursor_mode)
            return

        self.selected_shape = None  # Reset selected shape unless found
        for shape in self.no_go_shapes:
            coords = self.canvas.coords(shape)

            self.original_no_go_positions[shape] = coords[:]

            # Check for hovering over vertices
            for i in range(0, len(coords), 2):
                vx, vy = coords[i], coords[i + 1]
                if abs(event.x - vx) < 10 and abs(event.y - vy) < 10:
                    self.canvas.config(cursor="hand2")  # Indicate vertex hover
                    self.selected_shape = (shape, 'vertex', i)  # Store shape, mode, and vertex index
                    return

            # Check for hovering over the center of the shape
            cx = sum(coords[::2]) / (len(coords) // 2)
            cy = sum(coords[1::2]) / (len(coords) // 2)
            if abs(event.x - cx) < 15 and abs(event.y - cy) < 15:
                self.canvas.config(cursor="fleur")  # Indicate move cursor
                self.selected_shape = (shape, 'move', event.x, event.y)  # Store shape, mode, and initial position
                return

        self.canvas.config(cursor="arrow")  # Reset cursor if not hovering

    def is_home_zone_inside_no_go(self, x, y, shape, coords):
        """Check if the home zone at (x, y) is inside a no-go zone."""
        shape_type = self.get_shape_type(shape)

        if shape_type in ["Circle", "Oval"]:
            return self.is_point_inside_circle(x, y, coords)
        elif shape_type in ["Square", "Rectangle"]:
            return self.is_point_inside_rectangle(x, y, coords)
        elif shape_type in ["Triangle", "Pentagon"]:
            return self.is_point_inside_polygon(x, y, coords)

        return False  # Default to False if shape type is unknown


    def is_no_go_zone_over_home_zone(self, polygon_coords):
        """Check if a no-go zone overlaps with the home zone."""
        if not self.home_zone:
            return False  # No home zone exists yet

        hx, hy = self.home_zone
        for i in range(0, len(polygon_coords), 2):
            px, py = polygon_coords[i], polygon_coords[i + 1]
            if abs(hx - px) < 10 and abs(hy - py) < 10:
                return True  # Found overlap
        return False


    def is_point_inside_circle(self, x, y, coords):
        """Check if a point is inside a circular or oval no-go zone."""
        x1, y1, x2, y2 = coords  # Bounding box of the oval
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2  # Center of the circle
        radius = max(abs(x2 - x1), abs(y2 - y1)) / 2  # Approximate radius

        return (x - cx) ** 2 + (y - cy) ** 2 < radius ** 2


    def is_point_inside_rectangle(self, x, y, coords):
        """Check if a point is inside a rectangular or square no-go zone."""
        x1, y1, x2, y2 = coords
        return x1 <= x <= x2 and y1 <= y <= y2


    def is_point_inside_polygon(self, x, y, poly_coords):
        """Check if a point is inside a polygon using the ray-casting algorithm."""
        num = len(poly_coords) // 2  # Number of vertices
        inside = False
        j = num - 1  # Last vertex index

        for i in range(num):
            xi, yi = poly_coords[2 * i], poly_coords[2 * i + 1]  # Current vertex
            xj, yj = poly_coords[2 * j], poly_coords[2 * j + 1]  # Previous vertex

            if ((yi > y) != (yj > y)) and (
                x < (xj - xi) * (y - yi) / (yj - yi + 1e-10) + xi
            ):
                inside = not inside  # Flip the flag

            j = i  # Move to the next vertex

        return inside


    def get_shape_type(self, shape):
        """Identify the type of shape based on its coordinates."""
        coords = self.canvas.coords(shape)
        if len(coords) == 4:
            # Rectangles, squares, ovals, and circles all have 4 values (x1, y1, x2, y2)
            width = abs(coords[2] - coords[0])
            height = abs(coords[3] - coords[1])
            if width == height:
                return "Circle" if "oval" in self.canvas.gettags(shape) else "Square"
            return "Oval" if "oval" in self.canvas.gettags(shape) else "Rectangle"

        if len(coords) == 6:
            return "Triangle"

        if len(coords) == 10:
            return "Pentagon"

        return "Unknown"  # Fallback
        
    def on_press(self, event):
        if self.edit_mode:
            for shape in self.no_go_shapes:
                coords = self.canvas.coords(shape)
                for i in range(0, len(coords), 2):
                    vx, vy = coords[i], coords[i+1]
                    if abs(event.x - vx) < 10 and abs(event.y - vy) < 10:
                        self.selected_shape = (shape, 'vertex', i)
                        return

                cx = sum(coords[::2]) / (len(coords) // 2)
                cy = sum(coords[1::2]) / (len(coords) // 2)
                if abs(event.x - cx) < 15 and abs(event.y - cy) < 15:
                    self.selected_shape = (shape, 'move', event.x, event.y)
                    return
        elif self.mode == "no_go" and self.selected_shape:
            if self.is_inside_home_zone(event.x, event.y):
                self.show_warning("Cannot place a No-Go Zone over the Home Zone.")
                return
            self.start_x, self.start_y = event.x, event.y
            self.current_preview = None  # Reset preview
        elif self.mode == "home":
            for shape in self.no_go_shapes:
                coords = self.canvas.coords(shape)
                if self.is_home_zone_inside_no_go(event.x, event.y, shape, coords):
                    self.show_warning("Cannot place the Home Zone inside a No-Go Zone.")
                    return

            # Remove existing home zone if one exists
            if self.home_rectangle:
                self.canvas.delete(self.home_rectangle)

            self.home_zone = (event.x, event.y)
            self.home_rectangle = self.canvas.create_oval(
                event.x - 10, event.y - 10, event.x + 10, event.y + 10, fill="blue", outline="blue"
            )
            print(self.home_zone)

            
    def is_inside_home_zone(self, x, y):
        if self.home_zone:
            hx, hy = self.home_zone
            return (hx-10 <= x <= hx+10 and hy-10 <= y <= hy+10)
        return False
    
    
    def is_polygon_over_home_zone(self, polygon_coords):
        """Check if a no-go zone overlaps with the home zone."""
        if not self.home_zone:
            return False

        hx, hy = self.home_zone
        for i in range(0, len(polygon_coords), 2):
            if abs(hx - polygon_coords[i]) < 10 and abs(hy - polygon_coords[i+1]) < 10:
                return True
        return False

    def is_point_inside_no_go_zone(self, x, y):
        for shape in self.no_go_shapes:
            coords = self.canvas.coords(shape)
            if self.point_in_polygon(x, y, coords):
                return True
        return False

    def point_in_polygon(self, x, y, poly_coords):
        """Check if a point (x, y) is inside a polygon using the ray-casting algorithm."""
        num = len(poly_coords) // 2  # Number of vertices
        inside = False
        j = num - 1  # Last vertex index

        for i in range(num):
            xi, yi = poly_coords[2 * i], poly_coords[2 * i + 1]  # Current vertex
            xj, yj = poly_coords[2 * j], poly_coords[2 * j + 1]  # Previous vertex

            if ((yi > y) != (yj > y)) and (
                x < (xj - xi) * (y - yi) / (yj - yi + 1e-10) + xi
            ):
                inside = not inside  # Flip the flag

            j = i  # Move to the next vertex

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
        if self.mode == "no_go" and self.selected_shape:
            if self.current_preview:
                self.canvas.delete(self.current_preview)  # Remove old preview

            self.current_preview = self.create_shape(self.start_x, self.start_y, event.x, event.y, preview=True)
        if not self.edit_mode or not self.selected_shape:
            return
        
        shape, mode, *data = self.selected_shape
        shape, mode, *data = self.selected_shape
        coords = self.canvas.coords(shape)

        shape, mode, *data = self.selected_shape
        coords = self.canvas.coords(shape)

        if mode == 'vertex':  # Resizing
            index = data[0]
            coords[index] = event.x
            coords[index + 1] = event.y
            shape_type = self.get_shape_type(shape)
            is_invalid_resize = False

            if shape_type in ["Circle", "Oval"] and self.is_point_inside_circle(self.home_zone[0], self.home_zone[1], coords):
                is_invalid_resize = True
            elif shape_type in ["Square", "Rectangle"] and self.is_point_inside_rectangle(self.home_zone[0], self.home_zone[1], coords):
                is_invalid_resize = True
            elif shape_type in ["Triangle", "Pentagon"] and self.is_point_inside_polygon(self.home_zone[0], self.home_zone[1], coords):
                is_invalid_resize = True

            if is_invalid_resize:
                self.show_warning("Cannot resize No-Go Zone into the Home Zone.")

                # Restore shape to its original size
                if shape in self.original_no_go_positions:
                    self.canvas.coords(shape, *self.original_no_go_positions[shape])
                return

            self.canvas.coords(shape, *coords)

        elif mode == 'move':  # Moving
            start_x, start_y = data
            dx = event.x - start_x
            dy = event.y - start_y
            new_coords = [c + dx if i % 2 == 0 else c + dy for i, c in enumerate(coords)]

            # Prevent moving into home zone
            shape_type = self.get_shape_type(shape)
            is_invalid_move = False

            if shape_type in ["Circle", "Oval"] and self.is_point_inside_circle(self.home_zone[0], self.home_zone[1], new_coords):
                is_invalid_move = True
            elif shape_type in ["Square", "Rectangle"] and self.is_point_inside_rectangle(self.home_zone[0], self.home_zone[1], new_coords):
                is_invalid_move = True
            elif shape_type in ["Triangle", "Pentagon"] and self.is_point_inside_polygon(self.home_zone[0], self.home_zone[1], new_coords):
                is_invalid_move = True

            if is_invalid_move:
                self.show_warning("Cannot move No-Go Zone over the Home Zone.")

                if shape in self.original_no_go_positions:
                    self.canvas.coords(shape, *self.original_no_go_positions[shape])
                return

            

            self.canvas.coords(shape, *new_coords)
            self.selected_shape = (shape, 'move', event.x, event.y)


        
    def on_release(self, event):
        """ Finalizes the shape when the user releases the mouse button. """
        if self.mode == "no_go" and self.selected_shape:
            x1, y1 = self.start_x, self.start_y
            x2, y2 = event.x, event.y

            self.canvas.delete("preview")  # Remove preview

            if self.selected_shape == "Circle":
                radius = max(abs(x2 - x1), abs(y2 - y1)) // 2
                shape = self.canvas.create_oval(x1 - radius, y1 - radius, x1 + radius, y1 + radius, outline="black", fill="black")

            elif self.selected_shape == "Oval":
                shape = self.canvas.create_oval(x1, y1, x2, y2, outline="black", fill="black")

            elif self.selected_shape == "Square":
                side = max(abs(x2 - x1), abs(y2 - y1))
                shape = self.canvas.create_rectangle(x1, y1, x1 + side, y1 + side, outline="black", fill="black")

            elif self.selected_shape == "Triangle":
                points = [x1, y2, (x1 + x2) // 2, y1, x2, y2]
                shape = self.canvas.create_polygon(points, outline="black", fill="black")

            elif self.selected_shape == "Pentagon":
                shape = self.draw_pentagon_final(x1, y1, x2, y2)

            self.no_go_polygons.append(shape)

    def draw_pentagon_preview(self, x1, y1, x2, y2):
        """ Draws a preview of a pentagon. """
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        radius = max(abs(x2 - x1), abs(y2 - y1)) // 2

        points = []
        for i in range(5):
            angle = math.radians(72 * i - 90)  # 5 sides, 72-degree angles
            px = center_x + radius * math.cos(angle)
            py = center_y + radius * math.sin(angle)
            points.append(px)
            points.append(py)

        self.canvas.create_polygon(points, outline="black", fill="", tags="preview")
        
    def on_right_click(self, event):
        clicked_shapes = self.canvas.find_overlapping(event.x, event.y, event.x, event.y)

        for shape in clicked_shapes:
            if shape in self.no_go_shapes:  # Ensure deletion targets correct list
                self.canvas.delete(shape)
                self.no_go_shapes.remove(shape)
                print("No-Go Zone deleted")  # Debugging print
                return  # Stop after deleting the first detected shape

        if self.home_rectangle and self.is_inside_home_zone(event.x, event.y):
            self.canvas.delete(self.home_rectangle)
            self.home_rectangle = None
            self.home_zone = None

    def draw_pentagon_final(self, x1, y1, x2, y2):
        """ Draws a finalized pentagon after releasing the mouse button. """
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        radius = max(abs(x2 - x1), abs(y2 - y1)) // 2

        points = []
        for i in range(5):
            angle = math.radians(72 * i - 90)
            px = center_x + radius * math.cos(angle)
            py = center_y + radius * math.sin(angle)
            points.append(px)
            points.append(py)

        return self.canvas.create_polygon(points, outline="black", fill="black")

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

        for shape in self.no_go_shapes:
            coords = self.canvas.coords(shape)
            if len(coords) < 6:  # Check for at least 3 points
                print(f"Skipping invalid polygon with ID {shape}, not enough points.")
                continue
            scaled_coords = [(x * scale_x, y * scale_y) for x, y in zip(coords[::2], coords[1::2])]
            draw.polygon(scaled_coords, fill="black", outline="black")

        x, y = self.home_zone
        x, y = x * scale_x, y * scale_y
        self.home_zone = x, y
        #draw.ellipse([x - 10 * scale_x, y - 10 * scale_y, x + 10 * scale_x, y + 10 * scale_y], fill="blue", outline="blue")

        file_path = filedialog.asksaveasfilename(defaultextension=".pgm", filetypes=[("PGM Files", "*.pgm")])
        if file_path:
            annotated_map.save(file_path)
            map_filename = os.path.basename(file_path)

            yaml_content = f"""image: {map_filename}
resolution: 0.05
origin: [-3.0, -4.0, 0.0]
occupied_thresh: 0.65
free_thresh: 0.25
negate: 0
mode: trinary
"""
            yaml_path = file_path.replace(".pgm", ".yaml")
            with open(yaml_path, "w") as yaml_file:
                yaml_file.write(yaml_content)

            print("Map and YAML file saved at:", file_path)
            
            yaml_filename = os.path.basename(yaml_path)
            backend.map_filename = yaml_filename
            backend.home_zone = self.home_zone
            print(self.home_zone)

if __name__ == "__main__":
    root = tk.Tk()
    app = NoGoZoneApp(root)
    root.mainloop()
    try:
        root.mainloop()
    finally:
        app.stop_teleop_listener()
