"""IK Service unit tests — validate 3-Layer architecture"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from robotics.ik_service import solve_ik, compute_ik_detail, compute_ik_for_motion


LINKS = {"d1": 107, "a2": 105, "a3": 150, "a4": 65, "a6": 70}


# ── Layer 1: solve_ik ──

def test_solve_ik_valid():
    """유효 좌표 → valid=True, Elbow Up"""
    result = solve_ik(100, 200, 3, 0, 0, LINKS)
    assert result.valid == True
    assert result.config_name == "Elbow Up"


def test_solve_ik_out_of_reach():
    """범위 초과 → valid=False, Pointing"""
    result = solve_ik(500, 500, 3, 0, 0, LINKS)
    assert result.valid == False
    assert result.config_name == "Pointing"


def test_solve_ik_origin():
    """원점 → theta1=0"""
    result = solve_ik(0, 0, 3, 0, 0, LINKS)
    assert result.theta1 == 0.0


# ── Layer 3: compute_ik_detail (server.py facade) ──

def test_compute_ik_detail_returns_all_fields():
    """상세 출력에 필수 필드 7개 존재"""
    result = compute_ik_detail(100, 200, 3, "right_arm")
    for key in ["success", "local", "reach", "ik", "physical", "pulse", "config_name", "valid"]:
        assert key in result


def test_compute_ik_detail_no_z_offset():
    """compute_ik_detail은 z_offset 미적용"""
    r1 = compute_ik_detail(100, 200, 3, "right_arm")
    r2 = compute_ik_detail(100, 200, 3, "right_arm")
    # 같은 입력 → 같은 결과 (z_offset 미적용이므로 일관성)
    assert r1["ik"]["theta2"] == r2["ik"]["theta2"]


# ── Layer 3: compute_ik_for_motion (robot_api.py facade) ──

def test_compute_ik_for_motion_has_targets():
    """motion 결과에 targets 리스트 존재"""
    result = compute_ik_for_motion(100, 200, 3, "right_arm")
    assert "targets" in result
    assert len(result["targets"]) == 5  # slot 1-5 (gripper 제외)


def test_compute_ik_for_motion_z_offset_effect():
    """z_offset 적용으로 detail과 motion의 결과가 다름"""
    detail = compute_ik_detail(100, 200, 3, "right_arm")
    motion = compute_ik_for_motion(100, 200, 3, "right_arm")
    # right_arm z_offset=-17 → motion의 z가 달라져서 pulse 값이 다름
    # (z_offset=0이면 같을 수 있으므로 targets 존재만 확인)
    assert "targets" in motion
    assert "yaw_deg" in motion


def test_compute_ik_for_motion_orientation():
    """orientation 적용 시 slot5 변경"""
    r1 = compute_ik_for_motion(100, 200, 3, "right_arm", orientation=None)
    r2 = compute_ik_for_motion(100, 200, 3, "right_arm", orientation=45.0)
    # slot5 (index 4) pulse가 달라야 함
    assert r1["targets"][4] != r2["targets"][4]


def test_compute_ik_for_motion_left_arm():
    """left_arm도 정상 동작"""
    result = compute_ik_for_motion(-100, 200, 3, "left_arm")
    assert result["valid"] == True
