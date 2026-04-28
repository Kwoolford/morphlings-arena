"""
Between-wave upgrade system.

Each upgrade belongs to a rarity tier. Rarer upgrades appear more often in
later waves. The player picks 1 of 3 randomly drawn upgrades after each wave.

Rarity weight table (wave brackets 1-5 / 6-10 / 11-15 / 16-20 / 21+):
    common     55  38  25  15   8
    uncommon   30  30  27  22  16
    rare       12  20  26  28  25
    epic        3   9  16  22  27
    legendary   0   3   6  13  24

TODO: upgrade synergies — some upgrades unlock a bonus when combined
      (e.g. Fireball + Freeze → 'Cryo Burst': frozen targets take 2× fireball dmg)
TODO: upgrade re-roll — spend a currency to redraw the 3 options once per wave
TODO: negative 'curse' upgrades that appear rarely and must be avoided
TODO: persistent upgrade history display so player can review what they hold
TODO: legendary upgrades should have a unique visual effect on the creature model
      (e.g. PHOENIX adds a flame aura, TITAN grows the body size in-arena)
TODO: wave-specific upgrade pools (e.g. only healing upgrades offered on wave 1)
TODO: upgrade tier-up — holding 3 of the same rarity auto-combines into one rarity higher
"""
from dataclasses import dataclass
from typing import Callable
import random

RARITY_ORDER  = ['common', 'uncommon', 'rare', 'epic', 'legendary']

# RGB tuples — converted to Ursina Color objects in the arena UI
RARITY_RGB = {
    'common':    (170, 170, 170),
    'uncommon':  ( 70, 210,  70),
    'rare':      ( 60, 130, 255),
    'epic':      (190,  50, 255),
    'legendary': (255, 175,   0),
}

# Per-rarity weights at 5-wave brackets  [1-5, 6-10, 11-15, 16-20, 21+]
_WEIGHTS = {
    'common':    [55, 38, 25, 15,  8],
    'uncommon':  [30, 30, 27, 22, 16],
    'rare':      [12, 20, 26, 28, 25],
    'epic':      [ 3,  9, 16, 22, 27],
    'legendary': [ 0,  3,  6, 13, 24],
}


def _bracket(wave: int) -> int:
    return min(4, (wave - 1) // 5)


def _weights_for_wave(wave: int) -> dict:
    i = _bracket(wave)
    return {r: _WEIGHTS[r][i] for r in RARITY_ORDER}


@dataclass
class Upgrade:
    key:    str
    name:   str
    desc:   str
    rarity: str
    apply:  Callable  # fn(morphling) -> None


def _mk(key, name, desc, rarity, fn):
    return Upgrade(key=key, name=name, desc=desc, rarity=rarity, apply=fn)


def _hp(m, n):
    m.max_health += n
    m.health = min(m.health + n, m.max_health)

def _ab(m, ab):
    if not hasattr(m, 'abilities'):   return
    if not hasattr(m, 'ab_cd'):       return
    if ab not in m.abilities:
        m.abilities.append(ab)
        m.ab_cd[ab] = 0.0


ALL_UPGRADES = [
    # ── COMMON ───────────────────────────────────────────────────────────────
    _mk('hp1',      '+25 Max HP',       'Gain 25 max HP and heal for it.',       'common',
        lambda m: _hp(m, 25)),
    _mk('spd1',     '+Speed',           'Movement speed +0.5.',                  'common',
        lambda m: setattr(m, 'speed', m.speed + 0.5)),
    _mk('dmg1',     '+Damage',          'Base damage +4.',                       'common',
        lambda m: setattr(m, 'base_damage', m.base_damage + 4)),
    _mk('rng1',     '+Range',           'Detection range +3.',                   'common',
        lambda m: setattr(m, 'aggro_range', m.aggro_range + 3)),
    _mk('heal1',    'Quick Heal',       'Restore 20% of max HP now.',            'common',
        lambda m: _hp(m, int(m.max_health * 0.20))),
    _mk('dodge1',   'Nimble',           'Dodge chance +10%.',                    'common',
        lambda m: setattr(m, 'dodge_chance', min(0.90, m.dodge_chance + 0.10))),

    # ── UNCOMMON ─────────────────────────────────────────────────────────────
    _mk('hp2',      '+60 Max HP',       'Gain 60 max HP and heal for it.',      'uncommon',
        lambda m: _hp(m, 60)),
    _mk('dmg2',     '+Damage II',       'Base damage +12.',                      'uncommon',
        lambda m: setattr(m, 'base_damage', m.base_damage + 12)),
    _mk('spd2',     '+Speed II',        'Movement speed +1.2.',                  'uncommon',
        lambda m: setattr(m, 'speed', m.speed + 1.2)),
    _mk('shield',   'Iron Shield',      'Gain Shield ability.',                  'uncommon',
        lambda m: _ab(m, 'shield')),
    _mk('heal2',    'Rejuvenate',       'Restore 40% HP now.',                   'uncommon',
        lambda m: _hp(m, int(m.max_health * 0.40))),
    _mk('regen',    'Regeneration',     'Slowly regain HP over time.',           'uncommon',
        lambda m: setattr(m, '_regen_rate',
                          getattr(m, '_regen_rate', 0) + m.max_health * 0.008)),
    _mk('reflect1', 'Thorn Skin',       'Reflect 20% of incoming damage back.', 'uncommon',
        lambda m: setattr(m, 'spike_reflect', m.spike_reflect + 0.20)),

    # ── RARE ─────────────────────────────────────────────────────────────────
    _mk('fireball', 'Fireball',         'Gain Fireball ranged attack.',          'rare',
        lambda m: _ab(m, 'fireball')),
    _mk('freeze',   'Freeze Ray',       'Gain Freeze shot ability.',             'rare',
        lambda m: _ab(m, 'freeze')),
    _mk('hp3',      '+120 Max HP',      'Gain 120 max HP.',                      'rare',
        lambda m: _hp(m, 120)),
    _mk('dmg3',     '+Damage III',      'Base damage +22.',                      'rare',
        lambda m: setattr(m, 'base_damage', m.base_damage + 22)),
    _mk('spd3',     '+Speed III',       'Movement speed +2.0.',                  'rare',
        lambda m: setattr(m, 'speed', m.speed + 2.0)),
    _mk('dodge2',   'Evasion',          'Dodge chance +25%.',                    'rare',
        lambda m: setattr(m, 'dodge_chance', min(0.90, m.dodge_chance + 0.25))),
    _mk('spear',    'Spear Throw',      'Gain Spear Throw ranged ability.',      'rare',
        lambda m: _ab(m, 'spear')),
    _mk('lifesteal','Vampiric',         'Heal 15% of all damage dealt.',        'rare',
        lambda m: setattr(m, '_lifesteal',
                          getattr(m, '_lifesteal', 0) + 0.15)),

    # ── EPIC ─────────────────────────────────────────────────────────────────
    _mk('laser',    'Laser Eyes',       'Gain dual Laser Beam ability.',         'epic',
        lambda m: _ab(m, 'laser')),
    _mk('heal_ab',  'Healing Touch',    'Gain Heal ability.',                    'epic',
        lambda m: _ab(m, 'heal')),
    _mk('berserk',  'Berserk Rage',     '+60% damage when HP below 40%.',       'epic',
        lambda m: setattr(m, '_berserk', True)),
    _mk('hp4',      'Colossal HP',      '+200 max HP, full heal.',               'epic',
        lambda m: _hp(m, 200)),
    _mk('snipe',    'Sniper Round',     'Gain long-range Snipe ability.',        'epic',
        lambda m: _ab(m, 'snipe')),
    _mk('reflect2', 'Spike Armor',      'Reflect 40% of incoming damage.',      'epic',
        lambda m: setattr(m, 'spike_reflect', m.spike_reflect + 0.40)),
    _mk('shockwave','Shockwave',        'Gain AOE Shockwave ability.',           'epic',
        lambda m: _ab(m, 'shockwave')),
    _mk('lifesteal2','Drain Aura',      'Heal 30% of all damage dealt.',        'epic',
        lambda m: setattr(m, '_lifesteal',
                          getattr(m, '_lifesteal', 0) + 0.30)),
    _mk('dash',     'Blink Dash',       'Gain Blink Dash ability.',              'epic',
        lambda m: _ab(m, 'dash')),

    # ── LEGENDARY ────────────────────────────────────────────────────────────
    _mk('wrath',     'WRATH',           'Your base damage is DOUBLED.',          'legendary',
        lambda m: setattr(m, 'base_damage', m.base_damage * 2.0)),
    _mk('titan',     'TITAN',           '+250 HP and speed +30%.',              'legendary',
        lambda m: (_hp(m, 250), setattr(m, 'speed', m.speed * 1.30))),
    _mk('phoenix',   'PHOENIX',         'Revive once at 50% HP on death.',      'legendary',
        lambda m: setattr(m, '_phoenix', True)),
    _mk('all_ab',    'MUTATION SURGE',  'Unlock ALL abilities instantly.',      'legendary',
        lambda m: [_ab(m, a) for a in
                   ['fireball','spear','laser','freeze','snipe',
                    'heal','shockwave','shield','dash']]),
    _mk('overdrive', 'OVERDRIVE',       'Damage scales with missing HP.',       'legendary',
        lambda m: setattr(m, '_overdrive', True)),
    _mk('speed_god', 'SPEED DEMON',     'Movement speed is TRIPLED.',           'legendary',
        lambda m: setattr(m, 'speed', m.speed * 3.0)),
    _mk('deathbomb', 'DEATH BOMB',      'Explode for huge AOE damage on death.','legendary',
        lambda m: setattr(m, '_deathbomb', True)),
    _mk('mirror',    'MIRROR SHIELD',   'Reflect 60% damage + +50% HP.',       'legendary',
        lambda m: (setattr(m, 'spike_reflect', m.spike_reflect + 0.60),
                   _hp(m, int(m.max_health * 0.50)))),
]


def pick_upgrades(wave: int, count: int = 3) -> list:
    """Return `count` distinct Upgrade objects, rarity-weighted for this wave."""
    w    = _weights_for_wave(wave)
    pool = []
    wts  = []
    for r in RARITY_ORDER:
        for u in [x for x in ALL_UPGRADES if x.rarity == r]:
            pool.append(u)
            wts.append(w[r])

    chosen, seen = [], set()
    for _ in range(400):
        if len(chosen) >= count:
            break
        u = random.choices(pool, weights=wts, k=1)[0]
        if u.key not in seen:
            chosen.append(u)
            seen.add(u.key)
    return chosen
