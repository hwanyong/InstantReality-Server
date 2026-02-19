"""
Test script for Dual Reach Protocol kinematics implementation.
Verifies that compute_3d_reach produces expected values based on manual calculations.
"""
from servo_manager import ServoManager

def test_dual_reach():
    m = ServoManager()
    
    # Expected values from manual calculations (based on kinematics prompt)
    expected = {
        "1": {"stance": "open", "internal_angle": 173.6, "r_3d": 254.6},
        "2": {"stance": "closed", "internal_angle": 93.8, "r_3d": 188.7},
        "3": {"stance": "closed", "internal_angle": 73.2, "r_3d": 156.3},
        "4": {"stance": "open", "internal_angle": 167.3, "r_3d": 253.5}
    }
    
    print("=" * 60)
    print("Dual Reach Protocol Verification Test")
    print("=" * 60)
    
    all_passed = True
    
    for vid in range(1, 5):
        vertex = m.config.get("vertices", {}).get(str(vid))
        if not vertex:
            print(f"\n❌ Vertex {vid}: Not defined")
            continue
            
        owner = vertex.get("owner")
        result = m.compute_3d_reach(owner, vertex)
        exp = expected[str(vid)]
        
        print(f"\n=== Vertex {vid} ({owner}) ===")
        print(f"Yaw Delta:      {result['angles']['yaw_delta']:.1f}°")
        print(f"Shoulder Delta: {result['angles']['shoulder_delta']:.1f}°")
        print(f"Elbow Delta:    {result['angles']['elbow_delta']:.1f}°")
        print(f"Stance:         {result['stance']} (expected: {exp['stance']})")
        print(f"Internal Angle: {result['angles']['internal_angle']:.1f}° (expected: ~{exp['internal_angle']}°)")
        print(f"R_3d:           {result['r_3d']:.1f} mm (expected: ~{exp['r_3d']} mm)")
        print(f"R_xy:           {result['r_xy']:.1f} mm")
        print(f"Z_final:        {result['z_final']:.1f} mm")
        
        # Check stance
        if result["stance"] != exp["stance"]:
            print(f"⚠️ Stance MISMATCH!")
            all_passed = False
        else:
            print(f"✅ Stance OK")
        
        # Check internal angle (allow 2 degree tolerance)
        if abs(result["angles"]["internal_angle"] - exp["internal_angle"]) > 2:
            print(f"⚠️ Internal Angle MISMATCH!")
            all_passed = False
        else:
            print(f"✅ Internal Angle OK")
        
        # Check R_3d (allow 5mm tolerance)
        if abs(result["r_3d"] - exp["r_3d"]) > 5:
            print(f"⚠️ R_3d MISMATCH!")
            all_passed = False
        else:
            print(f"✅ R_3d OK")
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 All tests PASSED!")
    else:
        print("❌ Some tests FAILED!")
    print("=" * 60)
    
    return all_passed

def test_geometry_output():
    """Test that compute_geometry includes Z coordinates."""
    m = ServoManager()
    
    print("\n" + "=" * 60)
    print("Geometry Output Test")
    print("=" * 60)
    
    geometry = m.compute_geometry()
    
    for vid, data in geometry.get("vertices", {}).items():
        print(f"\nVertex {vid}:")
        print(f"  Position: ({data.get('x')}, {data.get('y')}, {data.get('z')})")
        print(f"  Stance: {data.get('stance')}")
        print(f"  R_3d: {data.get('r_3d')} mm")
        if "angles" in data:
            print(f"  Internal Angle: {data['angles'].get('internal_angle')}°")
    
    # Check Z is present
    for vid, data in geometry.get("vertices", {}).items():
        if "z" not in data:
            print(f"\n❌ Vertex {vid} missing Z coordinate!")
            return False
    
    print("\n✅ All vertices have Z coordinates")
    return True

if __name__ == "__main__":
    test_dual_reach()
    test_geometry_output()
