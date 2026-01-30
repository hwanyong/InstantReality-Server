import os
import json
import base64
import cv2
import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()


class ROIManager:
    """Manages Region of Interest cropping and coordinate transformation"""
    
    def __init__(self, roi_config=None):
        if roi_config is None:
            roi_config = {}
        self.ymin = roi_config.get("ymin", 0)
        self.xmin = roi_config.get("xmin", 0)
        self.ymax = roi_config.get("ymax", 1000)
        self.xmax = roi_config.get("xmax", 1000)
        self.roi_width = self.xmax - self.xmin
        self.roi_height = self.ymax - self.ymin
    
    def crop_roi(self, frame):
        """Crop ROI region from original frame"""
        h, w = frame.shape[:2]
        y1 = int(self.ymin / 1000 * h)
        x1 = int(self.xmin / 1000 * w)
        y2 = int(self.ymax / 1000 * h)
        x2 = int(self.xmax / 1000 * w)
        return frame[y1:y2, x1:x2].copy()
    
    def crop_box_with_margin(self, frame, box_2d, margin_ratio=0.25):
        """Crop around a bounding box with margin from original frame"""
        ymin, xmin, ymax, xmax = box_2d
        width = xmax - xmin
        height = ymax - ymin
        
        # Add margin
        new_xmin = max(0, xmin - width * margin_ratio)
        new_ymin = max(0, ymin - height * margin_ratio)
        new_xmax = min(1000, xmax + width * margin_ratio)
        new_ymax = min(1000, ymax + height * margin_ratio)
        
        # Convert to pixels
        h, w = frame.shape[:2]
        y1 = int(new_ymin / 1000 * h)
        x1 = int(new_xmin / 1000 * w)
        y2 = int(new_ymax / 1000 * h)
        x2 = int(new_xmax / 1000 * w)
        
        crop_info = {
            "crop_box": [new_ymin, new_xmin, new_ymax, new_xmax],
            "original_box": box_2d
        }
        return frame[y1:y2, x1:x2].copy(), crop_info
    
    def local_to_roi(self, local_point):
        """Transform local coordinates (from cropped ROI) to ROI-space coordinates"""
        local_y, local_x = local_point
        roi_x = self.xmin + (local_x * self.roi_width / 1000)
        roi_y = self.ymin + (local_y * self.roi_height / 1000)
        return [int(roi_y), int(roi_x)]
    
    def local_to_global(self, local_point, crop_box):
        """Transform local coordinates to global frame coordinates"""
        local_y, local_x = local_point
        crop_ymin, crop_xmin, crop_ymax, crop_xmax = crop_box
        crop_w = crop_xmax - crop_xmin
        crop_h = crop_ymax - crop_ymin
        
        global_x = crop_xmin + (local_x * crop_w / 1000)
        global_y = crop_ymin + (local_y * crop_h / 1000)
        return [int(global_y), int(global_x)]
    
    def transform_box_to_global(self, local_box, crop_box):
        """Transform a bounding box from local to global coordinates"""
        local_ymin, local_xmin, local_ymax, local_xmax = local_box
        
        top_left = self.local_to_global([local_ymin, local_xmin], crop_box)
        bottom_right = self.local_to_global([local_ymax, local_xmax], crop_box)
        
        return [top_left[0], top_left[1], bottom_right[0], bottom_right[1]]

class GeminiBrain:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            print("Warning: GEMINI_API_KEY not found in environment variables.")
            # We might want to load from a .env file explicitly if using python-dotenv
            # For now, we assume it's set or we'll fail later.
        
        self.client = None
        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"Failed to initialize Gemini Client: {e}")
        else:
            print("Gemini Client not initialized (Missing Key)")
            
        self.model_name = os.environ.get("GEMINI_MODEL", "gemini-robotics-er-1.5-preview")

    def analyze_frame(self, frame_bgr, instruction):
        """
        Analyzes a single frame (BGR numpy from OpenCV) with a text instruction.
        Returns a JSON object with the analysis result.
        """
        if not self.client:
            return {"error": "AI not initialized (Missing API Key). Please set GEMINI_API_KEY."}

        try:
            # 1. Convert BGR to RGB (Gemini expects RGB)
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            
            # 2. Encode to JPEG bytes
            success, buffer = cv2.imencode(".jpg", frame_rgb)
            if not success:
                return {"error": "Failed to encode image"}
            
            image_bytes = buffer.tobytes()
            
            # 3. Construct Prompt
            # We want structured output if possible.
            prompt = f"""
            You are a robot control assistant.
            The user instruction is: "{instruction}"
            
            Analyze the image and identify the target object(s) relevant to the instruction.
            Return the normalized center coordinates [y, x] (0-1000) for the target.
            
            Output strictly in JSON format:
            {{
                "target_detected": true/false,
                "coordinates": [y, x],
                "description": "brief description of what you found"
            }}
            """
            
            # 4. Call API
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[
                    prompt,
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            
            # 5. Parse Response
            result = json.loads(response.text)
            return result

        except Exception as e:
            print(f"AI Analysis Error: {e}")
            return {"error": str(e)}

    def _encode_frame(self, frame_bgr):
        """Convert BGR frame to JPEG bytes for Gemini API"""
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        success, buffer = cv2.imencode(".jpg", frame_rgb)
        if not success:
            return None
        return buffer.tobytes()

    def scan_scene(self, topview_frame, quarterview_frame=None):
        """
        Scan entire scene for object inventory.
        Used at server initialization or reset.
        Returns list of detected objects with bounding boxes.
        """
        if not self.client:
            return {"error": "AI not initialized", "objects": []}

        try:
            # Encode images
            topview_bytes = self._encode_frame(topview_frame)
            if topview_bytes is None:
                return {"error": "Failed to encode TopView", "objects": []}

            contents = []
            
            # Build prompt for scene inventory with Master-Reference strategy
            prompt = """You are a Robotics Vision System analyzing a dual-camera workspace.

Input Context:
1. Image 1 (MASTER): TOP-DOWN overhead view.
   - The robot base is at the BOTTOM of this image.
   - Use this image EXCLUSIVELY for all [y, x] coordinate calculations.
"""
            if quarterview_frame is not None:
                quarterview_bytes = self._encode_frame(quarterview_frame)
                if quarterview_bytes:
                    prompt += """
2. Image 2 (REFERENCE): QUARTER VIEW from front-to-back perspective (45°).
   - Camera looks from the operator's position toward the robot.
   - Use this to understand object height, depth, and verify occluded objects.
"""
            
            prompt += """
Task: Detect ALL graspable objects on the workspace table.

Output Format (JSON):
{
    "objects": [
        {
            "label": "descriptive name (e.g., red cup, blue marker)",
            "box_2d": [ymin, xmin, ymax, xmax],
            "grasp_strategy": "vertical" or "horizontal",
            "orientation": "brief description from angled view"
        }
    ]
}

Rules:
- Coordinates MUST be normalized 0-1000 based on Image 1 (Top-Down) ONLY.
- Do NOT detect robot arms or fixed equipment.
- Distinguish identical items by color or relative position (e.g., "left red cup", "right red cup").
- If an object is partially occluded in Image 1, use Image 2 to verify its existence.
- Include ALL visible moveable objects - do not skip any.
"""
            
            # Add images to contents
            contents.append(prompt)
            contents.append(types.Part.from_bytes(data=topview_bytes, mime_type="image/jpeg"))
            
            if quarterview_frame is not None:
                quarterview_bytes = self._encode_frame(quarterview_frame)
                if quarterview_bytes:
                    contents.append(types.Part.from_bytes(data=quarterview_bytes, mime_type="image/jpeg"))

            # Call API
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.5
                )
            )
            
            result = json.loads(response.text)
            return result

        except Exception as e:
            print(f"Scene Scan Error: {e}")
            return {"error": str(e), "objects": []}
    
    def scan_scene_with_roi(self, topview_frame, quarterview_frame=None, roi_config=None, precision=False):
        """
        2-Pass hierarchical scene analysis with ROI support.
        
        Phase 1: Scan ROI-cropped image for all objects
        Phase 2 (if precision=True): Refine each object with zoomed crop
        
        Args:
            topview_frame: Original full-resolution top-view frame
            quarterview_frame: Optional quarter-view frame for context
            roi_config: ROI settings dict {ymin, xmin, ymax, xmax} (0-1000)
            precision: If True, perform 2-Pass analysis
            
        Returns:
            dict with "objects" list and analysis metadata
        """
        if not self.client:
            return {"error": "AI not initialized", "objects": []}
        
        roi_mgr = ROIManager(roi_config)
        
        # Crop ROI from original frame
        roi_frame = roi_mgr.crop_roi(topview_frame)
        
        # Resize for Phase 1 analysis (800px width)
        h, w = roi_frame.shape[:2]
        target_width = 800
        new_h = int(target_width * h / w)
        resized_roi = cv2.resize(roi_frame, (target_width, new_h))
        
        # Phase 1: Global scan on ROI
        print("[Phase 1] Scanning ROI for objects...")
        phase1_result = self.scan_scene(resized_roi, quarterview_frame)
        
        if "error" in phase1_result:
            return phase1_result
        
        objects = phase1_result.get("objects", [])
        print(f"[Phase 1] Found {len(objects)} objects")
        
        # Transform coordinates from ROI-local to global
        for obj in objects:
            if "box_2d" in obj:
                local_box = obj["box_2d"]
                # Transform from ROI-local (0-1000) to global (0-1000)
                global_box = roi_mgr.transform_box_to_global(
                    local_box, 
                    [roi_mgr.ymin, roi_mgr.xmin, roi_mgr.ymax, roi_mgr.xmax]
                )
                obj["box_2d"] = global_box
                obj["roi_local_box"] = local_box  # Keep original for debugging
        
        result = {
            "objects": objects,
            "roi_config": roi_config,
            "analysis_mode": "precision" if precision else "quick"
        }
        
        if not precision:
            return result
        
        # Phase 2: Precision analysis for each object
        print("[Phase 2] Performing precision analysis...")
        refined_objects = []
        
        for i, obj in enumerate(objects):
            if "box_2d" not in obj:
                refined_objects.append(obj)
                continue
            
            print(f"  Refining object {i+1}/{len(objects)}: {obj.get('label', 'unknown')}")
            
            # Crop with margin from original full-res frame
            cropped, crop_info = roi_mgr.crop_box_with_margin(
                topview_frame, 
                obj["box_2d"], 
                margin_ratio=0.25
            )
            
            # Analyze cropped region
            refined = self._refine_object(cropped, obj.get("label", "object"))
            
            if refined and "point" in refined:
                # Transform point from crop-local to global
                global_point = roi_mgr.local_to_global(
                    refined["point"],
                    crop_info["crop_box"]
                )
                obj["point"] = global_point
                obj["refined_details"] = refined.get("details", "")
            
            refined_objects.append(obj)
        
        result["objects"] = refined_objects
        print(f"[Phase 2] Refined {len(refined_objects)} objects")
        
        return result
    
    def _refine_object(self, cropped_frame, label):
        """
        Analyze a cropped region for precise object details.
        Returns center point and additional details.
        """
        if not self.client:
            return None
        
        try:
            image_bytes = self._encode_frame(cropped_frame)
            if image_bytes is None:
                return None
            
            prompt = f"""This is a zoomed-in view of a "{label}".
            
Task: Provide precise analysis of this object.

Output Format (JSON):
{{
    "point": [y, x],
    "details": "brief description of object properties"
}}

Rules:
- "point" is the normalized center coordinates [y, x] (0-1000) of the object.
- Focus on the main object, ignore background.
"""
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[
                    prompt,
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.3
                )
            )
            
            return json.loads(response.text)
        
        except Exception as e:
            print(f"Refine Error for {label}: {e}")
            return None

if __name__ == "__main__":
    # Simple test
    brain = GeminiBrain()
    print("Brain initialized. Key present:", bool(brain.api_key))
