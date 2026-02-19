"""
Geometry Visualizer with FK/IK Verification
Robot geometry visualization tool using matplotlib.
Includes radius circles, yaw arrows, info panel, and FK/IK roundtrip verification.
"""

import matplotlib.pyplot as plt
from matplotlib.widgets import Button
from matplotlib.patches import Circle, FancyArrowPatch
import numpy as np
import math
import json
import os
import sys

# Ensure ik_tester can be imported
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from geometry_engine import compute_geometry, compute_reach, compute_yaw
from ik_tester.ik_solver import IKSolver


# Global variables for interactive updates
config_path = None
config = None
fig = None
ax = None
info_text = None


def load_config(path=None):
    """Load servo configuration from JSON file."""
    global config_path, config
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "servo_config.json")
    config_path = path
    
    with open(path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return config


def get_link_lengths(cfg):
    """Extract link lengths from config for IK solver."""
    # Use right_arm as reference (lengths should be same for both arms)
    arm = cfg.get("right_arm", {})
    return {
        'd1': arm.get("slot_1", {}).get("length", 107.0),
        'a2': arm.get("slot_2", {}).get("length", 105.0),
        'a3': arm.get("slot_3", {}).get("length", 150.0),
        'a4': arm.get("slot_4", {}).get("length", 65.0) + 
              arm.get("slot_5", {}).get("length", 0.0) + 
              arm.get("slot_6", {}).get("length", 115.0)  # Wrist + Gripper
    }


def compute_base_info(cfg, arm_name):
    """
    Compute base position info including reach, yaw, and coordinates.
    
    Returns:
        dict: {reach, yaw_deg, base_x, base_y} or None if share_point not found
    """
    share_point = cfg.get("share_points", {}).get(arm_name)
    if not share_point:
        return None
    
    reach = compute_reach(cfg, arm_name, share_point, is_vertex=False)
    yaw = compute_yaw(cfg, arm_name, share_point)
    yaw_deg = math.degrees(yaw)
    
    # Base position from share point (0, 0)
    # IK coordinate: yaw=0° = forward (+Y)
    base_x = -reach * (-math.sin(yaw))  # -sin for +X=right
    base_y = -reach * math.cos(yaw)
    
    return {
        'reach': reach,
        'yaw_deg': yaw_deg,
        'base_x': base_x,
        'base_y': base_y
    }


def verify_fk_ik(cfg, geometry):
    """
    Verify FK/IK roundtrip: FK result → IK → compare angles.
    
    Returns:
        list: Verification results for each vertex
    """
    results = []
    link_lengths = get_link_lengths(cfg)
    
    # Create IK solver with no joint limits for verification
    solver = IKSolver(link_lengths, {})
    
    for vid, vertex in geometry.get("vertices", {}).items():
        vx, vy = vertex["x"], vertex["y"]
        owner = vertex.get("owner", "")
        
        if owner not in geometry.get("bases", {}):
            continue
        
        base = geometry["bases"][owner]
        
        # Get original angles from config
        vertex_data = cfg.get("vertices", {}).get(vid, {})
        orig_angles = vertex_data.get("angles", {})
        
        # World yaw from slot 1
        slot1_cfg = cfg.get(owner, {}).get("slot_1", {})
        zero_offset = slot1_cfg.get("zero_offset", 0)
        orig_theta1 = orig_angles.get("slot_1", 0) - zero_offset
        
        # FK computed position relative to base
        rel_x = vx - base["x"]
        rel_y = vy - base["y"]
        
        # IK solve for this position (assuming Z=0 for 2D projection)
        # Using base as reference, target is vertex position
        target_xyz = (rel_x, rel_y, 0)
        ik_result = solver.solve(target_xyz)
        
        error = None
        ik_theta1 = None
        
        if ik_result.is_reachable and ik_result.best_solution:
            ik_theta1 = ik_result.best_solution.theta1
            error = abs(orig_theta1 - ik_theta1)
        
        results.append({
            'vid': vid,
            'owner': owner,
            'vx': vx,
            'vy': vy,
            'orig_theta1': orig_theta1,
            'ik_theta1': ik_theta1,
            'error': error,
            'is_reachable': ik_result.is_reachable
        })
    
    return results


def draw_geometry(ax, geometry, cfg):
    """Draw geometry elements on the axes with radius circles and yaw arrows."""
    ax.clear()
    
    # Collect all points to determine axis range
    all_x = [0]
    all_y = [0]
    
    colors = {'left_arm': '#3498db', 'right_arm': '#e74c3c'}  # Blue, Red
    
    # 1. Plot Share Point (origin)
    ax.plot(0, 0, 'ko', markersize=15, label='Share Point (Origin)', zorder=10)
    ax.annotate('Origin\n(0, 0)', (0, 0), textcoords="offset points", 
                xytext=(10, 10), fontsize=9, fontweight='bold')
    
    # 2. Draw radius circles and yaw arrows for each arm
    for arm in ["left_arm", "right_arm"]:
        base_info = compute_base_info(cfg, arm)
        if not base_info:
            continue
        
        color = colors.get(arm, 'gray')
        reach = base_info['reach']
        yaw_deg = base_info['yaw_deg']
        base_x = base_info['base_x']
        base_y = base_info['base_y']
        
        all_x.extend([base_x, -reach, reach])
        all_y.extend([base_y, -reach, reach])
        
        # 2.1 Draw radius circle (dashed)
        circle = Circle((0, 0), reach, fill=False, linestyle='--', 
                        color=color, alpha=0.5, linewidth=1.5, label=f'{arm} Reach Circle')
        ax.add_patch(circle)
        
        # 2.2 Draw dashed line from Share Point (0,0) to Base
        ax.plot([0, base_x], [0, base_y], '--', color=color, alpha=0.7, linewidth=2, zorder=5)
        
        # 2.3 Draw combined label (distance + yaw) on the line
        mid_x, mid_y = base_x / 2, base_y / 2
        dist = math.sqrt(base_x**2 + base_y**2)
        yaw_rad = math.radians(yaw_deg)
        # Offset the label perpendicular to the line
        perp_angle = yaw_rad + math.pi / 2
        offset_x = 20 * math.cos(perp_angle)
        offset_y = 20 * math.sin(perp_angle)
        ax.annotate(f'{dist:.0f}mm | {yaw_deg:.1f}°', (mid_x + offset_x, mid_y + offset_y),
                   fontsize=9, color=color, fontweight='bold',
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.9, edgecolor=color))
    
    # 3. Plot Base positions
    for arm, base in geometry.get("bases", {}).items():
        x, y = base["x"], base["y"]
        all_x.append(x)
        all_y.append(y)
        color = colors.get(arm, 'gray')
        ax.plot(x, y, 's', color=color, markersize=14, label=f'{arm} Base', zorder=8)
        ax.annotate(f'{arm.split("_")[0]}\n({x:.0f}, {y:.0f})', (x, y), 
                    textcoords="offset points", xytext=(8, 8), fontsize=9, fontweight='bold')
    
    # 4. Plot Vertex positions and connections with unique colors
    vertex_colors = {
        '1': '#9b59b6',  # Purple
        '2': '#1abc9c',  # Teal
        '3': '#f39c12',  # Orange
        '4': '#2ecc71',  # Green
        '5': '#e91e63',  # Pink
        '6': '#00bcd4',  # Cyan
        '7': '#ff5722',  # Deep Orange
        '8': '#795548',  # Brown
    }
    
    # Get distances from geometry
    distances = geometry.get("distances", {})
    sp_to_vertex = distances.get("share_point_to_vertex", {})
    
    for vid, vertex in geometry.get("vertices", {}).items():
        vx, vy = vertex["x"], vertex["y"]
        owner = vertex.get("owner", "")
        reach = vertex.get("reach", 0)
        all_x.append(vx)
        all_y.append(vy)
        
        # Use unique vertex color
        v_color = vertex_colors.get(vid, '#888888')
        
        # Draw Share Point→Vertex dotted line with distance label
        sp_dist = sp_to_vertex.get(vid, 0)
        ax.plot([0, vx], [0, vy], ':', color=v_color, alpha=0.5, linewidth=1)
        
        # Distance label at 1/3 point (closer to origin)
        label_x = vx * 0.35
        label_y = vy * 0.35
        ax.annotate(f'{sp_dist:.0f}mm', (label_x, label_y),
                   fontsize=6, color=v_color, alpha=0.8)
        
        # Vertex marker
        ax.plot(vx, vy, 'o', color=v_color, markersize=10, zorder=7)
        ax.annotate(f'V{vid}\n({vx:.0f}, {vy:.0f})', (vx, vy),
                    textcoords="offset points", xytext=(5, -15), fontsize=8, color=v_color)
        
        # Draw line from base to vertex with reach/yaw label
        if owner in geometry.get("bases", {}):
            base = geometry["bases"][owner]
            base_x, base_y = base["x"], base["y"]
            
            # Draw dashed line (with vertex color)
            ax.plot([base_x, vx], [base_y, vy], 
                    '--', color=v_color, alpha=0.6, linewidth=1.5)
            
            # Calculate midpoint and yaw for label
            mid_x = (base_x + vx) / 2
            mid_y = (base_y + vy) / 2
            
            # Get yaw from vertex angles
            vertex_data = cfg.get("vertices", {}).get(vid, {})
            if vertex_data:
                from geometry_engine import compute_yaw
                yaw_rad = compute_yaw(cfg, owner, vertex_data)
                yaw_deg = math.degrees(yaw_rad)
            else:
                yaw_deg = 0
            
            # Offset label perpendicular to line
            line_angle = math.atan2(vy - base_y, vx - base_x)
            perp_angle = line_angle + math.pi / 2
            offset_x = 15 * math.cos(perp_angle)
            offset_y = 15 * math.sin(perp_angle)
            
            ax.annotate(f'{reach:.0f}mm | {yaw_deg:.1f}°', 
                       (mid_x + offset_x, mid_y + offset_y),
                       fontsize=7, color=v_color,
                       bbox=dict(boxstyle='round,pad=0.2', facecolor='white', 
                                alpha=0.8, edgecolor=v_color, linewidth=0.5))
    
    # 5. Draw Vertex-to-Vertex connections with distances
    from matplotlib.patches import Arc
    vertex_ids = list(geometry.get("vertices", {}).keys())
    v_to_v = distances.get("vertex_to_vertex", {})
    
    # Just draw lines and distance labels (no angle here)
    for i, v1 in enumerate(vertex_ids):
        for v2 in vertex_ids[i+1:]:
            p1 = geometry["vertices"][v1]
            p2 = geometry["vertices"][v2]
            x1, y1 = p1["x"], p1["y"]
            x2, y2 = p2["x"], p2["y"]
            
            # Draw solid line between vertices
            ax.plot([x1, x2], [y1, y2], '-', color='#555555', alpha=0.4, linewidth=1, zorder=3)
            
            # Get distance
            dist_key = f"{v1}_{v2}"
            dist = v_to_v.get(dist_key, 0)
            
            # Distance label at line midpoint
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            ax.annotate(f'{dist:.0f}mm', (mid_x, mid_y),
                       fontsize=6, color='#555555', ha='center',
                       bbox=dict(boxstyle='round,pad=0.2', facecolor='#f0f0f0', 
                                alpha=0.7, edgecolor='#999999', linewidth=0.5))
    
    # 6. Draw angles at center vertex (3-vertex combinations)
    # Colors for different angle combinations
    angle_colors = [
        '#FF6B6B',  # Red
        '#4ECDC4',  # Cyan
        '#45B7D1',  # Blue
        '#96CEB4',  # Green
        '#FFEAA7',  # Yellow
        '#DDA0DD',  # Plum
    ]
    
    angle_idx = 0
    for center_vid in vertex_ids:
        center = geometry["vertices"][center_vid]
        cx, cy = center["x"], center["y"]
        
        # Get all other vertices connected to this center
        other_vids = [v for v in vertex_ids if v != center_vid]
        
        # For each pair of other vertices, calculate angle at center
        for i, va in enumerate(other_vids):
            for vb in other_vids[i+1:]:
                pa = geometry["vertices"][va]
                pb = geometry["vertices"][vb]
                ax_p, ay_p = pa["x"], pa["y"]
                bx_p, by_p = pb["x"], pb["y"]
                
                # Angle from center to each vertex
                angle_a = math.degrees(math.atan2(ay_p - cy, ax_p - cx))
                angle_b = math.degrees(math.atan2(by_p - cy, bx_p - cx))
                
                # Calculate the angle between the two directions
                start_angle = min(angle_a, angle_b)
                end_angle = max(angle_a, angle_b)
                angle_diff = end_angle - start_angle
                if angle_diff > 180:
                    start_angle, end_angle = end_angle, start_angle + 360
                    angle_diff = 360 - angle_diff
                
                # Draw arc at center vertex
                arc_radius = 20 + (angle_idx % 3) * 8
                color = angle_colors[angle_idx % len(angle_colors)]
                
                arc = Arc((cx, cy), arc_radius * 2, arc_radius * 2,
                         angle=0, theta1=start_angle, theta2=end_angle,
                         color=color, linewidth=1.5, linestyle='-', alpha=0.7)
                ax.add_patch(arc)
                
                # Angle label at arc midpoint
                mid_angle = math.radians((start_angle + end_angle) / 2)
                label_x = cx + (arc_radius + 12) * math.cos(mid_angle)
                label_y = cy + (arc_radius + 12) * math.sin(mid_angle)
                ax.annotate(f'{angle_diff:.0f}°', (label_x, label_y),
                           fontsize=5, color=color, ha='center', va='center',
                           fontweight='bold')
                
                angle_idx += 1
    margin = 100
    max_range = max(max(abs(min(all_x)), abs(max(all_x))),
                    max(abs(min(all_y)), abs(max(all_y)))) + margin
    
    ax.set_xlim(-max_range, max_range)
    ax.set_ylim(-max_range, max_range)
    
    # 6. Draw axis lines through origin
    ax.axhline(y=0, color='gray', linestyle='-', linewidth=0.5)
    ax.axvline(x=0, color='gray', linestyle='-', linewidth=0.5)
    
    # 7. Configure plot
    ax.set_title("Robot Geometry Visualization\n(+X=Right, +Y=Up, Origin=Share Point)", fontsize=12)
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper right', fontsize=8)


def update_info_panel(cfg, geometry):
    """Update the info panel with calculation details."""
    global info_text
    
    lines = ["═══ Calculation Details ═══\n"]
    
    for arm in ["left_arm", "right_arm"]:
        base_info = compute_base_info(cfg, arm)
        if not base_info:
            continue
        
        arm_short = arm.split("_")[0].capitalize()
        lines.append(f"【{arm_short} Arm】")
        lines.append(f"  Reach: {base_info['reach']:.1f} mm")
        lines.append(f"  Yaw: {base_info['yaw_deg']:.1f}°")
        lines.append(f"  Base: ({base_info['base_x']:.1f}, {base_info['base_y']:.1f})")
        lines.append("")
    
    # FK/IK verification summary
    verification = verify_fk_ik(cfg, geometry)
    if verification:
        lines.append("═══ FK/IK Verification ═══")
        for v in verification:
            status = "✓" if v['error'] is not None and v['error'] < 5 else "✗"
            if v['error'] is not None:
                lines.append(f"  V{v['vid']}: θ1={v['orig_theta1']:.1f}° → IK={v['ik_theta1']:.1f}° [{status}]")
            else:
                lines.append(f"  V{v['vid']}: Unreachable")
    
    info_text.set_text("\n".join(lines))


def on_compute_click(event):
    """Button callback: Reload config and recompute geometry."""
    global config_path, config, ax, fig, info_text
    
    print("\n" + "="*50)
    print("Reloading config and recomputing geometry...")
    config = load_config(config_path)
    geometry = compute_geometry(config)
    
    draw_geometry(ax, geometry, config)
    update_info_panel(config, geometry)
    
    fig.canvas.draw_idle()
    print("Done!")
    print("="*50)


def on_verify_click(event):
    """Button callback: Run FK/IK verification and print details."""
    global config, ax, fig
    
    print("\n" + "="*60)
    print("=== FK/IK ROUNDTRIP VERIFICATION ===")
    print("="*60)
    
    geometry = compute_geometry(config)
    link_lengths = get_link_lengths(config)
    
    print(f"\nLink Lengths: d1={link_lengths['d1']}, a2={link_lengths['a2']}, "
          f"a3={link_lengths['a3']}, a4={link_lengths['a4']}")
    
    # Print base info
    print("\n--- Base Positions ---")
    for arm in ["left_arm", "right_arm"]:
        base_info = compute_base_info(config, arm)
        if base_info:
            print(f"{arm}: reach={base_info['reach']:.1f}mm, yaw={base_info['yaw_deg']:.1f}°, "
                  f"base=({base_info['base_x']:.1f}, {base_info['base_y']:.1f})")
    
    # Print vertex verification
    print("\n--- Vertex Verification ---")
    verification = verify_fk_ik(config, geometry)
    for v in verification:
        print(f"\nV{v['vid']} ({v['owner']}):")
        print(f"  Position: ({v['vx']:.1f}, {v['vy']:.1f})")
        print(f"  Original θ1: {v['orig_theta1']:.1f}°")
        if v['ik_theta1'] is not None:
            print(f"  IK θ1: {v['ik_theta1']:.1f}°")
            print(f"  Error: {v['error']:.1f}°")
            print(f"  Status: {'[PASS]' if v['error'] < 5 else '[FAIL]'}")
        else:
            print(f"  IK: Unreachable")
    
    print("\n" + "="*60)


def visualize_geometry(cfg):
    """
    Visualize robot geometry using matplotlib with interactive buttons.
    
    Args:
        cfg: Servo configuration dict
    """
    global fig, ax, info_text, config
    config = cfg
    
    # Compute geometry
    geometry = compute_geometry(cfg)
    
    # Create figure with info panel on the right
    fig = plt.figure(figsize=(16, 12))
    
    # Main plot area
    ax = fig.add_axes([0.05, 0.1, 0.65, 0.85])
    
    # Info panel area (text on the right)
    info_ax = fig.add_axes([0.72, 0.3, 0.26, 0.6])
    info_ax.axis('off')
    info_text = info_ax.text(0, 1, "", fontsize=9, fontfamily='monospace',
                             verticalalignment='top', transform=info_ax.transAxes)
    
    # Draw initial geometry
    draw_geometry(ax, geometry, cfg)
    update_info_panel(cfg, geometry)
    
    # Add Compute Geometry button
    btn_compute_ax = plt.axes([0.3, 0.02, 0.15, 0.05])
    btn_compute = Button(btn_compute_ax, 'Compute Geometry', color='lightblue', hovercolor='skyblue')
    btn_compute.on_clicked(on_compute_click)
    
    # Add Verify FK/IK button
    btn_verify_ax = plt.axes([0.5, 0.02, 0.15, 0.05])
    btn_verify = Button(btn_verify_ax, 'Verify FK/IK', color='lightgreen', hovercolor='palegreen')
    btn_verify.on_clicked(on_verify_click)
    
    plt.show()


if __name__ == "__main__":
    cfg = load_config()
    visualize_geometry(cfg)
