import tkinter as tk
from tkinter import filedialog, Canvas
from PIL import Image, ImageTk
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
        
        self.save_button = tk.Button(self.root, text="Save No-Go Zones", command=self.save_zones)
        self.save_button.pack()
        
        self.instructions_label = tk.Label(self.root, text="Instructions:\n1. Load a map image.\n2. Click and drag to create no-go zones.\n3. Click 'Save No-Go Zones' to export.\n4. Click a no-go zone to delete it.")
        self.instructions_label.pack()
        
        self.rectangles = []  # Stores rectangle objects
        self.no_go_zones = []  # Stores coordinates of no-go zones
        
        self.start_x = None
        self.start_y = None
        self.rect = None
        self.map_image = None
        self.tk_map = None
        
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<ButtonPress-3>", self.on_right_click)  # Right-click to delete zones
        
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
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, event.x, event.y, outline="red", width=2)
        
    def on_drag(self, event):
        self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)
        
    def on_release(self, event):
        end_x, end_y = event.x, event.y
        self.no_go_zones.append({"x1": self.start_x, "y1": self.start_y, "x2": end_x, "y2": end_y})
        self.rectangles.append(self.rect)
        
    def on_right_click(self, event):
        for i, rect in enumerate(self.rectangles):
            coords = self.canvas.coords(rect)
            if coords[0] <= event.x <= coords[2] and coords[1] <= event.y <= coords[3]:
                self.canvas.delete(rect)
                del self.rectangles[i]
                del self.no_go_zones[i]
                break
        
    def save_zones(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
        if file_path:
            with open(file_path, "w") as f:
                json.dump(self.no_go_zones, f, indent=4)
        print("No-Go Zones Saved:", self.no_go_zones)

if __name__ == "__main__":
    root = tk.Tk()
    app = NoGoZoneApp(root)
    root.mainloop()
