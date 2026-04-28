"""
Creature data model.

POSITION CONVENTION (v2):
    px, py, pz are stored NORMALIZED to body radius. A part on the front face of
    the body has roughly pz=0.52, px=0, py=0. The actual world position is
    Vec3(px, py, pz) * cd.bs at render time. This makes parts follow the body
    when body_size changes — fixing the "parts move when size changes" bug.

    v1 saves stored absolute positions; load() migrates them automatically.
    v3 adds body_sx/sy/sz shape axes.
"""
from dataclasses import dataclass, field, asdict
import json, os

# Mutation budget is enforced in the sculptor at placement time.
MUTATION_BUDGET = 12

# Cost of one of each part type (used to compute total spend)
MUTATION_COSTS = {
    'arms': 1, 'eyes': 1, 'legs': 1, 'horns': 1,
    'tail': 1, 'wings': 2, 'spikes': 1,
}

# Caps for the legacy menu-style creator. The sculptor doesn't enforce these
# per-part — only the budget does. Keep them around for clamp safety.
MAX_MUTATIONS = {
    'arms': 4, 'eyes': 2, 'legs': 2, 'horns': 1,
    'tail': 1, 'wings': 1, 'spikes': 1,
}

MUTATION_DESC = {
    'arms':   'Throw Spears',
    'eyes':   'Laser Beams',
    'legs':   'Move Faster',
    'horns':  'Shockwave',
    'tail':   'Dodge Hits',
    'wings':  'Blink Dash (2pt)',
    'spikes': 'Reflect Dmg',
}

SAVE_PATH = 'saves/my_creature.json'

CREATURE_NAMES = [
    'My Morphling', 'Blobby', 'Spudster', 'Glorp', 'Wriggle',
    'Chomper', 'Zippity', 'Flumph', 'Squonk', 'Blorb',
    'Gribble', 'Puffkin', 'Slurk', 'Wendigo Jr.', 'Snort',
]

# Maps a sculptor part type to the legacy mutation key it contributes to.
# Source of truth lives in parts.PART_REGISTRY (`mut_key`); kept here as a
# fallback so creature_data.py does not import the parts module.
PART_TO_MUT = {
    'arm': 'arms', 'eye': 'eyes', 'leg': 'legs',
    'horn': 'horns', 'tail': 'tail', 'wing': 'wings', 'spike': 'spikes',
}

CURRENT_SAVE_VERSION = 6


@dataclass
class PartData:
    type:             str   = 'arm'
    px:               float = 0.0   # NORMALIZED position (body-radius units)
    py:               float = 0.0
    pz:               float = 0.0
    rot_y:            float = 0.0
    scale:            float = 1.0
    color_idx:        int   = -1    # -1 = inherit body color
    socket_id:        int   = -1    # -1 = freeform; >=0 = socket index on body grid
    parent_socket_id: int   = -1    # -1 = attached to body; >=0 = attached to parent part's output socket

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d):
        return PartData(**{k: v for k, v in d.items()
                           if k in PartData.__dataclass_fields__})


@dataclass
class CreatureData:
    name:       str   = 'My Morphling'
    color_idx:  int   = 0
    body_size:  float = 0.5
    # Body shape axes — visual scale multipliers on top of bs
    body_sx:    float = 1.0   # width  (X)
    body_sy:    float = 1.0   # height (Y)
    body_sz:    float = 1.0   # depth  (Z)
    # Legacy integer mutation counts (kept in sync with `parts` for arena stats)
    arms:       int   = 0
    eyes:       int   = 0
    legs:       int   = 0
    horns:      int   = 0
    tail:       int   = 0
    wings:      int   = 0
    spikes:     int   = 0
    # Stats / records
    wins:        int  = 0
    kills:       int  = 0
    best_score:  int  = 0
    bonus_budget: int = 0   # extra mutation points earned by surviving waves
    difficulty: str = 'normal'  # arena difficulty mode
    # Forge system (persistent upgrades)
    spine_crystals: int = 0   # earned per wave survived, persists across runs
    forge_dmg_bonus: float = 0.0   # permanent damage bonus
    forge_hp_bonus: float = 0.0    # permanent max health bonus
    forge_spd_bonus: float = 0.0   # permanent speed bonus
    forge_lucky: bool = False      # first upgrade of run is >=uncommon
    forge_iron_start: bool = False # start with 2s shield each run
    # Sculptor parts
    parts:      list  = field(default_factory=list)
    version:    int   = CURRENT_SAVE_VERSION

    # ── Parts helpers ─────────────────────────────────────────────────────────
    def get_parts(self):
        """Return list of PartData objects (parts may be stored as dicts on load)."""
        out = []
        for p in self.parts:
            out.append(p if isinstance(p, PartData) else PartData.from_dict(p))
        return out

    def count_parts(self, ptype):
        return sum(1 for p in self.get_parts() if p.type == ptype)

    def _sync_mutation_counts(self):
        """Keep legacy integer fields aligned with placed parts (for arena stats)."""
        self.arms   = self.count_parts('arm')
        self.eyes   = self.count_parts('eye')
        self.legs   = self.count_parts('leg')
        self.horns  = self.count_parts('horn')
        self.tail   = self.count_parts('tail')
        self.wings  = self.count_parts('wing')
        self.spikes = self.count_parts('spike')

    # ── Derived stats ─────────────────────────────────────────────────────────
    @property
    def bs(self):
        """Body radius scale factor."""
        return 0.65 + self.body_size * 0.5   # 0.65 – 1.15

    @property
    def speed(self):
        return 3.0 + self.legs * 0.65 + self.wings * 0.4

    @property
    def max_health(self):
        return 70.0 + self.body_size * 65.0

    @property
    def base_damage(self):
        return 8.0 + self.arms * 2.5 + self.horns * 3.5

    @property
    def aggro_range(self):
        return 9.0 + self.eyes * 3.0

    @property
    def dodge_chance(self):
        return self.tail * 0.18

    @property
    def spike_reflect(self):
        return self.spikes * 0.30

    # ── Budget ────────────────────────────────────────────────────────────────
    def mutation_spend(self):
        """Total cost of placed parts."""
        self._sync_mutation_counts()
        return sum(getattr(self, k) * MUTATION_COSTS[k] for k in MUTATION_COSTS)

    def budget_left(self):
        return MUTATION_BUDGET + self.bonus_budget - self.mutation_spend()

    def part_cost(self, ptype):
        """How many budget points adding ONE more of this part type would cost."""
        mut = PART_TO_MUT.get(ptype)
        return MUTATION_COSTS.get(mut, 0) if mut else 0

    def can_afford(self, ptype, mirrored=False):
        """Will placing one (or two if mirrored) of this part type fit in the budget?"""
        cost = self.part_cost(ptype) * (2 if mirrored else 1)
        return cost == 0 or self.budget_left() >= cost

    # ── Convenience ───────────────────────────────────────────────────────────
    def size_label(self):
        return ['Tiny', 'Small', 'Medium', 'Large', 'Huge'][min(4, round(self.body_size * 4))]

    def get_abilities(self):
        from abilities import abilities_for
        return abilities_for(self)

    # ── Persistence ───────────────────────────────────────────────────────────
    def save(self, path=SAVE_PATH):
        self._sync_mutation_counts()
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        data = asdict(self)
        data['parts'] = [p.to_dict() if isinstance(p, PartData) else p for p in self.parts]
        data['version'] = CURRENT_SAVE_VERSION
        with open(path, 'w') as fh:
            json.dump(data, fh, indent=2)

    @classmethod
    def load(cls, path=SAVE_PATH):
        if not os.path.exists(path):
            return cls()
        try:
            with open(path) as fh:
                data = json.load(fh)
            data = _migrate(data)
            parts_raw = data.pop('parts', [])
            obj = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            obj.parts = parts_raw
            return obj
        except Exception:
            return cls()


def _migrate(data):
    """Migrate v1→v2→v3→v4→v5→v6: positions, shape axes, budget, socket grid, part chains."""
    ver = data.get('version', 1)
    if ver < 2 and 'parts' in data:
        bs = 0.65 + data.get('body_size', 0.5) * 0.5
        if bs > 0:
            for p in data['parts']:
                p['px'] = p.get('px', 0.0) / bs
                p['py'] = p.get('py', 0.0) / bs
                p['pz'] = p.get('pz', 0.0) / bs
        data['version'] = 2
    if ver < 3:
        data.setdefault('body_sx', 1.0)
        data.setdefault('body_sy', 1.0)
        data.setdefault('body_sz', 1.0)
        data['version'] = 3
    if ver < 4:
        data.setdefault('bonus_budget', 0)
        data['version'] = 4
    if ver < 5:
        # Socket grid: all existing parts marked as freeform (-1)
        if 'parts' in data:
            for p in data['parts']:
                p.setdefault('socket_id', -1)
        # Spine crystals and forge upgrades
        data.setdefault('spine_crystals', 0)
        data.setdefault('forge_dmg_bonus', 0.0)
        data.setdefault('forge_hp_bonus', 0.0)
        data.setdefault('forge_spd_bonus', 0.0)
        data.setdefault('forge_lucky', False)
        data.setdefault('forge_iron_start', False)
        data['version'] = 5
    if ver < 6:
        # Part chains: all parts attached to body (no parent chains yet)
        if 'parts' in data:
            for p in data['parts']:
                p.setdefault('parent_socket_id', -1)
        data['version'] = 6
    return data
