import trimesh
import numpy as np
import json
import os

# Configuration
INPUT_FILENAME = './output/51_step5_vr.json'
OUTPUT_PATH = './output/51_dice_digital_twin.glb'

def get_color_rgba(color_name):
    """Maps string color names to RGBA 0-255 values."""
    cmap = {
        'red':   [255, 0, 0, 255],
        'white': [240, 240, 240, 255], # Slightly off-white for better visibility
        'blue':  [0, 0, 255, 255],
        'green': [0, 255, 0, 255],
        "yellow": [255, 255, 0, 255],
        "orange": [255, 165, 0, 255],
        "pink":   [255, 192, 203, 255],
        # 'black': [20, 20, 20, 255],
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
        mesh = trimesh.creation.box(extents=[0.02, 0.02, 0.02])
        
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
        # mesh.apply_transform(final_transform) #메쉬의 점(Vertex) 자체를 이동시켜 담고 있는 그릇(Node)은 (0,0,0)에 위치
        
        # Add to scene
        # scene.add_geometry(mesh, node_name=obj_id)
        scene.add_geometry(mesh, node_name=obj_id, transform=final_transform) #메쉬 자체를 변형하지 말고, 메쉬를 담는 노드(Node)에 변환 정보를 주기

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
    # Run the generator
    if os.path.exists(INPUT_FILENAME):
        process_dice_twin(INPUT_FILENAME, OUTPUT_PATH)
        print(f"🎉 GLB 생성 완료! 저장 경로: {OUTPUT_PATH}")
    else:
        print(f"⚠️ 오류: 데이터 파일이 없습니다. {INPUT_FILENAME}")