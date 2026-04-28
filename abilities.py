"""
Ability definitions. Each ability has metadata (color, range, cooldown)
plus a description. Behaviour is implemented in Morphling.use_ability.

To add a new ability:
  1. Add an AbilityDef entry to ABILITIES below.
  2. Add a matching branch in arena.Morphling.use_ability for its effect.
  3. Optionally wire it into abilities_for() so creatures with certain
     parts automatically start with it.

TODO: 'poison' ability — applies a damage-over-time debuff
TODO: 'summon' ability — spawns a small temporary minion
TODO: 'explode' ability — self-destruct for massive AOE (suicidal use)
TODO: ability charge system — holding the button charges for a stronger version
TODO: combo abilities — two abilities that chain (freeze → shatter for bonus dmg)
"""
from dataclasses import dataclass

from ursina import color
from config import c8


@dataclass(frozen=True)
class AbilityDef:
    name: str
    color: object       # Ursina Color
    range: float        # max distance to consider using
    cooldown: float     # seconds between uses
    description: str = ''


ABILITIES = {
    'fireball':  AbilityDef('fireball',  color.orange,    12, 2.5, 'Slow lobbed projectile'),
    'snipe':     AbilityDef('snipe',     color.red,       18, 3.5, 'Long-range single shot'),
    'freeze':    AbilityDef('freeze',    color.azure,     10, 5.0, 'Slows the target briefly'),
    'heal':      AbilityDef('heal',      color.lime,       0, 7.0, 'Restores 28% HP'),
    'shockwave': AbilityDef('shockwave', color.yellow,     5, 4.0, 'AoE burst around self'),
    'shield':    AbilityDef('shield',    color.cyan,       0, 5.5, 'Reduces damage 92%'),
    'dash':      AbilityDef('dash',      color.white,      8, 3.0, 'Closes distance + hits'),
    'spear':     AbilityDef('spear',     c8(139,90,43),   16, 2.8, 'Fast linear projectile'),
    'laser':     AbilityDef('laser',     c8(255,0,220),   14, 3.2, 'Twin pulse beams'),
}

ALL_AB = list(ABILITIES.keys())


# Part type → ability granted by that part (for part-based ability system)
PART_ABILITY = {
    'arm':   'spear',
    'eye':   'laser',
    'horn':  'shockwave',
    'wing':  'dash',
    'leg':   None,       # legs provide passive speed, not an ability
    'tail':  None,       # tail provides passive dodge
    'spike': None,       # spike provides passive reflect
    'mouth': None,
    'ear':   None,
    'fin':   None,
}


def abilities_for(cd):
    """Map a CreatureData (via its mutation counts) to its granted ability list."""
    out = []
    if cd.arms >= 2:    out.append('spear')
    elif cd.arms == 1:  out.append('fireball')
    if cd.eyes >= 1:    out.append('laser')
    if cd.wings:        out.append('dash')
    if cd.horns:        out.append('shockwave')
    if not out:         out.append('fireball')
    return out
