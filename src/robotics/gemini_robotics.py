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
    
    async def measure_z_from_side(self, image_bytes: bytes) -> Dict:
        """
        Measure gripper height from side view (QuarterView).
        
        Uses QuarterView camera to estimate Z-height by measuring
        the vertical pixel position of the gripper tip.
        
        Args:
            image_bytes: JPEG image from QuarterView camera
        
        Returns:
            {
                "gripper_y_pixel": int,  # Y pixel position (0=top, 1000=bottom)
                "estimated_height": str,  # "high", "medium", "low", "ground"
                "confidence": float
            }
        """
        from google.genai import types
        
        prompt = """You are a calibration vision system measuring gripper HEIGHT from a SIDE VIEW.

This is a side/quarter view of the robot arm. Measure where the gripper tip is vertically.

Output Requirements:
- Return ONLY valid JSON
- Format: {
    "gripper_y_pixel": <0-1000 where 0=top, 1000=bottom>,
    "estimated_height": "high|medium|low|ground",
    "confidence": 0.0-1.0
}

Height estimation guide:
- high: Gripper is in upper 1/4 of image (0-250)
- medium: Gripper is in second 1/4 (250-500)
- low: Gripper is in third 1/4 (500-750)
- ground: Gripper is in bottom 1/4 (750-1000) or touching surface

CRITICAL: Focus on the VERTICAL position of the gripper tip only."""

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
    
    async def get_gripper_tip_precise(self, image_bytes: bytes) -> Dict:
        """
        Get precise gripper tip position from RobotCamera (close-up view).
        
        Uses RightRobot or LeftRobot camera for high-precision tip detection.
        
        Args:
            image_bytes: JPEG image from RobotCamera
        
        Returns:
            {
                "point": [y, x],  # 0-1000 normalized
                "tip_visible": bool,
                "confidence": float,
                "tip_state": str  # "open", "closed", "unknown"
            }
        """
        from google.genai import types
        
        prompt = """You are a precision calibration system viewing the gripper from a CLOSE-UP camera.

This is a close-up view of the robot gripper. Find the EXACT CENTER of the gripper tip.

Output Requirements:
- Return ONLY valid JSON
- Format: {
    "point": [y, x],
    "tip_visible": true/false,
    "confidence": 0.0-1.0,
    "tip_state": "open|closed|unknown"
}
- Coordinates normalized 0-1000 where [0,0] is top-left

CRITICAL: 
1. Point must be the CENTER of the gripper tip opening
2. If gripper is closed, return center of closed tips
3. tip_visible = false if gripper is not clearly visible"""

        config = types.GenerateContentConfig(
            temperature=0.1,  # Very low for maximum precision
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
    
    async def verify_action_success(
        self,
        before_image: bytes,
        after_image: bytes,
        expected_change: str
    ) -> Dict:
        """
        Visually verify if action was successful by comparing before/after images.
        
        Args:
            before_image: Image before action (JPEG bytes)
            after_image: Image after action (JPEG bytes)
            expected_change: Description of expected change
        
        Returns:
            {"success": bool, "confidence": float, "reason": str, "detected_change": str}
        """
        from google.genai import types
        
        prompt = f"""You are a robot action verification system.

Compare the two images (BEFORE and AFTER) and determine if the expected action was successful.

Expected change: "{expected_change}"

Output Requirements:
- Return ONLY valid JSON
- Format: {{"success": true/false, "confidence": 0.0-1.0, "reason": "explanation", "detected_change": "what changed"}}

CRITICAL: If the object position hasn't changed significantly, return success=false."""

        config = types.GenerateContentConfig(
            temperature=0.2,
            thinking_config=types.ThinkingConfig(thinking_budget=512)
        )
        
        response = self.client.models.generate_content(
            model=self.MODEL_ID,
            contents=[
                "Image 1 (BEFORE):",
                types.Part.from_bytes(data=before_image, mime_type="image/jpeg"),
                "Image 2 (AFTER):",
                types.Part.from_bytes(data=after_image, mime_type="image/jpeg"),
                prompt
            ],
            config=config
        )
        
        return self._parse_json_response(response.text)
    
    async def analyze_with_self_correction(
        self,
        image_bytes: bytes,
        target_object: str,
        context: str = ""
    ) -> Dict:
        """
        Analyze with Code Execution enabled for self-correction.
        
        Args:
            image_bytes: JPEG image bytes
            target_object: Object to find
            context: Additional context
        
        Returns:
            {"point": [y, x], "label": str, "corrected": bool, "correction_reason": str}
        """
        from google.genai import types
        
        prompt = f"""You are a robot vision system with self-correction capability.

Find: "{target_object}"
{f'Context: {context}' if context else ''}

Use code execution to validate coordinates if needed.

Output: {{"point": [y, x], "label": "name", "corrected": true/false, "correction_reason": "reason"}}
Coordinates: 0-1000 normalized"""

        config = types.GenerateContentConfig(
            temperature=0.3,
            thinking_config=types.ThinkingConfig(thinking_budget=1024),
            tools=[types.Tool(code_execution=types.ToolCodeExecution())]
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

