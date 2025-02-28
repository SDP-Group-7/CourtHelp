import tkinter as tk
import tkinter.ttk as ttk
from tkinter import filedialog, Canvas, messagebox
from PIL import Image, ImageTk, ImageDraw
import backend
import os
PANEL_BG="#14213d"
class NoGoZoneApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Setting up your CourtHelp robot")
        self.root.state("normal")
        
        # Create a frame for control buttons on the left side
        self.control_frame = tk.Frame(self.root, bg=PANEL_BG)
        self.control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5, ipadx=5, ipady=5)
        button_panel_title = tk.Label(self.control_frame, text="Setting up your robot", bg="yellow", fg="black", relief=tk.FLAT, borderwidth=1, font=('TkDefaultFont', 13))
        button_panel_title.pack(fill=tk.X, pady=5,)

        self.custom_step_label(self.control_frame,"Step 1: Configure the Robot")
        self.configure_button = self.custom_button(self.control_frame, text="Configure", command=backend.run_ros_package, tooltip="Start robot configuration")
        self.save_map_button = self.custom_button(self.control_frame, text="Configuration Done", command=backend.run_ros_package2, tooltip="Save the map created by the robot")

        self.custom_step_label(self.control_frame, "Step 2: Load Map")
        self.load_map_button = self.custom_button(self.control_frame, text="Load Map", command=self.load_map, tooltip="Load the .pgm map from the robot.")

        self.custom_step_label(self.control_frame,"Step 3: Mark Map")
        self.no_go_button= self.custom_button(self.control_frame, text="Draw No-Go Zone",command=self.set_no_go_mode, tooltip="Click and drag then release to draw a No-Go zone (black rectangle). Right click a the zone to delete.\n A No-Go Zone is an area the robot is forbidden from entering such as the benches for players, an open door or other obstacles too high or low for the LIDAR sensor to detect.")
        self.home_zone_button = self.custom_button(self.control_frame, text="Draw Home Zone", command=self.set_home_zone_mode, tooltip="Click position to place a Home zone (blue circle). The robot returns to the home zone after collecting all balls. There must be exactly 1 home zone in the map.") 
        self.delete_all_button = self.custom_button(self.control_frame, text="Delete All Zones", command=self.delete_all_zones, tooltip="Click to delete all No-Go and Home zones from the map.")
        self.edit_zone_button = self.custom_button(self.control_frame, text="Edit Zones (Move)", command=self.enable_edit_mode, tooltip="Click to enable edit mode. Drag center of No-Go or Home zones to move them and hover over edges of No-Go zones until you see a cross then drag to extend them")
        
        self.custom_step_label(self.control_frame,"Step 4: Save Map")
        self.save_button = self.custom_button(self.control_frame, text="Save Map with Zones", command=self.save_map_with_zones, tooltip="Save your map with added zones.")

        self.custom_step_label(self.control_frame,"Step 5: Start the Robot")
        self.done_button = self.custom_button(self.control_frame, text="Done", command=backend.main, tooltip="Start the robot's function")

        self.canvas = Canvas(self.root, bg='white')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Create bottom border
        self.bottom_frame = tk.Frame(self.root)
        self.bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        
        self.tooltip = tk.Label(self.root, text="", bg="yellow", fg="black", relief=tk.SOLID, borderwidth=1, font=('TkDefaultFont', 11))
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
        self.cursor_mode="arrow"
        self.canvas.config(cursor=self.cursor_mode)
        
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<ButtonPress-3>", self.on_right_click)  # Right-click to delete zones
        self.canvas.bind("<Motion>", self.on_motion)  # Detect hovering over corners

    def custom_button(self, control_frame, text, command, tooltip):
        button = ttk.Button(master=control_frame,
                        text=text,
                        command=command,
                        style='standard.TButton'
                        )
        button.pack(fill=tk.BOTH, ipady=5, pady=3, padx=10,)
        button.bind("<Enter>", lambda e: self.show_tooltip(tooltip))
        button.bind("<Leave>", lambda e: self.hide_tooltip())
        return button
    
    def custom_step_label(self, control_frame, msg):
        step1 = tk.Label(control_frame, text=msg, anchor="w", fg="white",bg=PANEL_BG, relief=tk.FLAT, borderwidth=1, font=('TkDefaultFont', 13))
        step1.pack(fill=tk.X, pady=5, padx=2)

    def is_inside_no_go_zone(self, x, y):
        """ Check if a point (x, y) is inside any no-go zone. """
        for rect in self.rectangles:
            x1, y1, x2, y2 = self.canvas.coords(rect)
            if x1 <= x <= x2 and y1 <= y <= y2:
                return True
        return False

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
        if self.map_image is None:
            self.show_warning("Please load a map before performing this action.")
            return False
        return True

    def show_tooltip(self, text):
        self.tooltip.config(text=text)
        self.tooltip.place(x=240, y=10)
    
    def hide_tooltip(self):
        self.tooltip.place_forget()
        
    def set_no_go_mode(self):
        if not self.check_map_loaded():
            return
        self.mode = "no_go"
        self.cursor_mode = "tcross"
        self.edit_mode = False
        
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
        for rect in self.rectangles:
            self.canvas.delete(rect)
        self.rectangles.clear()
        self.no_go_zones.clear()
        if self.home_rectangle:
            self.canvas.delete(self.home_rectangle)
            self.home_rectangle = None
            self.home_zone = None
        self.cursor_mode = "arrow"
        
    def load_map(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.bmp;*.pgm")])
        self.cursor_mode = "arrow"
        if file_path:
            self.map_image = Image.open(file_path)
            self.original_map_size = self.map_image.size #save size for later resizing
            self.map_image = self.map_image.resize((self.canvas.winfo_width(), self.canvas.winfo_height()))
            self.tk_map = ImageTk.PhotoImage(self.map_image)
            self.canvas.create_image(self.canvas.winfo_width() // 2, self.canvas.winfo_height() // 2, anchor=tk.CENTER, image=self.tk_map)

        
    def on_motion(self, event):
        for rect in self.rectangles:
            x1, y1, x2, y2 = self.canvas.coords(rect)
            # if cursor near a no-go zone set cursor to cross
            if abs(event.x - x1) < 5 or abs(event.x - x2) < 5 or abs(event.y - y1) < 5 or abs(event.y - y2) < 5:
                self.canvas.config(cursor="cross")  # Resize cursor
                return
            # if cursor within a no-go zone and in edit more set cursor to "fleur"
            elif self.edit_mode and x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self.canvas.config(cursor="fleur")  # Move cursor
                return
        self.canvas.config(cursor=self.cursor_mode)
        
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
                if self.check_no_go_zone_overlap(event.x, event.y, event.x + 30, event.y + 30):
                    self.show_warning("Cannot place a No-Go Zone on top of the Home Zone.")
                    return
                self.start_x, self.start_y = event.x, event.y
                rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, fill="black", outline="black")
                self.rectangles.append(rect)
                self.no_go_zones.append((self.start_x, self.start_y, self.start_x, self.start_y))
            elif self.mode == "home":
                if self.is_inside_no_go_zone(event.x, event.y):
                    self.show_warning("Cannot place the Home Zone inside a No-Go Zone.")
                    return
                if self.home_rectangle:
                    self.canvas.delete(self.home_rectangle)
                self.home_zone = (event.x, event.y)
                self.home_rectangle = self.canvas.create_oval(event.x-10, event.y-10, event.x+10, event.y+10, fill="blue", outline="blue")

    def on_drag(self, event):
        if self.edit_mode and self.selected_rectangle:
            x1, y1, x2, y2 = self.canvas.coords(self.selected_rectangle)

            if self.resizing:
                # Calculate new potential size
                new_x1, new_y1, new_x2, new_y2 = x1, y1, event.x, event.y
                
                # Prevent resizing into the Home Zone
                if self.home_zone:
                    hx, hy = self.home_zone
                    if new_x1 <= hx <= new_x2 and new_y1 <= hy <= new_y2:
                        self.show_warning("Cannot resize a No-Go Zone over the Home Zone.")
                        return
                
                self.canvas.coords(self.selected_rectangle, new_x1, new_y1, new_x2, new_y2)

            elif self.dragging:
                step_x = event.x - self.start_x
                step_y = event.y - self.start_y

                # Compute new position
                new_x1, new_y1, new_x2, new_y2 = x1 + step_x, y1 + step_y, x2 + step_x, y2 + step_y

                # Prevent moving into the Home Zone
                if self.home_zone:
                    hx, hy = self.home_zone
                    if new_x1 <= hx <= new_x2 and new_y1 <= hy <= new_y2:
                        self.show_warning("Cannot move a No-Go Zone over the Home Zone.")
                        return  # Stop movement

                # Move the rectangle if no overlap
                self.canvas.move(self.selected_rectangle, step_x, step_y)
                self.start_x, self.start_y = event.x, event.y

        elif not self.edit_mode and self.mode == "no_go":
            # Prevent creating a No-Go Zone over the Home Zone (delete it if it happens)
            if self.home_zone:
                hx, hy = self.home_zone
                if min(self.start_x, event.x) <= hx <= max(self.start_x, event.x) and min(self.start_y, event.y) <= hy <= max(self.start_y, event.y):
                    self.show_warning("No-Go Zone deleted: Cannot place it over the Home Zone.")
                    self.canvas.delete(self.rectangles[-1])
                    self.rectangles.pop()
                    return  

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

        if self.home_zone is None:
            self.show_warning("Please mark exactly one Home zone on the map before saving.")
            return

        # Get original map dimensions before resizing
        original_width, original_height = self.original_map_size  # Store this when loading the map

        # Get current displayed map size
        current_width, current_height = self.map_image.size  # This is the resized map in the UI

        # Calculate scaling factor (current -> original)
        scale_x = original_width / current_width
        scale_y = original_height / current_height

        # Create a copy of the original map at its original size
        annotated_map = self.map_image.copy().resize((original_width, original_height))
        draw = ImageDraw.Draw(annotated_map)

        # Scale down and draw the no-go zones proportionally
        for rect in self.rectangles:
            x1, y1, x2, y2 = self.canvas.coords(rect)
            x1, x2 = x1 * scale_x, x2 * scale_x
            y1, y2 = y1 * scale_y, y2 * scale_y
            draw.rectangle([x1, y1, x2, y2], fill="black", outline="black")

        # Scale down and draw the home zone proportionally
        if self.home_zone:
            x, y = self.home_zone
            x, y = x * scale_x, y * scale_y
            draw.ellipse([x-10*scale_x, y-10*scale_y, x+10*scale_x, y+10*scale_y], fill="blue", outline="blue")

        # Ask user for save location
        file_path = filedialog.asksaveasfilename(defaultextension=".pgm", filetypes=[("PGM Files", "*.pgm")])
        
        if file_path:
            annotated_map.save(file_path)

            map_filename = os.path.basename(file_path)

    # Generate YAML file
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
