
import tkinter as tk

def draw_arc():
    root = tk.Tk()
    canvas = tk.Canvas(root, width=300, height=300, bg="black")
    canvas.pack()
    
    cx, cy = 150, 150
    r = 100
    
    # Grid
    canvas.create_line(0, 150, 300, 150, fill="gray") # Horizontal
    canvas.create_line(150, 0, 150, 300, fill="gray") # Vertical
    
    # Case 1: Start=-39.3, Extent=183.3 (Max 144 - Min -39.3)
    # Expected: 4 o'clock (Start) -> CCW -> 11 o'clock (End)
    start_angle = -39.3
    extent_angle = 144 - (-39.3) # = 183.3
    
    canvas.create_arc(cx-r, cy-r, cx+r, cy+r, 
                      start=start_angle, extent=extent_angle,
                      fill="green", outline="white", style=tk.PIESLICE)
    
    # Label Start and End
    canvas.create_text(250, 200, text="Start (-39.3)", fill="white") # Approx 4 o'clock
    canvas.create_text(100, 50, text="End (144)", fill="white")   # Approx 11 o'clock
    
    root.mainloop()

if __name__ == "__main__":
    draw_arc()
