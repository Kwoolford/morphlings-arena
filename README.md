# Morphlings Arena

A Spore-inspired creature creator and wave-survival arena built with Python + Ursina.

## Quick Start

```bash
uv run python main.py
```

Requires Python 3.12+ and Ursina ≥ 8.3.0 (installed automatically via `uv`).

---

## What It Is

**Creature Creator** — sculpt your Morphling by clicking parts onto a 3D body.
Stretch the body shape on three axes, mirror limbs, adjust scale and colour,
then send it into battle.

**Wave Arena** — your creature fights progressively harder waves of randomly
generated enemies. Early waves are manageable; by wave 10 enemies are grotesque;
by wave 20 they are comically over-mutated monstrosities stacked with 30+ parts.

**Between Waves** — pick 1 of 3 randomly drawn upgrades. Upgrades range from
common stat bumps to legendary game-changers (PHOENIX, WRATH, SPEED DEMON…).
Rarer upgrades appear more often as waves increase.

**Creator Budget** — every 3 waves you earn +2 mutation budget points, letting
you add more parts to your creature between runs.

---

## Controls

### Sculptor
| | |
|-|-|
| Drag (LMB / RMB) | Spin camera |
| W / S | Camera height |
| Scroll | Zoom |
| Click body | Place active part |
| Click part | Select part |
| MOVE button | Reposition selected part |
| Delete / Backspace | Remove selected part |
| ESC | Cancel / quit |

### Arena
| | |
|-|-|
| WASD / Arrows | Pan camera |
| Q / E | Orbit |
| Z / X | Tilt pitch |
| Scroll | Zoom |
| F | Follow mode |
| P | Pause |
| R | Reset (wave 1) |
| C | Back to creator |
| ESC | Quit |

---

## File Structure

```
main.py           entry point, mode switch
sculptor.py       creature editor
arena.py          wave combat, Morphling AI
waves.py          enemy generation & difficulty
upgrades.py       35+ tiered upgrades
render.py         shared creature rendering
parts.py          part registry & builders
creature_data.py  data model, save/load
abilities.py      ability metadata
morphs.py         preset creature templates
config.py         palette & colour helpers
saves/            player creature save (auto-created)
```

---

## Upgrade Rarities

| Rarity | Colour | Example |
|--------|--------|---------|
| Common | Gray | +25 HP, +Speed |
| Uncommon | Green | Shield, Regen, +60 HP |
| Rare | Blue | Fireball, Spear Throw, +Damage III |
| Epic | Purple | Laser Eyes, Berserk, Lifesteal |
| Legendary | Gold | WRATH (2× dmg), PHOENIX (revive), SPEED DEMON (3× spd) |
