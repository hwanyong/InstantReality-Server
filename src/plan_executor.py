"""
Server-side plan execution orchestrator.
src/plan_executor.py

Replaces client-driven HTTP polling (app.mjs runPlan/executeStep/_verifyStep)
with server-driven execution + WebSocket progress streaming.
"""

import asyncio
import json
import logging
import math
import time
import uuid

from lib.config_loader import load_execution_config
from robotics.ik_service import compute_ik_for_motion

logger = logging.getLogger(__name__)


class PlanExecutor:
    """
    Orchestrates robot plan execution on the server.
    Streams progress to clients via WebSocket broadcast.

    Replaces ~400 lines of client-side JavaScript:
      - runPlan()      → start() + _run_plan()
      - executeStep()  → _execute_step()
      - _verifyStep()  → _verify_step()
      - _moveTo()      → _move_to()
      - abortPlan()    → abort()
    """

    def __init__(self, brain, controller, ws_broadcast):
        """
        Args:
            brain: GeminiBrain instance (execute_with_tools, verify_action)
            controller: RobotController instance (move_to_pulses, open/close_gripper, etc.)
            ws_broadcast: async function(message_dict) to broadcast to all WS clients
        """
        self.brain = brain
        self.controller = controller
        self.ws_broadcast = ws_broadcast
        self._active_task = None
        self._aborted = False
        self._last_move_args = None  # Tracks last move position for safe approach

    async def start(self, instruction):
        """
        Generate plan and start async execution.
        Returns plan_id immediately; execution runs in background.
        """
        config = load_execution_config()
        plan_id = str(uuid.uuid4())[:8]

        # Capture TopView frame for plan generation
        topview_frame = self._capture_topview()
        if topview_frame is None:
            await self._broadcast("plan:error", {
                "plan_id": plan_id,
                "error": "Failed to capture TopView camera frame"
            })
            return {"plan_id": plan_id, "error": "No TopView frame"}

        # Generate plan (synchronous AI call)
        plan = await asyncio.to_thread(
            self.brain.execute_with_tools, topview_frame, instruction
        )

        if plan.get("error"):
            await self._broadcast("plan:error", {
                "plan_id": plan_id,
                "error": plan["error"]
            })
            return {"plan_id": plan_id, "error": plan["error"]}

        steps = plan.get("steps", [])
        if not steps:
            await self._broadcast("plan:error", {
                "plan_id": plan_id,
                "error": "No steps generated"
            })
            return {"plan_id": plan_id, "error": "No steps generated"}

        # Broadcast plan to clients
        await self._broadcast("plan:ready", {
            "plan_id": plan_id,
            "steps": steps,
            "summary": instruction,
            "step_count": len(steps)
        })

        # Start async execution
        self._aborted = False
        self._last_move_args = None
        self._active_task = asyncio.create_task(
            self._run_plan(plan_id, steps, config)
        )

        return {"plan_id": plan_id, "step_count": len(steps)}

    async def abort(self):
        """Immediately abort current execution."""
        self._aborted = True
        self.controller.release_all()
        logger.info("[PlanExecutor] Abort requested — servos released")

    # ─────────────────────────────────────────────────────────────────────
    # Internal: Plan execution loop
    # ─────────────────────────────────────────────────────────────────────

    async def _run_plan(self, plan_id, steps, config):
        """Main execution loop — runs as asyncio.Task."""
        start_time = time.time()
        exec_cfg = config.get("execution", {})
        step_delay = exec_cfg.get("step_delay_ms", 500) / 1000.0

        # Phase 0: Connect + Home
        if exec_cfg.get("auto_connect", True):
            if not self.controller.is_connected():
                success = self.controller.connect()
                if not success:
                    await self._broadcast("plan:failed", {
                        "plan_id": plan_id,
                        "error": "Failed to connect to robot"
                    })
                    return

        if exec_cfg.get("home_before_plan", True):
            self.controller.go_home(3.0)

        # Phase 1: Execute steps
        for i, step in enumerate(steps):
            if self._aborted:
                await self._broadcast("plan:aborted", {
                    "plan_id": plan_id,
                    "reason": "User abort"
                })
                return

            await self._broadcast("step:start", {
                "plan_id": plan_id,
                "index": i,
                "tool": step.get("tool"),
                "args": step.get("args", {}),
                "description": step.get("description", "")
            })

            # Execute step
            result = await asyncio.to_thread(self._execute_step, step, config)

            if result.get("success") == False:
                await self._broadcast("step:failed", {
                    "plan_id": plan_id,
                    "index": i,
                    "error": result.get("error", "Unknown")
                })
                break

            # Verify step
            verify_result = await self._verify_step(plan_id, i, step, config)

            if self._aborted:
                await self._broadcast("plan:aborted", {
                    "plan_id": plan_id,
                    "reason": "User abort during verification"
                })
                return

            await self._broadcast("step:done", {
                "plan_id": plan_id,
                "index": i,
                "verified": verify_result.get("verified", True)
            })

            await asyncio.sleep(step_delay)

        # Phase 2: Disconnect
        if exec_cfg.get("auto_disconnect", True):
            self.controller.disconnect()

        elapsed = round(time.time() - start_time, 1)
        if not self._aborted:
            await self._broadcast("plan:complete", {
                "plan_id": plan_id,
                "total_time_sec": elapsed
            })

        logger.info(f"[PlanExecutor] Plan {plan_id} completed in {elapsed}s")

    # ─────────────────────────────────────────────────────────────────────
    # Internal: Step execution (ported from app.mjs executeStep)
    # ─────────────────────────────────────────────────────────────────────

    def _execute_step(self, step, config):
        """Execute a single plan step. Runs in thread."""
        tool = step.get("tool")
        args = step.get("args", {})
        safety = config.get("safety", {})
        safe_height = safety.get("safe_height_mm", 100)

        if tool == "move_arm":
            return self._execute_move_arm(args, safe_height, config)
        elif tool == "open_gripper":
            return self._execute_gripper(args, "open")
        elif tool == "close_gripper":
            return self._execute_gripper(args, "close")
        elif tool == "go_home":
            return self._execute_go_home(args, safe_height)
        else:
            return {"success": False, "error": f"Unknown tool: {tool}"}

    def _execute_move_arm(self, args, safe_height, config):
        """3-Phase Safe Approach: ascend → horizontal → descend."""
        safety = config.get("safety", {})
        min_z = safety.get("min_z_mm", 5)

        target_x = float(args.get("x", 0))
        target_y = float(args.get("y", 0))
        target_z = max(min_z, float(args.get("z", 1)))
        arm = args.get("arm", "auto")
        motion_time = float(args.get("motion_time", 2.0))
        orientation = args.get("orientation", None)

        # Phase 0: Ascend from previous position
        if self._last_move_args:
            prev = self._last_move_args
            self._move_to(prev["x"], prev["y"], safe_height, prev["arm"], 1.0)

        # Phase 1: Approach — move to target XY at safe height
        self._move_to(target_x, target_y, safe_height, arm, 1.0, orientation)

        # Phase 2: Descend — lower to target Z
        result = self._move_to(target_x, target_y, target_z, arm, motion_time, orientation)

        # Track position for next ascend + verification
        self._last_move_args = {
            "x": target_x, "y": target_y, "arm": arm,
            "yaw": result.get("yaw_deg", 0)
        }

        return result

    def _execute_gripper(self, args, action):
        """Open or close gripper."""
        arm = args.get("arm", "right")
        if action == "open":
            self.controller.open_gripper(arm)
        else:
            self.controller.close_gripper(arm)
        return {"success": True, "arm": arm, "action": action}

    def _execute_go_home(self, args, safe_height):
        """Safety: ascend before homing."""
        if self._last_move_args:
            prev = self._last_move_args
            self._move_to(prev["x"], prev["y"], safe_height, prev["arm"], 1.0)
            self._last_move_args = None

        motion_time = float(args.get("motion_time", 3.0))
        success = self.controller.go_home(motion_time)
        return {"success": success}

    def _move_to(self, x, y, z, arm, motion_time, orientation=None):
        """
        Low-level move command — replaces app.mjs _moveTo().
        Uses IK service + RobotController directly (no HTTP).
        """
        config = load_execution_config()
        min_z = config.get("safety", {}).get("min_z_mm", 5)
        z = max(min_z, z)

        # Normalize arm name (same as robot_api.py handle_move_to)
        if arm == "auto":
            arm_name = "left_arm" if x < 0 else "right_arm"
        elif arm == "left":
            arm_name = "left_arm"
        elif arm == "right":
            arm_name = "right_arm"
        else:
            arm_name = arm

        result = compute_ik_for_motion(x, y, z, arm_name, orientation)
        success = self.controller.move_to_pulses(result["targets"], motion_time, wait=True)

        return {
            "success": success,
            "arm": arm_name,
            "yaw_deg": result.get("yaw_deg", 0),
            "valid": result.get("valid", False)
        }

    # ─────────────────────────────────────────────────────────────────────
    # Internal: Step verification (ported from app.mjs _verifyStep)
    # ─────────────────────────────────────────────────────────────────────

    async def _verify_step(self, plan_id, step_index, step, config):
        """Verify step and apply corrections if needed."""
        tool = step.get("tool")
        args = step.get("args", {})

        # Only verify move_arm and close_gripper
        if tool != "move_arm" and tool != "close_gripper":
            return {"verified": True}

        arm = args.get("arm") or (self._last_move_args or {}).get("arm") or "right"
        step_type = "move_arm" if tool == "move_arm" else "gripper"
        context = step.get("description", tool)
        verification = config.get("verification", {})

        if step_type == "move_arm":
            v_cfg = verification.get("position", {})
        else:
            v_cfg = verification.get("gripper", {})

        max_retries = v_cfg.get("max_retries", 3)

        for retry in range(max_retries):
            if self._aborted:
                return {"verified": False, "aborted": True}

            # Capture arm camera frame
            frame = self._capture_arm_camera(arm)
            if frame is None:
                logger.warning(f"[PlanExecutor] No arm camera frame for {arm}")
                return {"verified": True}  # Skip verification if no camera

            # AI verification
            v_result = await asyncio.to_thread(
                self.brain.verify_action, frame, step_type, context
            )

            if v_result.get("verified"):
                return {"verified": True, "description": v_result.get("description", "")}

            # Position correction
            if step_type == "move_arm" and v_result.get("offset"):
                correction = await self._apply_position_correction(
                    plan_id, step_index, retry, v_result, v_cfg, args
                )
                if correction.get("within_tolerance"):
                    return {"verified": True}
                continue  # Re-verify after correction

            # Gripper retry
            if step_type == "gripper" and not v_result.get("verified"):
                await self._retry_grip(
                    plan_id, step_index, retry, step, config, arm
                )
                continue  # Re-verify after retry

            return {"verified": False, "description": v_result.get("description", "")}

        return {"verified": False, "description": "Max retries exceeded"}

    async def _apply_position_correction(self, plan_id, step_index, retry, v_result, v_cfg, args):
        """Apply damped position correction (ported from app.mjs L607-629)."""
        offset = v_result.get("offset", {})
        dx = float(offset.get("dx", 0))
        dy = float(offset.get("dy", 0))

        # Camera Y is inverted relative to robot Y
        cam_dy = -dy

        # Tolerance check
        tolerance = v_cfg.get("tolerance_mm", 3.0)
        offset_mag = math.sqrt(dx * dx + dy * dy)
        if offset_mag < tolerance:
            return {"within_tolerance": True}

        # Camera-to-robot 2D rotation by -yaw + damping
        damping = v_cfg.get("damping_factor", 0.5)
        yaw_rad = -(self._last_move_args.get("yaw", 0) if self._last_move_args else 0) * math.pi / 180
        robot_dx = (dx * math.cos(yaw_rad) - cam_dy * math.sin(yaw_rad)) * damping
        robot_dy = (dx * math.sin(yaw_rad) + cam_dy * math.cos(yaw_rad)) * damping

        new_x = (self._last_move_args.get("x", 0) if self._last_move_args else 0) + robot_dx
        new_y = (self._last_move_args.get("y", 0) if self._last_move_args else 0) + robot_dy

        logger.info(f"[PlanExecutor] Position correction: cam({dx},{dy}) → robot({robot_dx:.1f},{robot_dy:.1f})")

        await self._broadcast("step:corrected", {
            "plan_id": plan_id,
            "index": step_index,
            "attempt": retry + 1,
            "offset": {"dx": round(robot_dx, 1), "dy": round(robot_dy, 1)}
        })

        # Apply correction
        result = await asyncio.to_thread(
            self._move_to, new_x, new_y, float(args.get("z", 1)), 
            self._last_move_args.get("arm", "right") if self._last_move_args else "right",
            1.0
        )
        if self._last_move_args:
            self._last_move_args["x"] = new_x
            self._last_move_args["y"] = new_y
            self._last_move_args["yaw"] = result.get("yaw_deg", self._last_move_args.get("yaw", 0))

        return {"within_tolerance": False}

    async def _retry_grip(self, plan_id, step_index, retry, step, config, arm):
        """Gripper retry sequence (ported from app.mjs L632-682)."""
        safety = config.get("safety", {})
        safe_height = safety.get("safe_height_mm", 100)

        logger.info(f"[PlanExecutor] Grip retry {retry + 1}")

        # 1. Re-open gripper
        await asyncio.to_thread(self.controller.open_gripper, arm)

        # 2. Ascend to safe height
        if self._last_move_args:
            await asyncio.to_thread(
                self._move_to, self._last_move_args["x"], self._last_move_args["y"],
                safe_height, self._last_move_args["arm"], 1.0
            )

        # 3. Re-analyze via TopView (if configured)
        if not config.get("verification", {}).get("gripper", {}).get("re_analyze_on_fail", True):
            return

        topview_frame = self._capture_topview()
        if topview_frame is None:
            return

        context = step.get("description", "")
        analysis = await asyncio.to_thread(
            self.brain.analyze_frame, topview_frame, context
        )

        if not analysis or not analysis.get("target_detected"):
            logger.warning("[PlanExecutor] Object re-detection failed")
            return

        coords = analysis.get("coordinates")
        if not coords:
            return

        # 4. Convert Gemini coords to robot mm
        from lib.coordinate_transform import gemini_to_robot
        from calibration_manager import get_calibration_for_role

        cal = get_calibration_for_role("TopView")
        if not cal or not cal.get("homography_matrix"):
            logger.warning("[PlanExecutor] No calibration data for coord conversion")
            return

        H = cal["homography_matrix"]
        res = cal.get("resolution", {})
        width = res.get("width", 1920)
        height = res.get("height", 1080)

        gy, gx = coords[0], coords[1]
        robot = gemini_to_robot(gx, gy, H, width, height)
        new_x = round(robot["x"], 1)
        new_y = round(robot["y"], 1)
        new_arm = "left" if new_x < 0 else "right"

        logger.info(f"[PlanExecutor] Re-position: ({new_x}, {new_y}) arm={new_arm}")

        # 5. Re-position (approach + descend)
        orientation = step.get("args", {}).get("orientation")
        await asyncio.to_thread(
            self._move_to, new_x, new_y, safe_height, new_arm, 1.0, orientation
        )
        target_z = float(step.get("args", {}).get("z", 1))
        result = await asyncio.to_thread(
            self._move_to, new_x, new_y, target_z, new_arm, 1.5, orientation
        )
        self._last_move_args = {
            "x": new_x, "y": new_y, "arm": new_arm,
            "yaw": result.get("yaw_deg", 0)
        }

        # 6. Close gripper again
        await asyncio.to_thread(self.controller.close_gripper, new_arm)

        await self._broadcast("step:corrected", {
            "plan_id": plan_id,
            "index": step_index,
            "attempt": retry + 1,
            "offset": {"description": "Grip retry with re-analysis"}
        })

    # ─────────────────────────────────────────────────────────────────────
    # Internal: Camera helpers
    # ─────────────────────────────────────────────────────────────────────

    def _capture_topview(self):
        """Capture frame from TopView camera."""
        from camera_mapping import get_index_by_role
        from camera_manager import get_camera
        idx = get_index_by_role("TopView")
        if idx is None:
            logger.warning("[PlanExecutor] TopView camera not found")
            return None
        cam = get_camera(idx)
        if cam is None:
            return None
        frame, _ = cam.get_frames()
        return frame

    _ARM_ROLE_MAP = {
        "right": "RightRobot",
        "left": "LeftRobot",
        "right_arm": "RightRobot",
        "left_arm": "LeftRobot",
    }

    def _capture_arm_camera(self, arm):
        """Capture frame from arm-mounted camera."""
        from camera_mapping import get_index_by_role
        from camera_manager import get_camera
        role = self._ARM_ROLE_MAP.get(arm, "RightRobot")
        idx = get_index_by_role(role)
        if idx is None:
            return None
        cam = get_camera(idx)
        if cam is None:
            return None
        frame, _ = cam.get_frames()
        return frame

    # ─────────────────────────────────────────────────────────────────────
    # Internal: WebSocket broadcast helper
    # ─────────────────────────────────────────────────────────────────────

    async def _broadcast(self, msg_type, data):
        """Send typed WebSocket message to all clients."""
        message = {"type": msg_type, **data}
        await self.ws_broadcast(message)
        logger.debug(f"[PlanExecutor] WS: {msg_type} → {json.dumps(data)[:200]}")
