import os
import json
import base64
import cv2
import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

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

if __name__ == "__main__":
    # Simple test
    brain = GeminiBrain()
    print("Brain initialized. Key present:", bool(brain.api_key))
