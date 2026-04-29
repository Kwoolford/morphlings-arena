"""
Creature visual rendering — shared by sculptor preview and arena combat.

All part positions are NORMALIZED (body-radius units) in CreatureData.
Multiply by `cd.bs` to get world-space placement.

Body shape (cd.body_sx/sy/sz) is applied as a visual scale multiplier on top
of the base sphere. The click-detection sphere in the sculptor stays round;
only the rendered mesh stretches.

TODO: body mesh sculpting — replace the sphere with a deformable mesh so the
      player can pull vertices (true Spore-style body editing)
TODO: LOD — far-away arena creatures could use fewer sub-entities
TODO: support non-sphere body primitives ('cube', 'capsule') as body base shapes
TODO: cache part entity trees so do_morph doesn't rebuild from scratch every time
"""
from ursina import Entity, Vec3, color

from config import c8, PALETTE
from parts import make_part, PART_REGISTRY
from sockets import orient_part_for_socket


def add_eyes(parent, hs, offset, iris_color):
    """The default pair of eyes that every creature gets on its head."""
    es = hs * 0.22
    for ss in (-1, 1):
        ex = ss * hs * 0.31
        ey = offset.y + hs * 0.14
        ez = offset.z + hs * 0.47
        Entity(parent=parent, model='sphere', color=color.white, scale=es,
               position=Vec3(ex, ey, ez))
        Entity(parent=parent, model='sphere', color=iris_color, scale=es*0.62,
               position=Vec3(ex, ey, ez+es*0.26))
        Entity(parent=parent, model='sphere', color=color.black, scale=es*0.34,
               position=Vec3(ex, ey, ez+es*0.46))
        Entity(parent=parent, model='sphere', color=color.white, scale=es*0.11,
               position=Vec3(ex+es*0.09, ey+es*0.09, ez+es*0.56))


def build_body_base(parent, bc, bs, sx=1.0, sy=1.0, sz=1.0):
    """Body sphere (shaped by sx/sy/sz) + head lump + base eye pair + nostrils."""
    hs = bs * 0.78
    # Head sits at the top of the (possibly stretched) body sphere
    body_top = bs * sy * 0.5
    hy = body_top + hs * 0.30
    Entity(parent=parent, model='sphere', color=bc, scale=Vec3(bs*sx, bs*sy, bs*sz))
    Entity(parent=parent, model='sphere', color=bc, scale=hs, position=Vec3(0, hy, 0))
    add_eyes(parent, hs, Vec3(0, hy, 0), color.black)
    for ss in (-1, 1):
        Entity(parent=parent, model='sphere', color=c8(255,180,180),
               scale=hs*0.19, position=Vec3(ss*hs*0.37, hy, hs*0.44))


def collect_anim_pivots(entity):
    """Walk entity children recursively, return all with _anim_attr set."""
    result = []
    for child in entity.children:
        if hasattr(child, '_anim_attr'):
            result.append(child)
        result.extend(collect_anim_pivots(child))
    return result


def build_creature(parent, cd):
    """Full creature: body + all placed parts.
    Returns (body_color, body_size, anim_pivots).

    Part attachment:
        - Socket-placed parts (socket_id >= 0): wrap is positioned at body center
          and rotated so the part's natural outward axis aligns with the socket
          outward normal. The part's default_offset places its anchor at the body
          surface naturally.
        - Freeform parts (socket_id == -1): legacy behavior using stored px/py/pz.
    """
    bc = PALETTE[cd.color_idx % len(PALETTE)]
    bs = cd.bs
    sx = getattr(cd, 'body_sx', 1.0)
    sy = getattr(cd, 'body_sy', 1.0)
    sz = getattr(cd, 'body_sz', 1.0)
    build_body_base(parent, bc, bs, sx, sy, sz)
    anim_pivots = []
    for part_idx, pd in enumerate(cd.get_parts()):
        part_bc = PALETTE[pd.color_idx % len(PALETTE)] if pd.color_idx >= 0 else bc
        info = PART_REGISTRY.get(pd.type)

        wrap = Entity(parent=parent)
        wrap._part_idx = part_idx

        if pd.socket_id >= 0 and info:
            # Socket-placed: orient wrap so default_offset places part at the socket
            default_off_fn = info.get('default_offset')
            default_off = default_off_fn(1.0) if default_off_fn else Vec3(0, 0, 1)
            orient_part_for_socket(wrap, pd.socket_id, bs, sx, sy, sz, default_off)
        else:
            # Legacy freeform: use stored normalized position and yaw
            wrap.position = Vec3(pd.px * sx, pd.py * sy, pd.pz * sz) * bs
            wrap.rotation_y = pd.rot_y

        entities = make_part(wrap, pd.type, part_bc, bs, scale_mult=pd.scale, pos=None, sx=sx, sy=sy, sz=sz)
        for e in entities:
            if hasattr(e, '_anim_attr'):
                e._anim_px = pd.px
                anim_pivots.append(e)
    return bc, bs, anim_pivots
