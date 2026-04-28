"""
Part registry. Each part type registers a builder + metadata.

To add a new part type:

    @register('horn_curved', 'CURVED HORN', c8(180, 80, 240),
              mut_key='horns', default_offset=lambda s: Vec3(0, s*0.6, 0))
    def _curved_horn(parent, bc, s, ep, sx=1.0, sy=1.0, sz=1.0):
        return [Entity(parent=parent, model='cube', color=darker(bc, 0.3),
                       scale=Vec3(s*0.10, s*0.40, s*0.10), position=ep,
                       rotation_x=-25)]

Animation contract:
    If the builder returns a pivot Entity with these attributes set, the sculptor
    and arena will animate it every frame:
        _anim_attr   str    Ursina attribute to oscillate ('rotation_z', 'rotation_x')
        _anim_amp    float  degrees of swing amplitude
        _anim_freq   float  oscillations per second

    The phase (left vs right side) is determined at animation time from the part's
    normalised px position — no need to set it in the builder.

TODO: _anim_phase field is set but currently unused; remove or use it for
      per-placement random phase offsets so two arms don't sync perfectly.
TODO: add 'claw' part (3-pronged hand, large, high cost)
TODO: add 'antennae' part (pair of thin stalks above head)
TODO: add 'shell' part (wide flat carapace on back — provides passive defense bonus)
TODO: add 'tentacle' part (sinusoidal animated limb, replaces arm slot)
TODO: 'neck' part that repositions the head lump vertically
TODO: parts that have functional joints (elbow/knee angle is adjustable in sculptor)
"""
from ursina import Entity, Vec3, color

from config import c8, darker, lighter


# ptype -> dict(label, color, mirror_default, mut_key, default_offset, builder)
PART_REGISTRY = {}


def register(ptype, label, ui_color, *, mirror_default=False,
             mut_key=None, default_offset=None):
    """Decorator. `default_offset` is a function of `s` (scaled body unit)."""
    def deco(builder):
        PART_REGISTRY[ptype] = dict(
            label=label,
            color=ui_color,
            mirror_default=mirror_default,
            mut_key=mut_key,
            default_offset=default_offset,
            builder=builder,
        )
        return builder
    return deco


def make_part(parent, ptype, body_color, body_size, scale_mult=1.0, pos=None, sx=1.0, sy=1.0, sz=1.0):
    """Build a part's visual children on `parent`. Returns the entity list.

    Anchor position uses `body_size` only so the attachment point stays fixed
    to the body surface as scale_mult changes.  Geometry sizes use the full
    `s = body_size * scale_mult` so the part grows without drifting outward.
    The sx/sy/sz parameters account for body shape stretching when positioning connectors.
    """
    info = PART_REGISTRY.get(ptype)
    if not info:
        return []
    s = body_size * scale_mult
    if pos is not None:
        ep = pos
    elif info['default_offset']:
        ep = info['default_offset'](body_size)   # anchor stays fixed to body_size
    else:
        ep = Vec3(0, 0, 0)
    return info['builder'](parent, body_color, s, ep, sx, sy, sz)


def part_types():
    """Stable iteration order for UI building."""
    return list(PART_REGISTRY.keys())


def add_connector(parent, body_color, body_size, attachment_pos, sx=1.0, sy=1.0, sz=1.0):
    """Create a tapered connector from body surface to attachment point.
    Bridges visual gap between body and part. Accounts for ellipsoid body scaling."""
    bs = body_size
    ap = attachment_pos
    dist = ap.length()
    if dist < 0.001:
        return
    direction = ap / dist
    # Connector extends from body surface to attachment point
    # Body surface point on ellipsoid: scale the unit direction by the shape axes
    body_surface = Vec3(direction.x * sx * bs * 0.50,
                        direction.y * sy * bs * 0.50,
                        direction.z * sz * bs * 0.50)
    connector_length = (ap - body_surface).length()
    if connector_length < 0.01:
        return
    # Create tapered connector using scaled spheres for smooth blending
    connector_ents = []
    conn_color = darker(body_color, 0.08)
    # Base sphere at body surface (larger)
    base = Entity(parent=parent, model='sphere',
                  color=conn_color,
                  scale=bs*0.14,
                  position=body_surface)
    connector_ents.append(base)
    # Mid sphere (medium)
    mid_pos = body_surface + (ap - body_surface) * 0.5
    mid = Entity(parent=parent, model='sphere',
                 color=conn_color,
                 scale=bs*0.10,
                 position=mid_pos)
    connector_ents.append(mid)
    # Tip sphere at attachment point (smaller)
    tip = Entity(parent=parent, model='sphere',
                 color=darker(body_color, 0.04),
                 scale=bs*0.09,
                 position=ap)
    connector_ents.append(tip)
    return connector_ents


# ════════════════════════════════════════════════════════════════════════════
# Built-in part types
# ════════════════════════════════════════════════════════════════════════════

@register('arm', 'ARM', c8(255,160,100), mirror_default=True, mut_key='arms',
          default_offset=lambda s: Vec3(s*0.52, s*0.05, 0))
def _arm(parent, bc, s, ep, sx=1.0, sy=1.0, sz=1.0):
    """Segmented arm: shoulder → upper arm → elbow → forearm → hand.
    Returns a pivot entity tagged for idle swing animation."""
    ul = s * 0.32   # upper arm length
    fl = s * 0.24   # forearm length

    # Add connector from body surface to attachment
    connector_ents = add_connector(parent, bc, s/1.0 if s > 0.1 else s, ep, sx, sy, sz)

    pivot = Entity(parent=parent, position=ep)
    pivot._anim_attr  = 'rotation_z'
    pivot._anim_amp   = 22.0
    pivot._anim_freq  = 1.3
    pivot._anim_phase = 0.0

    # Shoulder ball
    Entity(parent=pivot, model='sphere', color=darker(bc, 0.04),
           scale=s*0.21)
    # Upper arm tube
    Entity(parent=pivot, model='sphere', color=darker(bc, 0.14),
           scale=Vec3(s*0.13, ul, s*0.13),
           position=Vec3(0, -ul*0.5, 0))
    # Elbow knob
    Entity(parent=pivot, model='sphere', color=darker(bc, 0.08),
           scale=s*0.14, position=Vec3(0, -ul, 0))
    # Forearm tube (slight forward lean)
    Entity(parent=pivot, model='sphere', color=darker(bc, 0.18),
           scale=Vec3(s*0.11, fl, s*0.11),
           position=Vec3(0, -ul - fl*0.5, s*0.05))
    # Hand pad
    Entity(parent=pivot, model='sphere', color=lighter(bc, 0.06),
           scale=Vec3(s*0.18, s*0.11, s*0.18),
           position=Vec3(0, -ul - fl, s*0.09))
    # Three stubby fingers
    for i, fx in enumerate((-0.055, 0, 0.055)):
        Entity(parent=pivot, model='sphere', color=darker(bc, 0.10),
               scale=Vec3(s*0.055, s*0.10, s*0.055),
               position=Vec3(s*fx, -ul - fl - s*0.09, s*0.09))

    return [pivot] + (connector_ents if connector_ents else [])


@register('leg', 'LEG', c8(100,200,255), mirror_default=True, mut_key='legs',
          default_offset=lambda s: Vec3(s*0.28, -s*0.22, 0))
def _leg(parent, bc, s, ep, sx=1.0, sy=1.0, sz=1.0):
    """Segmented leg: hip → thigh → knee → shin → foot.
    Returns a pivot entity tagged for walking animation."""
    tl = s * 0.30   # thigh length
    sl = s * 0.24   # shin length

    # Add connector from body surface to attachment
    connector_ents = add_connector(parent, bc, s/1.0 if s > 0.1 else s, ep, sx, sy, sz)

    pivot = Entity(parent=parent, position=ep)
    pivot._anim_attr  = 'rotation_x'
    pivot._anim_amp   = 18.0
    pivot._anim_freq  = 1.6
    pivot._anim_phase = 0.0

    # Hip ball
    Entity(parent=pivot, model='sphere', color=darker(bc, 0.04),
           scale=s*0.22)
    # Thigh tube
    Entity(parent=pivot, model='sphere', color=darker(bc, 0.12),
           scale=Vec3(s*0.15, tl, s*0.15),
           position=Vec3(0, -tl*0.5, 0))
    # Knee knob
    Entity(parent=pivot, model='sphere', color=darker(bc, 0.07),
           scale=s*0.15, position=Vec3(0, -tl, 0))
    # Shin tube (slight forward lean)
    Entity(parent=pivot, model='sphere', color=darker(bc, 0.16),
           scale=Vec3(s*0.12, sl, s*0.12),
           position=Vec3(0, -tl - sl*0.5, s*0.04))
    # Foot (wide, flat)
    Entity(parent=pivot, model='sphere', color=lighter(bc, 0.04),
           scale=Vec3(s*0.20, s*0.08, s*0.26),
           position=Vec3(0, -tl - sl, s*0.10))

    return [pivot] + (connector_ents if connector_ents else [])


@register('eye', 'EYE', c8(255,80,80), mut_key='eyes',
          default_offset=lambda s: Vec3(0, 0, s*0.5))
def _eye(parent, bc, s, ep, sx=1.0, sy=1.0, sz=1.0):
    es = s * 0.22
    return [
        Entity(parent=parent, model='sphere', color=color.white, scale=es, position=ep),
        Entity(parent=parent, model='sphere', color=color.black, scale=es*0.62,
               position=ep + Vec3(0, 0, es*0.26)),
        Entity(parent=parent, model='sphere', color=color.black, scale=es*0.34,
               position=ep + Vec3(0, 0, es*0.46)),
        Entity(parent=parent, model='sphere', color=color.white, scale=es*0.11,
               position=ep + Vec3(es*0.09, es*0.09, es*0.56)),
    ]


@register('horn', 'HORN', c8(200,100,255), mut_key='horns',
          default_offset=lambda s: Vec3(0, s*0.5, 0))
def _horn(parent, bc, s, ep, sx=1.0, sy=1.0, sz=1.0):
    connector_ents = add_connector(parent, bc, s/1.0 if s > 0.1 else s, ep, sx, sy, sz)
    horn = [Entity(parent=parent, model='cube', color=darker(bc, 0.25),
                   scale=Vec3(s*0.12, s*0.32, s*0.12), position=ep)]
    return horn + (connector_ents if connector_ents else [])


@register('tail', 'TAIL', c8(100,255,180), mut_key='tail',
          default_offset=lambda s: Vec3(0, 0, -s*0.6))
def _tail(parent, bc, s, ep, sx=1.0, sy=1.0, sz=1.0):
    return [
        Entity(parent=parent, model='sphere', color=bc, scale=s*0.20, position=ep),
        Entity(parent=parent, model='sphere', color=bc, scale=s*0.14,
               position=ep + Vec3(0, 0, -s*0.18)),
        Entity(parent=parent, model='sphere', color=bc, scale=s*0.09,
               position=ep + Vec3(0, 0, -s*0.32)),
    ]


@register('wing', 'WING', c8(255,255,100), mirror_default=True, mut_key='wings',
          default_offset=lambda s: Vec3(s*0.55, s*0.08, 0))
def _wing(parent, bc, s, ep, sx=1.0, sy=1.0, sz=1.0):
    connector_ents = add_connector(parent, bc, s/1.0 if s > 0.1 else s, ep, sx, sy, sz)
    wing = [Entity(parent=parent, model='cube', color=lighter(bc, 0.20),
                   scale=Vec3(s*0.55, s*0.38, s*0.04), position=ep)]
    return wing + (connector_ents if connector_ents else [])


@register('spike', 'SPIKE', c8(255,100,100), mut_key='spikes',
          default_offset=lambda s: Vec3(0, s*0.5, 0))
def _spike(parent, bc, s, ep, sx=1.0, sy=1.0, sz=1.0):
    connector_ents = add_connector(parent, bc, s/1.0 if s > 0.1 else s, ep, sx, sy, sz)
    spike = [Entity(parent=parent, model='sphere', color=darker(bc, 0.30),
                   scale=Vec3(s*0.09, s*0.24, s*0.09), position=ep)]
    return spike + (connector_ents if connector_ents else [])


@register('mouth', 'MOUTH', c8(255,180,180),
          default_offset=lambda s: Vec3(0, -s*0.1, s*0.48))
def _mouth(parent, bc, s, ep, sx=1.0, sy=1.0, sz=1.0):
    return [
        Entity(parent=parent, model='cube', color=c8(40,10,10),
               scale=Vec3(s*0.32, s*0.10, s*0.08), position=ep),
        Entity(parent=parent, model='sphere', color=c8(255,80,80),
               scale=s*0.07, position=ep + Vec3(0, -s*0.04, s*0.04)),
    ]


@register('ear', 'EAR', c8(200,160,255), mirror_default=True,
          default_offset=lambda s: Vec3(s*0.40, s*0.52, 0))
def _ear(parent, bc, s, ep, sx=1.0, sy=1.0, sz=1.0):
    connector_ents = add_connector(parent, bc, s/1.0 if s > 0.1 else s, ep, sx, sy, sz)
    ear = [Entity(parent=parent, model='sphere', color=bc,
                   scale=Vec3(s*0.18, s*0.28, s*0.12), position=ep)]
    return ear + (connector_ents if connector_ents else [])


@register('fin', 'FIN', c8(100,220,220),
          default_offset=lambda s: Vec3(0, s*0.5, -s*0.3))
def _fin(parent, bc, s, ep, sx=1.0, sy=1.0, sz=1.0):
    return [Entity(parent=parent, model='cube', color=lighter(bc, 0.12),
                   scale=Vec3(s*0.06, s*0.30, s*0.40), position=ep)]
