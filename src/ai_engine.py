import os
import json
import base64
import cv2
import numpy as np
from google import genai
from google.genai import types

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
            
        self.model_name = os.environ.get("GEMINI_MODEL", "gemini-1.5-pro-latest")

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

if __name__ == "__main__":
    # Simple test
    brain = GeminiBrain()
    print("Brain initialized. Key present:", bool(brain.api_key))
