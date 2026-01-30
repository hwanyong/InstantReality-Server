"""
Gemini Robotics ER-1.5 API Client

Provides interface to Gemini Robotics model for:
- Vision-based object detection
- Target coordinate extraction
- Gripper position detection for calibration
"""

import os
import json
import re
from typing import Optional, Dict


class GeminiRoboticsClient:
    """
    Client for Gemini Robotics ER-1.5 API.
    
    Uses google-genai SDK to communicate with the model.
    Returns normalized coordinates [y, x] in 0-1000 range.
    """
    
    MODEL_ID = "gemini-robotics-er-1.5-preview"
    
    def __init__(self, api_key: str = None):
        """
        Initialize Gemini Robotics client.
        
        Args:
            api_key: Gemini API key (uses GEMINI_API_KEY env var if not provided)
        """
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.client = None
        self._init_client()
    
    def _init_client(self):
        """Initialize the google-genai client."""
        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
            self.genai = genai
        except ImportError:
            raise ImportError("google-genai package not installed. Run: pip install google-genai")
    
    async def get_target_coordinates(
        self,
        image_bytes: bytes,
        target_object: str,
        thinking_budget: int = 0
    ) -> Dict:
        """
        Analyze image and return target object coordinates.
        
        Args:
            image_bytes: JPEG image bytes
            target_object: Object to find (e.g., "red block", "gripper tip")
            thinking_budget: 0 for fast response, 1024 for complex spatial reasoning
        
        Returns:
            {
                "point": [y, x],  # 0-1000 normalized
                "label": str,
                "description": str,
                "orientation": str  # Optional: "left", "right", etc.
            }
        """
        from google.genai import types
        
        prompt = f"""You are a robot vision system. Analyze this image and find: "{target_object}"

Output Requirements:
- Return ONLY valid JSON (no markdown, no explanation)
- Format: {{"point": [y, x], "label": "object name", "description": "brief description"}}
- Coordinates are normalized 0-1000 where [0,0] is top-left, [1000,1000] is bottom-right
- For gripper/robot parts, include "orientation" field if applicable

Example output:
{{"point": [456, 723], "label": "red block", "description": "small red cube on table"}}

Find: {target_object}"""

        config = types.GenerateContentConfig(
            temperature=0.3,
            thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget)
        )
        
        response = self.client.models.generate_content(
            model=self.MODEL_ID,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                prompt
            ],
            config=config
        )
        
        # Parse response
        return self._parse_json_response(response.text)
    
    async def get_gripper_position(self, image_bytes: bytes) -> Dict:
        """
        Detect current gripper tip position in image.
        
        Uses specialized prompt for precise gripper tip localization
        during calibration.
        
        Args:
            image_bytes: JPEG image bytes
        
        Returns:
            {"point": [y, x], "label": "gripper tip", ...}
        """
        from google.genai import types
        
        prompt = """You are a calibration vision system. Find the EXACT TIP of the robot gripper.

Look for:
- The robot arm's end effector (gripper)
- Identify the very TIP CENTER where it would contact an object

Output Requirements:
- Return ONLY valid JSON
- Format: {"point": [y, x], "label": "gripper tip", "confidence": 0.0-1.0}
- Coordinates normalized 0-1000 where [0,0] is top-left

CRITICAL: Point must be the gripper's TIP CENTER, not the gripper body."""

        config = types.GenerateContentConfig(
            temperature=0.2,  # Lower for precision
            thinking_config=types.ThinkingConfig(thinking_budget=0)
        )
        
        response = self.client.models.generate_content(
            model=self.MODEL_ID,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                prompt
            ],
            config=config
        )
        
        return self._parse_json_response(response.text)
    
    async def get_robot_base_position(self, image_bytes: bytes) -> Dict:
        """
        Detect robot base mount position in image.
        
        Uses specialized prompt for base localization during calibration.
        
        Args:
            image_bytes: JPEG image bytes
        
        Returns:
            {"point": [y, x], "label": "robot base", ...}
        """
        from google.genai import types
        
        prompt = """You are a calibration vision system. Find the ROBOT BASE MOUNT POINT.

Look for:
- Where the robot arm is mounted to the table/surface
- The center of the base mounting plate/joint
- This is the fixed anchor point of the robot

Output Requirements:
- Return ONLY valid JSON
- Format: {"point": [y, x], "label": "robot base", "confidence": 0.0-1.0}
- Coordinates normalized 0-1000 where [0,0] is top-left

CRITICAL: Point must be the CENTER of the base mount, not the arm body."""

        config = types.GenerateContentConfig(
            temperature=0.2,
            thinking_config=types.ThinkingConfig(thinking_budget=0)
        )
        
        response = self.client.models.generate_content(
            model=self.MODEL_ID,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                prompt
            ],
            config=config
        )
        
        return self._parse_json_response(response.text)
    
    async def analyze_object_for_grasping(
        self,
        image_bytes: bytes,
        target_object: str
    ) -> Dict:
        """
        Analyze object with full spatial reasoning for optimal grasping.
        
        Args:
            image_bytes: JPEG image bytes
            target_object: Object to grasp
        
        Returns:
            {
                "point": [y, x],
                "label": str,
                "orientation": str,  # "horizontal", "vertical", etc.
                "grasp_approach": str,  # "top", "side", etc.
                "confidence": float
            }
        """
        from google.genai import types
        
        prompt = f"""You are a robot vision system planning a grasp.
Analyze this image to determine the optimal grasping strategy for: "{target_object}"

Output Requirements:
- Return ONLY valid JSON
- Format: {{
    "point": [y, x],
    "label": "object name",
    "orientation": "horizontal|vertical|angled",
    "grasp_approach": "top|side|front",
    "handle_direction": "left|right|up|down|none",
    "confidence": 0.0-1.0
}}
- Coordinates normalized 0-1000

Find and analyze: {target_object}"""

        config = types.GenerateContentConfig(
            temperature=0.3,
            thinking_config=types.ThinkingConfig(thinking_budget=1024)  # Use thinking for complex analysis
        )
        
        response = self.client.models.generate_content(
            model=self.MODEL_ID,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                prompt
            ],
            config=config
        )
        
        return self._parse_json_response(response.text)
    
    def _parse_json_response(self, text: str) -> Dict:
        """
        Parse JSON from Gemini response, handling markdown code blocks.
        
        Args:
            text: Raw response text
        
        Returns:
            Parsed JSON dict
        """
        # Remove markdown code block if present
        clean_text = text.strip()
        
        # Handle ```json ... ``` blocks
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', clean_text)
        if json_match:
            clean_text = json_match.group(1)
        
        # Try to parse JSON
        try:
            return json.loads(clean_text)
        except json.JSONDecodeError:
            # Fallback: try to extract JSON object
            obj_match = re.search(r'\{[\s\S]*\}', clean_text)
            if obj_match:
                return json.loads(obj_match.group())
            raise ValueError(f"Could not parse JSON from response: {text[:200]}")
    
    @staticmethod
    def encode_frame(frame_bgr) -> bytes:
        """
        Encode OpenCV BGR frame to JPEG bytes.
        
        Args:
            frame_bgr: OpenCV BGR image (numpy array)
        
        Returns:
            JPEG bytes
        """
        import cv2
        _, buffer = cv2.imencode('.jpg', frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return buffer.tobytes()
