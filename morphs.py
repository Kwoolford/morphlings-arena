"""
Base morph templates — starting points for the player to evolve from.

Positions are normalized (body-radius units). On the unit sphere:
    +x = right,  -x = left
    +y = up,     -y = down
    +z = front,  -z = back

A position with magnitude ~0.52 sits on the body surface.

To add a new morph: append to MORPHS as a (key, builder) entry. The builder
is a zero-arg function returning a fresh CreatureData.
"""
from creature_data import CreatureData, PartData


def _p(t, x, y, z, scale=1.0, color_idx=-1):
    return PartData(type=t, px=x, py=y, pz=z,
                    scale=scale, color_idx=color_idx).to_dict()


def _build_blob():
    return CreatureData(name='Blobby', color_idx=2, body_size=0.5, parts=[])


def _build_crawler():
    return CreatureData(
        name='Crawler', color_idx=3, body_size=0.5, parts=[
            _p('leg',  0.30, -0.45,  0.20),
            _p('leg', -0.30, -0.45,  0.20),
            _p('leg',  0.30, -0.45, -0.20),
            _p('leg', -0.30, -0.45, -0.20),
            _p('mouth', 0.0,  -0.05,  0.50),
        ],
    )


def _build_flyer():
    return CreatureData(
        name='Flyer', color_idx=4, body_size=0.4, parts=[
            _p('wing',  0.55,  0.10,  0.0, scale=1.3),
            _p('wing', -0.55,  0.10,  0.0, scale=1.3),
            _p('tail',  0.0,   0.05, -0.55),
        ],
    )


def _build_spiker():
    return CreatureData(
        name='Spiker', color_idx=0, body_size=0.6, parts=[
            _p('spike',  0.0,   0.55,  0.0),
            _p('spike',  0.45,  0.20,  0.0),
            _p('spike', -0.45,  0.20,  0.0),
            _p('spike',  0.0,   0.20,  0.45),
            _p('spike',  0.0,   0.20, -0.45),
            _p('horn',   0.0,   0.55,  0.30),
            _p('arm',    0.50,  0.0,   0.10),
            _p('arm',   -0.50,  0.0,   0.10),
        ],
    )


def _build_brawler():
    return CreatureData(
        name='Brawler', color_idx=9, body_size=0.75, parts=[
            _p('arm',   0.55,  0.10,  0.05, scale=1.2),
            _p('arm',  -0.55,  0.10,  0.05, scale=1.2),
            _p('leg',   0.25, -0.45,  0.10),
            _p('leg',  -0.25, -0.45,  0.10),
            _p('horn',  0.20,  0.50,  0.20),
            _p('horn', -0.20,  0.50,  0.20),
        ],
    )


def _build_tank():
    return CreatureData(
        name='Tank', color_idx=1, body_size=0.9, body_sx=1.5, body_sy=0.8, body_sz=1.5, parts=[
            _p('leg',   0.35, -0.50,  0.30),
            _p('leg',  -0.35, -0.50,  0.30),
            _p('leg',   0.35, -0.50, -0.30),
            _p('leg',  -0.35, -0.50, -0.30),
            _p('arm',   0.60,  0.0,   0.15, scale=1.1),
            _p('arm',  -0.60,  0.0,   0.15, scale=1.1),
            _p('spike', 0.50,  0.40,  0.40),
            _p('spike',-0.50,  0.40,  0.40),
        ],
    )


def _build_serpent():
    return CreatureData(
        name='Serpent', color_idx=5, body_size=0.6, body_sx=0.6, body_sy=1.8, body_sz=0.6, parts=[
            _p('tail',   0.0,   0.05, -0.55),
            _p('fin',    0.50,  0.30, -0.10),
            _p('fin',   -0.50,  0.30, -0.10),
            _p('horn',   0.0,   0.55,  0.20),
            _p('eye',    0.40,  0.10,  0.45),
            _p('eye',   -0.40,  0.10,  0.45),
        ],
    )


def _build_hydra():
    return CreatureData(
        name='Hydra', color_idx=6, body_size=0.7, parts=[
            _p('arm',    0.50,  0.05,  0.10),
            _p('arm',   -0.50,  0.05,  0.10),
            _p('eye',    0.52,  0.15,  0.10),
            _p('eye',   -0.52,  0.15,  0.10),
            _p('eye',    0.35,  0.30,  0.40),
            _p('eye',   -0.35,  0.30,  0.40),
            _p('horn',   0.25,  0.50,  0.20),
            _p('horn',  -0.25,  0.50,  0.20),
            _p('tail',   0.0,   0.0,  -0.55),
        ],
    )


def _build_mantis():
    return CreatureData(
        name='Mantis', color_idx=7, body_size=0.6, parts=[
            _p('arm',    0.50,  0.15,  0.05, scale=0.8),
            _p('arm',   -0.50,  0.15,  0.05, scale=0.8),
            _p('arm',    0.45,  0.45,  0.05, scale=0.7),
            _p('arm',   -0.45,  0.45,  0.05, scale=0.7),
            _p('eye',    0.40,  0.20,  0.40),
            _p('eye',   -0.40,  0.20,  0.40),
            _p('wing',   0.50,  0.05, -0.05, scale=1.1),
            _p('wing',  -0.50,  0.05, -0.05, scale=1.1),
        ],
    )


def _build_golem():
    return CreatureData(
        name='Golem', color_idx=8, body_size=0.9, body_sx=1.4, body_sy=1.0, body_sz=1.4, parts=[
            _p('arm',    0.60,  0.0,  0.05, scale=1.5),
            _p('arm',   -0.60,  0.0,  0.05, scale=1.5),
            _p('leg',    0.30, -0.45,  0.25),
            _p('leg',   -0.30, -0.45,  0.25),
            _p('spike',  0.40,  0.45,  0.40),
            _p('spike', -0.40,  0.45,  0.40),
        ],
    )


# Public ordered list — what the sculptor's "Load Morph" UI iterates over.
MORPHS = [
    ('blob',     _build_blob),
    ('crawler',  _build_crawler),
    ('flyer',    _build_flyer),
    ('spiker',   _build_spiker),
    ('brawler',  _build_brawler),
    ('tank',     _build_tank),
    ('serpent',  _build_serpent),
    ('hydra',    _build_hydra),
    ('mantis',   _build_mantis),
    ('golem',    _build_golem),
]

MORPH_KEYS = [k for k, _ in MORPHS]


def make(key):
    """Return a fresh CreatureData for the given morph key, or None."""
    for k, fn in MORPHS:
        if k == key:
            return fn()
    return None
