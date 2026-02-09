Here is the robust Python script using `trimesh` and `numpy`.

### Prerequisites
You will need the `trimesh` library. If you haven't installed it yet:
bash
pip install trimesh numpy scipy


### Python Script


import trimesh
import numpy as np
import json
import os

# Configuration
INPUT_FILENAME = 'dice_data.json'
OUTPUT_PATH = '/Users/carol/Desktop/worktest/ai_coding/robotics_test2/notebooks/5_GenCode/dice_digital_twin.glb'

# ---------------------------------------------------------
# HELPER: Create the dummy JSON file for this test execution
# (In production, this file would already exist)
# ---------------------------------------------------------
def create_sample_data_file():
    data = {
        "timestamp": 1770550262.377944, 
        "objects": [
            {
                "id": "Red_Dice_0", 
                "type": "dice", 
                "properties": {"color": "red"}, 
                "transform": {
                    "position": {"x": 83.7, "y": 10, "z": 70.6}, 
                    "rotation": {"x": 0, "y": 0, "z": 0}, 
                    "scale": {"x": 1, "y": 1, "z": 1}
                }
            }, 
            {
                "id": "White_Dice_0", 
                "type": "dice", 
                "properties": {"color": "white"}, 
                "transform": {
                    "position": {"x": 78.0, "y": 10, "z": 79.4}, 
                    "rotation": {"x": 0, "y": 45, "z": 0}, 
                    "scale": {"x": 1, "y": 1, "z": 1}
                }
            }
        ]
    }
    
    with open(INPUT_FILENAME, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"DEBUG: Created temporary input file: {INPUT_FILENAME}")

# ---------------------------------------------------------
# MAIN LOGIC
# ---------------------------------------------------------

def get_color_rgba(color_name):
    """Maps string color names to RGBA 0-255 values."""
    cmap = {
        'red':   [255, 0, 0, 255],
        'white': [240, 240, 240, 255], # Slightly off-white for better visibility
        'blue':  [0, 0, 255, 255],
        'green': [0, 255, 0, 255],
        'black': [20, 20, 20, 255]
    }
    return cmap.get(color_name.lower(), [128, 128, 128, 255]) # Default gray

def process_dice_twin(json_input_path, glb_output_path):
    # 1. Dynamic Loading: Read from external JSON file
    if not os.path.exists(json_input_path):
        raise FileNotFoundError(f"Input file not found: {json_input_path}")
        
    with open(json_input_path, 'r') as f:
        data = json.load(f)

    # Initialize Scene
    scene = trimesh.Scene()
    
    # 2. Iterate through objects
    objects = data.get('objects', [])
    print(f"Processing {len(objects)} objects...")

    for obj in objects:
        obj_id = obj.get('id', 'unknown')
        props = obj.get('properties', {})
        trans = obj.get('transform', {})
        
        # Geometry Creation
        # We assume 'dice' is a cube. Let's give it a base size.
        # Since positions are around ~80 units, a size of 4.0 ensures visibility.
        mesh = trimesh.creation.box(extents=[4.0, 4.0, 4.0])
        
        # Apply Color
        color_name = props.get('color', 'gray')
        rgba = get_color_rgba(color_name)
        mesh.visual.face_colors = rgba
        
        # -------------------------------------------------
        # Transform Logic
        # -------------------------------------------------
        
        # Position
        pos_data = trans.get('position', {'x': 0, 'y': 0, 'z': 0})
        translation = [pos_data['x'], pos_data['y'], pos_data['z']]
        
        # Rotation (Euler Degrees -> Radians -> Matrix)
        rot_data = trans.get('rotation', {'x': 0, 'y': 0, 'z': 0})
        # Converting degrees to radians
        euler_angles = np.radians([rot_data['x'], rot_data['y'], rot_data['z']])
        # Create rotation matrix (Assuming standard XYZ order)
        matrix_rot = trimesh.transformations.euler_matrix(
            euler_angles[0], euler_angles[1], euler_angles[2], axes='sxyz'
        )
        
        # Scale
        scale_data = trans.get('scale', {'x': 1, 'y': 1, 'z': 1})
        matrix_scale = np.eye(4)
        matrix_scale[0,0] = scale_data['x']
        matrix_scale[1,1] = scale_data['y']
        matrix_scale[2,2] = scale_data['z']
        
        # Translation Matrix
        matrix_trans = trimesh.transformations.translation_matrix(translation)
        
        # Combine Matrices: Translation * Rotation * Scale
        # Note: Trimesh handles multiplication order for us usually, 
        # but logically it is T @ R @ S
        final_transform = trimesh.transformations.concatenate_matrices(
            matrix_trans, matrix_rot, matrix_scale
        )
        
        # Apply transform to mesh
        mesh.apply_transform(final_transform)
        
        # Add to scene
        scene.add_geometry(mesh, node_name=obj_id)

    # 3. Export
    # Ensure directory exists
    output_dir = os.path.dirname(glb_output_path)
    if output_dir and not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir, exist_ok=True)
            print(f"Created directory: {output_dir}")
        except OSError as e:
            print(f"Error creating directory: {e}")
            return

    print(f"Exporting GLB to: {glb_output_path}")
    scene.export(glb_output_path)
    print("Generation Complete.")

if __name__ == "__main__":
    # Create the data file (per requirement to load it externally)
    create_sample_data_file()
    
    # Run the generator
    process_dice_twin(INPUT_FILENAME, OUTPUT_PATH)