"""
2-Bone Inverse Kinematics solver.

Solves the position of a middle joint (knee/elbow) given:
  - Root position (hip/shoulder)
  - Target position (foot/hand)
  - Two bone lengths (thigh+calf, or upper-arm+forearm)

Uses analytical solution (law of cosines) for deterministic, fast solving.
Handles unreachable targets by clamping to maximum reach.
"""
import math
from ursina import Vec3


def solve_2bone_ik(root: Vec3, target: Vec3, bone1_len: float, bone2_len: float) -> tuple[Vec3, Vec3]:
    """
    Solve 2-bone IK chain.

    Args:
        root: Position of the root joint (e.g., hip)
        target: Desired position of the end effector (e.g., foot)
        bone1_len: Length of first bone (e.g., thigh)
        bone2_len: Length of second bone (e.g., calf)

    Returns:
        Tuple of (middle_pos, end_pos) where:
            middle_pos: Position of the middle joint (e.g., knee)
            end_pos: Actual position of end effector (may differ from target if unreachable)

    Algorithm: Law of cosines to find angles, then construct positions.
    """
    to_target = target - root
    dist_to_target = to_target.length()

    # Clamp to reachable range
    max_reach = bone1_len + bone2_len
    min_reach = abs(bone1_len - bone2_len)

    if dist_to_target > max_reach:
        # Target unreachable — extend fully toward it
        to_target = to_target / dist_to_target * max_reach
        actual_target = root + to_target
        dist_to_target = max_reach
    elif dist_to_target < min_reach:
        # Target too close — extend minimally
        if dist_to_target < 0.001:
            # Root and target are same point — return bones extended in arbitrary direction
            to_target = Vec3(0, 0, 1)
        to_target = to_target / to_target.length() * min_reach
        actual_target = root + to_target
        dist_to_target = min_reach
    else:
        actual_target = target

    # Use law of cosines to find angle at root joint
    # c² = a² + b² - 2ab*cos(C)
    # cos(C) = (a² + b² - c²) / (2ab)
    cos_root_angle = (bone1_len**2 + dist_to_target**2 - bone2_len**2) / (2 * bone1_len * dist_to_target + 1e-6)
    cos_root_angle = max(-1.0, min(1.0, cos_root_angle))  # Clamp to [-1, 1]
    root_angle = math.acos(cos_root_angle)

    # Direction toward target
    dir_to_target = to_target / (dist_to_target + 1e-6)

    # Perpendicular direction (in XZ plane, assuming Y is up)
    perp = Vec3(-dir_to_target.z, 0, dir_to_target.x)

    # Middle joint position: root + bone1 along clamped target direction, rotated by root_angle
    cos_angle = math.cos(root_angle)
    sin_angle = math.sin(root_angle)

    # Position middle joint at bone1 length along direction, rotated
    bone1_dir = dir_to_target * cos_angle + perp * sin_angle
    middle_pos = root + bone1_dir * bone1_len

    # End effector is bone2 length from middle toward actual target
    to_end = actual_target - middle_pos
    dist_to_end = to_end.length()

    if dist_to_end < 0.001:
        # Middle joint and target are same — extend bone2 in arbitrary direction
        end_pos = middle_pos + Vec3(0, 0, bone2_len)
    else:
        end_pos = middle_pos + (to_end / dist_to_end) * bone2_len

    return middle_pos, end_pos


def get_joint_angles(root: Vec3, middle: Vec3, end: Vec3) -> tuple[float, float]:
    """
    Get Euler angles for each joint given positions.

    Args:
        root: Root joint position
        middle: Middle joint position
        end: End effector position

    Returns:
        Tuple of (angle1, angle2) in radians, where:
            angle1: Rotation of bone1 (at root joint)
            angle2: Rotation of bone2 (at middle joint)

    Useful for setting rotation_x/rotation_z on animated parts.
    """
    # First bone direction
    bone1 = middle - root
    bone1_angle = math.atan2(bone1.x, bone1.z)

    # Second bone direction (relative to first)
    bone2 = end - middle
    bone2_angle = math.atan2(bone2.x, bone2.z)

    # Relative rotation of bone2
    rel_angle = bone2_angle - bone1_angle

    return bone1_angle, rel_angle


class IKChain:
    """Represent and solve a part chain with IK."""

    def __init__(self, root_part: 'SculptPart', chain_parts: list['SculptPart']):
        """
        Initialize IK chain.

        Args:
            root_part: The part attached to the body (e.g., leg)
            chain_parts: List of child parts forming the chain (e.g., [shin, foot])
        """
        self.root = root_part
        self.chain = chain_parts
        self.enabled = len(chain_parts) >= 2  # Need at least 2 bones for IK

    def solve(self, target: Vec3) -> None:
        """Solve chain to reach target position."""
        if not self.enabled or len(self.chain) < 2:
            return

        # Use only first two parts for 2-bone IK
        part1 = self.chain[0]
        part2 = self.chain[1]

        # Estimate bone lengths from part positions
        bone1_len = (part1.position - self.root.position).length()
        bone2_len = (part2.position - part1.position).length()

        if bone1_len < 0.001 or bone2_len < 0.001:
            return  # Can't solve if bones are degenerate

        # Solve IK
        middle_pos, end_pos = solve_2bone_ik(
            self.root.position, target, bone1_len, bone2_len
        )

        # Update positions (simplified — full implementation would update rotations)
        part1.position = middle_pos
        part2.position = end_pos

        # TODO: Update rotations for animation
        # angle1, angle2 = get_joint_angles(self.root.position, middle_pos, end_pos)
        # part1.rotation_x = angle1
        # part2.rotation_x = angle2
