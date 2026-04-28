"""Body socket grid system for part attachment.

24 discrete attachment points on the body sphere. Parts snap to the nearest socket,
ensuring clean connections and preventing overlap. Sockets are normalized to SURFACE_R=0.52
and updated when body shape (sx/sy/sz) changes.
"""
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
