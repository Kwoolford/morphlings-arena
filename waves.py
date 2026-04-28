"""
Wave difficulty parameters and procedural enemy generation.

Enemies scale comically: late-game morphlings stack 15-30+ random parts,
get stretched body shapes, and grow large — pure chaos by wave 15.

Scaling summary:
    Wave  1:  4 enemies, 0–2 extra parts, small bodies
    Wave  5:  8 enemies, 4–15 extra parts, bodies starting to stretch
    Wave 10: 13 enemies, 9–30 extra parts, grotesque silhouettes
    Wave 20: 14 enemies (cap), 19–60 extra parts, comically over-mutated

TODO: elite/boss enemies — one oversized morphling per wave with 3x HP
TODO: enemy ability selection weighted by wave (ranged builds appear later)
TODO: swarm wave variant — 20 tiny weak morphlings instead of few big ones
TODO: wave modifiers ('Haste Wave': all enemies +50% speed, etc.)
TODO: enemy loot drops — killed enemies occasionally drop a pick-up upgrade
TODO: different base morph archetypes per wave bracket (e.g. flyers dominate wave 8)
TODO: part placement clustering — related parts (arm pairs) should spawn symmetrically
"""
import random, math
from creature_data import CreatureData, PartData
from morphs import make as make_morph, MORPH_KEYS

SURFACE_R = 0.52

# Parts that enemies can randomly accumulate
RAND_PARTS = ['arm', 'leg', 'horn', 'spike', 'wing', 'tail', 'eye', 'mouth', 'fin', 'ear']

# Budget bonus given to the creator every N waves
BUDGET_INTERVAL = 3
BUDGET_AMOUNT   = 2


def wave_enemy_count(wave: int) -> int:
    """Number of enemies to spawn this wave."""
    return min(3 + wave, 14)


def wave_mutation_range(wave: int) -> tuple:
    """(min_extra_parts, max_extra_parts) for an enemy on this wave."""
    low  = max(0, wave - 1)
    high = max(low, min(40, wave * 3))
    return low, high


def generate_enemy_cd(wave: int) -> CreatureData:
    """Procedurally build a CreatureData for one enemy at the given wave."""
    cd = make_morph(random.choice(MORPH_KEYS))

    # Increasingly extreme body shape — late game = bizarre silhouettes
    stretch = min(2.4, 1.0 + wave * 0.06)
    cd.body_sx = random.uniform(0.55, stretch)
    cd.body_sy = random.uniform(0.55, stretch)
    cd.body_sz = random.uniform(0.55, stretch)
    cd.body_size = min(1.0, 0.15 + wave * 0.04 + random.random() * 0.30)
    cd.color_idx = random.randint(0, 9)
    cd.name = _gen_name()

    low, high = wave_mutation_range(wave)
    n_extra = random.randint(low, high)
    for _ in range(n_extra):
        _place_random_part(cd, random.choice(RAND_PARTS))

    cd._sync_mutation_counts()
    return cd


def _place_random_part(cd: CreatureData, ptype: str):
    theta = random.uniform(0, math.tau)
    phi   = random.uniform(-math.pi * 0.45, math.pi * 0.45)
    x = math.cos(phi) * math.sin(theta)
    y = math.sin(phi)
    z = math.cos(phi) * math.cos(theta)
    pd = PartData(
        type      = ptype,
        px        = x * SURFACE_R,
        py        = y * SURFACE_R,
        pz        = z * SURFACE_R,
        rot_y     = math.degrees(math.atan2(x, z)),
        scale     = random.uniform(0.55, 2.0),
        color_idx = random.randint(-1, 9),
    )
    cd.parts.append(pd)


_PREFIXES = [
    'Mega', 'Ultra', 'Proto', 'Vile', 'Grim', 'Neon', 'Hyper', 'Void',
    'Feral', 'Chaos', 'Toxic', 'Rogue', 'Abyssal', 'Frenzied', 'Mutant',
]
_SUFFIXES = [
    'Lurker', 'Crusher', 'Blight', 'Gnasher', 'Wraith', 'Brute',
    'Fiend', 'Maw', 'Reaper', 'Scourge', 'Ravager', 'Obliterator',
]


def _gen_name() -> str:
    return f'{random.choice(_PREFIXES)} {random.choice(_SUFFIXES)}'


def total_budget_bonus(wave: int) -> int:
    """Total creator budget bonus earned through completing the given wave."""
    return (wave // BUDGET_INTERVAL) * BUDGET_AMOUNT
