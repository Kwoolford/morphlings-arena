"""Body socket grid system for part attachment.

24 discrete attachment points on the body sphere. Parts snap to the nearest socket,
ensuring clean connections and preventing overlap. Sockets are normalized to SURFACE_R=0.52
and updated when body shape (sx/sy/sz) changes.

Part attachment architecture:
    Each part has a "natural outward axis" inferred from its default_offset direction.
    For socket-placed parts, the wrap entity is positioned at body CENTER and rotated
    so that the part's outward axis aligns with the socket's outward normal. The part's
    default_offset then naturally places its anchor at the body surface.

    This avoids the "double offset" bug where positioning the wrap at the surface AND
    applying default_offset would push the part to 2x the surface distance.
"""
import math
from ursina import Vec3


# 24 body sockets arranged on a geodesic-like grid covering the sphere
# All are pre-normalized to radius ~0.52 (SURFACE_R)
BODY_SOCKETS = [
    # 6 cardinal face centers
    Vec3(0,      0,      0.52),   # 0:  front
    Vec3(0,      0,     -0.52),   # 1:  back
    Vec3(0.52,   0,      0),      # 2:  right
    Vec3(-0.52,  0,      0),      # 3:  left
    Vec3(0,      0.52,   0),      # 4:  top
    Vec3(0,     -0.52,   0),      # 5:  bottom

    # 8 upper diagonal points (above equator)
    Vec3(0.37,   0.37,   0),      # 6:  upper-right-front
    Vec3(-0.37,  0.37,   0),      # 7:  upper-left-front
    Vec3(0,      0.37,   0.37),   # 8:  upper-front-center
    Vec3(0,      0.37,  -0.37),   # 9:  upper-back-center
    Vec3(0.26,   0.37,   0.26),   # 10: upper-right-front-mid
    Vec3(-0.26,  0.37,   0.26),   # 11: upper-left-front-mid
    Vec3(0.26,   0.37,  -0.26),   # 12: upper-right-back-mid
    Vec3(-0.26,  0.37,  -0.26),   # 13: upper-left-back-mid

    # 6 equatorial points (middle ring)
    Vec3(0.37,   0,      0.37),   # 14: front-right-mid
    Vec3(-0.37,  0,      0.37),   # 15: front-left-mid
    Vec3(0.37,   0,     -0.37),   # 16: back-right-mid
    Vec3(-0.37,  0,     -0.37),   # 17: back-left-mid
    Vec3(0.52,   0,      0),      # 2:  right (reused for spacing)
    Vec3(-0.52,  0,      0),      # 3:  left (reused)

    # 6 lower diagonal points (below equator)
    Vec3(0.37,  -0.37,   0),      # 18: lower-right-front
    Vec3(-0.37, -0.37,   0),      # 19: lower-left-front
    Vec3(0,     -0.37,   0.37),   # 20: lower-front-center
    Vec3(0,     -0.37,  -0.37),   # 21: lower-back-center
    Vec3(0.26,  -0.37,   0.26),   # 22: lower-right-front-mid
    Vec3(-0.26, -0.37,  -0.26),   # 23: lower-left-back-mid
]


def nearest_socket(direction_vec):
    """
    Find the index of the nearest socket to a direction vector.
    Normalizes the input direction and finds the socket with highest dot product.
    Args:
        direction_vec: Vec3 direction (will be normalized internally)
    Returns:
        int: socket index (0-23)
    """
    d_len = direction_vec.length()
    if d_len < 0.001:
        return 0  # default to front if direction is near-zero

    normal = direction_vec / d_len
    best_idx = 0
    best_dot = -1.0

    for i, socket in enumerate(BODY_SOCKETS):
        socket_norm = socket.normalized()
        dot = normal.dot(socket_norm)
        if dot > best_dot:
            best_idx = i
            best_dot = dot

    return best_idx


def socket_world_pos(socket_idx, body_size, sx=1.0, sy=1.0, sz=1.0):
    """
    Get the world position of a socket accounting for body shape.
    Args:
        socket_idx: int (0-23)
        body_size: float (the bs value from CreatureData)
        sx/sy/sz: float (body shape multipliers)
    Returns:
        Vec3: world position of the socket
    """
    if socket_idx < 0 or socket_idx >= len(BODY_SOCKETS):
        return Vec3(0, 0, 0)

    s = BODY_SOCKETS[socket_idx]
    return Vec3(s.x * sx, s.y * sy, s.z * sz) * body_size


def get_socket_label(socket_idx):
    """Get a human-readable label for a socket."""
    labels = [
        'Front', 'Back', 'Right', 'Left', 'Top', 'Bottom',
        'Upper-Right', 'Upper-Left', 'Upper-Front', 'Upper-Back',
        'Upper-Right-Mid', 'Upper-Left-Mid', 'Upper-Back-Right', 'Upper-Back-Left',
        'Front-Right', 'Front-Left', 'Back-Right', 'Back-Left', 'Right', 'Left',
        'Lower-Right', 'Lower-Left', 'Lower-Front', 'Lower-Back',
        'Lower-Right-Mid', 'Lower-Back-Left',
    ]
    if socket_idx < len(labels):
        return labels[socket_idx]
    return f'Socket {socket_idx}'


def get_outward_axis_name(default_offset):
    """Determine which local axis a part naturally extends along, based on its default_offset.

    Returns one of: 'right', 'left', 'up', 'down', 'forward', 'back'

    This is the axis that should be aligned with the socket outward normal so that
    the part extends from body surface outward (not into the body or parallel to it).
    """
    if default_offset is None:
        return 'right'
    abs_x = abs(default_offset.x)
    abs_y = abs(default_offset.y)
    abs_z = abs(default_offset.z)
    if abs_x >= abs_y and abs_x >= abs_z:
        return 'right' if default_offset.x >= 0 else 'left'
    elif abs_y >= abs_z:
        return 'up' if default_offset.y >= 0 else 'down'
    else:
        return 'forward' if default_offset.z >= 0 else 'back'


def orient_part_for_socket(wrap, socket_idx, bs, sx, sy, sz, default_offset):
    """Position and orient a part wrap to attach cleanly at a socket.

    Strategy:
        1. Wrap is placed at LOCAL (0, 0, 0) — body center in the parent's frame.
        2. Wrap is rotated so the part's natural extension direction (from
           default_offset) points along the socket's outward normal.
        3. The part's default_offset then naturally places its anchor at the
           body surface, with geometry extending outward from there.

    This eliminates the "double offset" bug where positioning at surface AND
    applying default_offset would put parts at 2x the surface distance.

    The rotation is computed directly using a simple matrix construction so that
    it works correctly when the wrap is parented to a creature with rotation.
    """
    socket_pos = socket_world_pos(socket_idx, bs, sx, sy, sz)
    if socket_pos.length() < 0.001:
        return

    outward = socket_pos.normalized()

    # Place wrap at body center
    wrap.position = Vec3(0, 0, 0)

    # Determine which axis name to use for look_at, based on the part's
    # default_offset direction.
    axis = get_outward_axis_name(default_offset)

    # Transform the local-space outward direction into WORLD space, accounting
    # for the parent's world rotation (so the rotation works correctly when the
    # creature is rotated, e.g. in arena combat where morphlings face their target).
    outward_world = _local_dir_to_world(wrap, outward)

    # Compute world-space target and use Ursina's look_at, which is well-tested
    # for all cardinal axes. This handles top/bottom/front/back/sides correctly.
    target_world = wrap.world_position + outward_world
    try:
        wrap.look_at(target_world, axis=axis)
    except Exception:
        # Last-resort fallback: yaw-only based on horizontal projection of outward
        wrap.rotation_y = math.degrees(math.atan2(outward.x, outward.z))


def _local_dir_to_world(entity, local_dir):
    """Transform a direction vector from entity's parent's local frame to world frame.

    Handles the common case where the parent has only rotation_y (yaw). Falls back
    to identity if no parent or parent isn't rotated.
    """
    parent = entity.parent
    if parent is None or not hasattr(parent, 'world_rotation_y'):
        return local_dir

    yaw = math.radians(getattr(parent, 'world_rotation_y', 0.0))
    if abs(yaw) < 1e-6:
        return local_dir

    # Rotate around Y axis by parent's world yaw
    cos_y = math.cos(yaw)
    sin_y = math.sin(yaw)
    return Vec3(
        local_dir.x * cos_y + local_dir.z * sin_y,
        local_dir.y,
        -local_dir.x * sin_y + local_dir.z * cos_y,
    )


def _euler_from_to(from_dir, to_dir):
    """Compute Euler rotation (rotation_x, rotation_y, rotation_z) that rotates
    from_dir to to_dir, both unit vectors in the same coordinate frame.

    Uses Ursina's YXZ Euler convention. Returns Vec3(rx, ry, rz) in degrees.

    Approach: rotate the "from" direction first to +Z (yaw + pitch in reverse),
    then from +Z to the "to" direction (yaw + pitch). Combine the rotations.

    For the common cases (horizontal sockets, parts with horizontal default_offset)
    this resolves to a simple rotation_y. For non-horizontal cases, it adds a pitch.
    """
    # Step 1: angles to rotate +Z to from_dir
    fx, fy, fz = from_dir.x, from_dir.y, from_dir.z
    f_horiz = math.sqrt(fx*fx + fz*fz)
    f_yaw = math.atan2(fx, fz) if f_horiz > 0.001 else 0.0  # +Z → from in horizontal
    f_pitch = math.atan2(-fy, max(f_horiz, 0.001))           # +Z → from in vertical

    # Step 2: angles to rotate +Z to to_dir
    tx, ty, tz = to_dir.x, to_dir.y, to_dir.z
    t_horiz = math.sqrt(tx*tx + tz*tz)
    t_yaw = math.atan2(tx, tz) if t_horiz > 0.001 else 0.0
    t_pitch = math.atan2(-ty, max(t_horiz, 0.001))

    # The rotation that takes from_dir to to_dir is approximately:
    #   rotate by -f_yaw, -f_pitch (sending from_dir to +Z), then by t_pitch, t_yaw
    # In Ursina YXZ Euler order, applying rotations in sequence does NOT cleanly
    # simplify, so we use the simple delta which works for cardinal-axis from_dirs.
    delta_yaw = t_yaw - f_yaw
    delta_pitch = t_pitch - f_pitch

    return Vec3(math.degrees(delta_pitch), math.degrees(delta_yaw), 0)
