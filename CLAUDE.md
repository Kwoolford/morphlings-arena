# CLAUDE.md — Morphlings Arena

## Project Overview

A Spore-inspired creature creator + wave-survival arena built with Python 3.12
and the Ursina 3D engine. The player sculpts a creature in the editor, then
sends it into progressively harder waves of procedurally mutated enemies.

## Tooling

```bash
uv run python main.py   # launch
uv add <package>        # add dependency
```

Python 3.12+, Ursina ≥ 8.3.0.

---

## Module Map

| File | Responsibility |
|------|---------------|
| `main.py` | App entry point; mode switch (creator ↔ arena) |
| `sculptor.py` | Spore-style creature editor (click-to-place parts) |
| `arena.py` | Wave combat scene: Morphling AI, Projectile, Arena orchestrator |
| `waves.py` | Wave difficulty params + procedural enemy CD generation |
| `upgrades.py` | 35+ tiered upgrades (common→legendary), pick-3 rarity draw |
| `render.py` | Shared creature rendering (sculptor preview + arena) |
| `parts.py` | Part registry: builders, labels, animation metadata |
| `creature_data.py` | `CreatureData` + `PartData` dataclasses, save/load, migrations |
| `abilities.py` | Ability metadata (`AbilityDef`); effects live in `Morphling.use_ability` |
| `morphs.py` | Named preset creatures (templates for the sculptor Load Morph UI) — 10 templates |
| `config.py` | Palette, color helpers (`c8`, `ca`, `darker`, `lighter`), constants |
| `debug.py` | Debug visualization system (hitboxes, aggro ranges, part attachment, body ellipsoid) |
| `difficulty.py` | Difficulty mode presets (Easy/Normal/Hard/Nightmare) |
| `environment.py` | Arena obstacle generation + obstacle-aware AI steering |

---

## Architecture Notes

### Position convention (v2+)
Part positions in `PartData` are **normalized to body-radius units** — a value
of `(0, 0, 0.52)` means "on the front face of the body", regardless of body
size. At render time everything is multiplied by `cd.bs`.  
Migration from v1 (absolute positions) is handled in `creature_data._migrate()`.

### Body shape
`CreatureData.body_sx/sy/sz` are visual scale multipliers applied on top of
`bs`. The sculptor's click-detection sphere stays round; only the rendered mesh
stretches.

### Wave state machine
```
wave_start → (timer) → fighting → (all enemies dead) → wave_clear
    → (timer) → upgrade_pick → (player picks) → intermission
    → (optional budget banner) → wave_start (next wave)
```
State strings live as constants `_FIGHTING`, `_WAVE_START`, etc. at the top of
`arena.py`. Always use the constants — never compare to raw strings.

### Part animation
Parts that want idle/walk animation return a **pivot Entity** from their builder
with these attributes set:
- `_anim_attr` — Ursina attribute to oscillate (e.g. `'rotation_z'`)
- `_anim_amp` — amplitude in degrees
- `_anim_freq` — oscillations per second

Left/right phase is derived from `pd.px` sign at animation time. The sculptor's
`on_update` and `Morphling.update` both run the same loop over collected pivots.

### Upgrade effects
Upgrades in `upgrades.py` set fields directly on the `Morphling` instance
(`_berserk`, `_phoenix`, `_regen_rate`, `_lifesteal`, `_overdrive`,
`_deathbomb`). Morphling.update() and take_damage() check these each frame.
The `damage_mult` property composes `_berserk` + `_overdrive` multipliers.

### Budget system
`CreatureData.bonus_budget` is earned at a rate of +2 per 3 waves survived.
It widens `budget_left()` so the sculptor allows more mutations after a strong
arena run. Saved to `saves/my_creature.json` immediately on grant.

### Save format
`saves/my_creature.json`, version 4+. Migrations: `_migrate()` in
`creature_data.py`. Current fields added per version:
- v2: normalized part positions
- v3: `body_sx`, `body_sy`, `body_sz`
- v4: `bonus_budget`

### Part floating bug fix
**Fixed in v4.1**: Part positions now correctly apply body shape scaling.
Old formula: `Vec3(px, py, pz) * bs`
New formula: `Vec3(px*sx, py*sy, pz*sz) * bs`
This ensures parts sit flush on ellipsoid-shaped bodies when `body_sx/sy/sz ≠ 1.0`.

### Debug overlay system
Press F-keys in sculptor or arena to toggle debug visualizations:
- **F1**: Hitbox spheres (melee collision radius around creatures)
- **F2**: Aggro range rings + vision cone pie slices (shows creature detection zones)
- **F3**: Part attachment cubes + connector lines (shows where parts attach)
- **F4**: Body ellipsoid wireframe (shows stretched body shape)

Useful for understanding why limbs aren't attaching correctly or AI isn't responding.

### Difficulty modes
Four difficulty presets affect enemy stats and wave scaling:
- **Easy**: 0.6× enemy HP/damage, 0.7× wave scale, +1 upgrade rarity
- **Normal**: 1.0× (baseline)
- **Hard**: 1.4× HP, 1.3× damage, 1.3× wave scale
- **Nightmare**: 2.0× HP, 1.7× damage, 1.6× wave scale

Selected at sculptor mode (to be wired to UI in future). Saved to `CreatureData.difficulty`.

### Environment obstacles
Each wave generates procedural obstacles (rocks, pillars, crystals) that:
- Increase in number/size with wave difficulty
- Block pathfinding and force AI to steer around them
- Use simple occupancy grid + distance checks for collision
- Are generated fresh each wave in `_begin_next_wave()`

AI uses `arena.environment.get_steer_direction()` to avoid blocked paths with ~50% strength nudge.

### AI vision and target acquisition
Creatures have a `vision_cone` attribute (default 360° for full awareness):
- Currently always visible; future upgrades can reduce vision_cone
- Target acquisition: nearest living creature within `aggro_range`
- Alert state: instantly acquire target if hit by out-of-cone attacker (future)
- Debug F2 shows vision cone as pie-slice ring

---

## Controls

### Sculptor
| Input | Action |
|-------|--------|
| Drag (LMB/RMB) | Spin camera (yaw only — pitch locked) |
| W / S | Camera height |
| Scroll | Zoom |
| Click body | Place active part type |
| Click part | Select placed part |
| MOVE button | Click body to reposition selected part |
| ESC | Cancel pick/selection, or quit |
| Delete / Backspace | Delete selected part |

### Arena
| Input | Action |
|-------|--------|
| WASD / Arrows | Pan camera |
| Q / E | Orbit camera |
| Z / X | Tilt camera pitch |
| Scroll | Zoom |
| F | Toggle follow mode |
| P | Pause / unpause |
| R | Reset arena (restarts from wave 1) |
| C | Return to creator |
| ESC | Quit (always works, even during upgrade pick) |

---

## Adding Things

### New part type
In `parts.py`, decorate a builder function:
```python
@register('claw', 'CLAW', c8(200,80,80), mirror_default=True,
          mut_key='arms', default_offset=lambda s: Vec3(s*0.58, 0.05, 0))
def _claw(parent, bc, s, ep):
    pivot = Entity(parent=parent, position=ep)
    pivot._anim_attr = 'rotation_z'
    pivot._anim_amp  = 20.0
    pivot._anim_freq = 1.3
    # ... add child entities to pivot ...
    return [pivot]
```
The part automatically appears in the sculptor palette and arena rendering.

### New ability
1. Add `AbilityDef` to `ABILITIES` in `abilities.py`.
2. Add matching branch in `Morphling.use_ability` in `arena.py`.
3. Optionally reference it from `upgrades.py` or `abilities_for()`.

### New upgrade
In `upgrades.py`, add to `ALL_UPGRADES`:
```python
_mk('key', 'NAME', 'One-line description.', 'rare',
    lambda m: setattr(m, 'some_field', new_value)),
```

### New morph template
In `morphs.py`, add a builder function and append to `MORPHS`.

---

## Morph Templates (10 total)
| Name | Body Size | Shape | Key Parts | Role |
|------|-----------|-------|-----------|------|
| Blob | 0.5 | sphere | none | pure body |
| Crawler | 0.5 | sphere | 4 legs, mouth | grounded |
| Flyer | 0.4 | sphere | 2 wings, tail | airborne (cosmetic) |
| Spiker | 0.6 | sphere | 5 spikes, horn, 2 arms | ranged/melee hybrid |
| Brawler | 0.75 | sphere | 2 large arms, 2 legs, 2 horns | melee brawler |
| Tank | 0.9 | disc (1.5/0.8/1.5) | 4 legs, 2 arms, 2 spikes | durable tank |
| Serpent | 0.6 | tall (0.6/1.8/0.6) | tail, 2 fins, horn, 2 eyes | agile striker |
| Hydra | 0.7 | sphere | 2 arms, 4 eyes, 2 horns, tail | all-sensing |
| Mantis | 0.6 | sphere | 4 small arms, 2 eyes, 2 wings | scuttler |
| Golem | 0.9 | boulder (1.4/1.0/1.4) | 2 huge arms, 2 legs, 2 spikes | bruiser |

---

## Known Limitations / Deferred Work

- Body click-detection sphere does not track body shape axes (always round)
- Difficulty selector UI not wired in sculptor (set in creature_data directly)
- Full environment creator tool not implemented (static generation only)
- Skybox system planned but not implemented (needs texture assets)
- No sound effects
- No player-controlled movement (creature AI-controls itself in arena)
- Upgrade cards have no keyboard shortcuts (1/2/3)
- No persistent leaderboard beyond single best-score
- Vision cone currently always 360° (upgradeable field exists but not used)

See inline `TODO:` comments throughout the codebase for granular next steps.
