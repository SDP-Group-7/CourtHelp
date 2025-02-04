import tkinter as tk
from tkinter import filedialog, Canvas
from PIL import Image, ImageTk, ImageDraw
import json

class NoGoZoneApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Court Help No-Go Zone Implementation")
        self.root.geometry("800x600")
        
        self.canvas = Canvas(self.root, bg='white')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.load_map_button = tk.Button(self.root, text="Load Map", command=self.load_map)
        self.load_map_button.pack()
        
        self.no_go_button = tk.Button(self.root, text="Draw No-Go Zone", command=self.set_no_go_mode)
        self.no_go_button.pack()
        
        self.home_zone_button = tk.Button(self.root, text="Draw Home Zone", command=self.set_home_zone_mode)
        self.home_zone_button.pack()
        
        self.save_button = tk.Button(self.root, text="Save Map with Zones", command=self.save_map_with_zones)
        self.save_button.pack()
        
        self.instructions_label = tk.Label(self.root, text="Instructions:\n1. Load a map image.\n2. Click and drag to create no-go or home zones.\n3. Use the respective buttons to switch between zones.\n4. Right-click a zone to delete it.\n5. Only one home zone can be created.")
        self.instructions_label.pack()
        
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
        
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<ButtonPress-3>", self.on_right_click)  # Right-click to delete zones
        
    def set_no_go_mode(self):
        self.mode = "no_go"
        
    def set_home_zone_mode(self):
        self.mode = "home"
        
    def load_map(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.bmp")])
        if file_path:
            self.map_image = Image.open(file_path)
            self.map_image = self.map_image.resize((800, 500))  # Resize for display
            self.tk_map = ImageTk.PhotoImage(self.map_image)
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_map)
            
    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        color = "blue" if self.mode == "home" else "red"
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, event.x, event.y, outline=color, width=2)
        
    def on_drag(self, event):
        self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)
        
    def on_release(self, event):
        end_x, end_y = event.x, event.y
        if self.mode == "no_go":
            self.no_go_zones.append({"x1": self.start_x, "y1": self.start_y, "x2": end_x, "y2": end_y})
            self.rectangles.append(self.rect)
        elif self.mode == "home":
            if self.home_rectangle:
                self.canvas.delete(self.home_rectangle)
            center_x = (self.start_x + end_x) // 2
            center_y = (self.start_y + end_y) // 2
            self.home_zone = {"x": center_x, "y": center_y}
            self.home_rectangle = self.rect
        
    def on_right_click(self, event):
        for i, rect in enumerate(self.rectangles):
            coords = self.canvas.coords(rect)
            if coords[0] <= event.x <= coords[2] and coords[1] <= event.y <= coords[3]:
                self.canvas.delete(rect)
                del self.rectangles[i]
                del self.no_go_zones[i]
                return
        if self.home_rectangle:
            coords = self.canvas.coords(self.home_rectangle)
            if coords[0] <= event.x <= coords[2] and coords[1] <= event.y <= coords[3]:
                self.canvas.delete(self.home_rectangle)
                self.home_rectangle = None
                self.home_zone = None
        
    def save_map_with_zones(self):
        if self.map_image is None:
            return
        
        annotated_map = self.map_image.copy()
        draw = ImageDraw.Draw(annotated_map)
        
        for zone in self.no_go_zones:
            draw.rectangle([zone['x1'], zone['y1'], zone['x2'], zone['y2']], outline="red", width=3)
        
        if self.home_zone:
            draw.ellipse([(self.home_zone['x']-5, self.home_zone['y']-5),
                          (self.home_zone['x']+5, self.home_zone['y']+5)], fill="blue", outline="blue")
        
        file_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PGM Files", "*.pgm")])
        if file_path:
            annotated_map.save(file_path)
        print("Map with zones saved.")

if __name__ == "__main__":
    root = tk.Tk()
    app = NoGoZoneApp(root)
    root.mainloop()
