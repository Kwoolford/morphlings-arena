"""Difficulty settings and presets for arena waves."""
from dataclasses import dataclass


@dataclass
class DifficultyDef:
    """Difficulty preset configuration."""
    label: str
    enemy_hp: float        # Multiplier for enemy health (1.0 = normal)
    enemy_dmg: float       # Multiplier for enemy damage
    wave_scale: float      # Multiplier for wave enemy count
    upgrade_bonus: int     # Bonus/penalty to upgrade rarity draw (+1 = more rare, -1 = less rare)


DIFFICULTIES = {
    'easy': DifficultyDef(
        label='EASY',
        enemy_hp=0.6,
        enemy_dmg=0.6,
        wave_scale=0.7,
        upgrade_bonus=1
    ),
    'normal': DifficultyDef(
        label='NORMAL',
        enemy_hp=1.0,
        enemy_dmg=1.0,
        wave_scale=1.0,
        upgrade_bonus=0
    ),
    'hard': DifficultyDef(
        label='HARD',
        enemy_hp=1.4,
        enemy_dmg=1.3,
        wave_scale=1.3,
        upgrade_bonus=0
    ),
    'nightmare': DifficultyDef(
        label='NIGHTMARE',
        enemy_hp=2.0,
        enemy_dmg=1.7,
        wave_scale=1.6,
        upgrade_bonus=-1
    ),
}


def get_difficulty(key):
    """Get a difficulty definition by key. Defaults to 'normal' if not found."""
    return DIFFICULTIES.get(key, DIFFICULTIES['normal'])


def difficulty_keys():
    """Get list of available difficulty keys."""
    return list(DIFFICULTIES.keys())
