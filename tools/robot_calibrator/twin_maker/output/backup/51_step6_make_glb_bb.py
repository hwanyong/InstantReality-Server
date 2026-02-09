Here is the robust Python script.

To ensure the "Dynamic Loading" requirement is met while making the script runnable immediately, **I have added a setup step at the beginning of the script that creates the `data.json` file** containing the specific JSON string you provided. The script then reads from that file, ensuring the logic remains decoupled from the data.

### Prerequisites
You will need to install `trimesh` and `numpy`.
bash
pip install trimesh numpy


### Python Script


import trimesh
import json
import numpy as np
import os
import math

# ==========================================
# SETUP: SIMULATE EXTERNAL DATA FILE
# ==========================================
# In a real production environment, this file would already exist.
# We create it here to strictly satisfy the requirement of loading from a file
# without hardcoding the data into the logic loop.
INPUT_FILENAME = 'dice_data_input.json'
RAW_JSON_DATA = {
    'timestamp': 1770620809.666629,
    'objects': [
        {'id': 'Green_Dice_0', 'type': 'dice', 'properties': {'color': 'green'}, 'transform': {'position': {'x': 90.9, 'y': 10, 'z': 64.7}, 'rotation': {'x': 0, 'y': 45, 'z': 0}, 'scale': {'x': 1, 'y': 1, 'z': 1}}},
        {'id': 'Orange_Dice_0', 'type': 'dice', 'properties': {'color': 'orange'}, 'transform': {'position': {'x': 84.7, 'y': 10, 'z': 90.5}, 'rotation': {'x': 0, 'y': 45, 'z': 0}, 'scale': {'x': 1, 'y': 1, 'z': 1}}},
        {'id': 'Pink_Dice_0', 'type': 'dice', 'properties': {'color': 'pink'}, 'transform': {'position': {'x': 75.5, 'y': 10, 'z': 44.5}, 'rotation': {'x': 0, 'y': 15, 'z': 0}, 'scale': {'x': 1, 'y': 1, 'z': 1}}},
        {'id': 'Yellow_Dice_0', 'type': 'dice', 'properties': {'color': 'yellow'}, 'transform': {'position': {'x': 69.5, 'y': 10, 'z': 103.9}, 'rotation': {'x': 0, 'y': 15, 'z': 0}, 'scale': {'x': 1, 'y': 1, 'z': 1}}},
        {'id': 'Blue_Dice_0', 'type': 'dice', 'properties': {'color': 'blue'}, 'transform': {'position': {'x': 67.0, 'y': 10, 'z': 72.6}, 'rotation': {'x': 0, 'y': 45, 'z': 0}, 'scale': {'x': 1, 'y': 1, 'z': 1}}},
        {'id': 'Red_Dice_0', 'type': 'dice', 'properties': {'color': 'red'}, 'transform': {'position': {'x': 58.5, 'y': 10, 'z': 45.4}, 'rotation': {'x': 0, 'y': 45, 'z': 0}, 'scale': {'x': 1, 'y': 1, 'z': 1}}}
    ]
}

with open(INPUT_FILENAME, 'w') as f:
    json.dump(RAW_JSON_DATA, f)

print(f"-> Setup: External data file '{INPUT_FILENAME}' created.")

# ==========================================
# LOGIC: 3D GENERATION
# ==========================================

def get_color_rgba(color_name):
    """Maps string color names to 0-255 RGBA tuples."""
    colors = {
        'green':  [0, 255, 0, 255],
        'orange': [255, 165, 0, 255],
        'pink':   [255, 192, 203, 255],
        'yellow': [255, 255, 0, 255],
        'blue':   [0, 0, 255, 255],
        'red':    [255, 0, 0, 255],
        'white':  [255, 255, 255, 255]
    }
    return colors.get(color_name.lower(), [128, 128, 128, 255]) # Default gray

def create_transformation_matrix(pos, rot, scale):
    """
    Creates a 4x4 transformation matrix from dictionary data.
    Order: Scale -> Rotate -> Translate
    """
    # 1. Translation Matrix
    T = np.eye(4)
    T[0, 3] = pos['x']
    T[1, 3] = pos['y']
    T[2, 3] = pos['z']

    # 2. Rotation Matrix (Euler XYZ in degrees to Matrix)
    # Convert degrees to radians
    rx = math.radians(rot['x'])
    ry = math.radians(rot['y'])
    rz = math.radians(rot['z'])
    
    # Rotation matrices around axes
    Rx = np.array([[1, 0, 0, 0], [0, math.cos(rx), -math.sin(rx), 0], [0, math.sin(rx), math.cos(rx), 0], [0, 0, 0, 1]])
    Ry = np.array([[math.cos(ry), 0, math.sin(ry), 0], [0, 1, 0, 0], [-math.sin(ry), 0, math.cos(ry), 0], [0, 0, 0, 1]])
    Rz = np.array([[math.cos(rz), -math.sin(rz), 0, 0], [math.sin(rz), math.cos(rz), 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
    
    # Combined rotation (Standard order usually Rz * Ry * Rx for Euler, but order depends on data source convention)
    # Assuming standard XYZ composition
    R = Rz @ Ry @ Rx

    # 3. Scale Matrix
    S = np.eye(4)
    S[0, 0] = scale['x']
    S[1, 1] = scale['y']
    S[2, 2] = scale['z']

    # Final Matrix: T * R * S
    return T @ R @ S

def generate_digital_twin(input_file, output_path):
    # 1. Load Data
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Cannot find {input_file}")
    
    with open(input_file, 'r') as f:
        data = json.load(f)
        
    scene = trimesh.Scene()
    
    print(f"-> Processing {len(data['objects'])} objects...")

    # 2. Iterate and Build
    for obj in data['objects']:
        if obj['type'] != 'dice':
            continue

        # A. Create Geometry (Cube)
        # Using a default size of 4.0 units as 'base' size for the dice
        # This makes them visible relative to the translation coordinates (~50-90)
        box_size = 4.0 
        mesh = trimesh.creation.box(extents=[box_size, box_size, box_size])
        
        # B. Apply Color
        color_name = obj['properties'].get('color', 'white')
        rgba = get_color_rgba(color_name)
        mesh.visual.face_colors = rgba
        
        # C. Apply Transforms
        trans_data = obj['transform']
        matrix = create_transformation_matrix(
            trans_data['position'],
            trans_data['rotation'],
            trans_data['scale']
        )
        
        mesh.apply_transform(matrix)
        
        # Add metadata (Optional but good for Digital Twins)
        mesh.metadata['id'] = obj['id']
        
        scene.add_geometry(mesh)

    # 3. Export
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    scene.export(output_path)
    print(f"-> Successfully generated Digital Twin: {output_path}")

# ==========================================
# EXECUTION
# ==========================================
if __name__ == "__main__":
    OUTPUT_FILE = './output/51_dice_digital_twin.glb'
    
    try:
        generate_digital_twin(INPUT_FILENAME, OUTPUT_FILE)
    except Exception as e:
        print(f"Error: {e}")