
# Debug script for Slot 2 Angles
config = {
    "min": 86.7,
    "max": 270.0,
    "zero_offset": 126.0,
    "actuation_range": 270,
    "min_pos": "bottom"
}

zero_offset = config["zero_offset"]
limits_min = config["min"]
limits_max = config["max"]

# Polarity +1 logic
polarity = 1
math_min = (limits_min - zero_offset) * polarity
math_max = (limits_max - zero_offset) * polarity

print(f"Zero Offset: {zero_offset}")
print(f"Physical Limits: {limits_min} to {limits_max}")
print(f"Math Limits (Forward=0): {math_min:.2f} to {math_max:.2f}")

# Visual check (Tkinter 0=Right, 90=Down)
# -39.3 deg -> Up 39.3? No, Math +Y is Up. Tkinter +Y is Down.
# Math 0 -> Tkinter 0.
# Math +90 (Up) -> Tkinter -90 (Up).
# Math -39.3 (Down-Right) -> Tkinter +39.3 (Down-Right).
print(f"Visual Start (Tkinter): {-math_min:.2f} (Positive is CW/Down)")
print(f"Visual End (Tkinter): {-math_max:.2f} (Negative is CCW/Up)")

# Background Arc
phy_min = 0
phy_max = 270
math_bg_min = (phy_min - zero_offset)
math_bg_max = (phy_max - zero_offset)
print(f"Background Math: {math_bg_min:.2f} to {math_bg_max:.2f}")
