"""Project-wide constants, color helpers, and palette."""
from ursina import color
from ursina.color import Color


# ── Color helpers ─────────────────────────────────────────────────────────────
def c8(r, g, b):
    """0-255 RGB shortcut."""
    return Color(r/255, g/255, b/255, 1)


def ca(r, g, b, a=255):
    """0-255 RGBA shortcut."""
    return Color(r/255, g/255, b/255, a/255)


def darker(c, d=0.12):
    return Color(max(0, c[0]-d), max(0, c[1]-d), max(0, c[2]-d), 1)


def lighter(c, d=0.16):
    return Color(min(1, c[0]+d), min(1, c[1]+d), min(1, c[2]+d), 1)


# ── Window / world ────────────────────────────────────────────────────────────
WINDOW_BG  = c8(12, 12, 22)
ARENA_SIZE = 20

# ── Creature color palette ────────────────────────────────────────────────────
PALETTE = [
    c8(255,120,130), c8(255,185,90),  c8(110,210,130), c8(100,185,255),
    c8(200,135,255), c8(255,225,85),  c8(255,145,200), c8(75, 225,205),
    c8(195,205,255), c8(204,107,61),
]

# ── Persistence ───────────────────────────────────────────────────────────────
SAVE_PATH = 'saves/my_creature.json'
