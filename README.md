# Morphlings Arena

A Spore-inspired creature creator + wave-survival roguelike. Sculpt a morphling from 10+ body parts, then battle increasingly grotesque procedurally-generated enemies across 20+ waves. Earn currency, unlock permanent upgrades, and master the perfect creature design.

**GitHub**: https://github.com/Kwoolford/morphlings-arena

## Quick Start

```bash
uv run python main.py
```

**Requires**: Python 3.12+, Ursina ≥ 8.3.0 (auto-installed via `uv`)

---

## Core Systems (v5)

### 🎨 Creature Sculptor
- **Click-to-place** arms, legs, wings, horns, spikes, eyes, tails, fins, mouths, ears
- **Socket grid** (24 attachment points): parts snap to nearest socket → guaranteed clean attachment
- **Body shaping**: stretch width/height/depth axes independently
- **Mirror mode**: auto-place symmetric limbs
- **Preset morphs** (10): Blob, Crawler, Flyer, Spiker, Brawler, Tank, Serpent, Hydra, Mantis, Golem
- **Mutation budget**: 12 base points (earn +2 per 3 waves survived in arena)
- **Debug views** (F1-F4): hitboxes, aggro ranges, part attachment, body ellipsoid

### ⚔️ Wave Arena
- **Progressive enemies**: spawn count, size, complexity scale with waves
- **Procedural generation**: each enemy is randomly mutated from a base template
- **Enemy AI**: chase, flank, use ranged abilities, dodge, apply passives
- **Combat upgrades** (35 total): pick 1 of 3 per wave, rarity increases with difficulty
- **Difficulty modes**: Easy/Normal/Hard/Nightmare (affect enemy stats and upgrade draws)
- **Environmental obstacles**: rocks, pillars, crystals block pathfinding and force tactical movement
- **Smite ability** (purchasable): click to drop a massive sword (AoE 250 dmg/5 units)

### 💎 Two-Tier Currency

**Morph Shards** (in-run, resets each game)
- Earn: 10 per enemy killed
- Spend: emergency heal, shield, speed boost, smite charges, wave banish, refresh upgrades
- Shop auto-opens after wave clear and upgrade pick
- Accessible anytime via 'B' key

**Spine Crystals** (persistent, saved to character file)
- Earn: number of waves survived per run
- Spend: "Morphling Forge" to unlock permanent bonuses
  - +Damage Core (+5 base dmg, max 5×)
  - +Health Matrix (+15 max HP, max 5×)
  - +Speed Shard (+0.2 speed, max 5×)
  - +Budget Expander (+1 mutation budget, max 3×)
  - Lucky Spark (first upgrade ≥uncommon, 1×)
  - Iron Start (begin with 2s shield, 1×)

### 🎯 Debug Overlays
Press F1-F4 to toggle:
- **F1**: Hitbox spheres (melee collision radius)
- **F2**: Aggro range rings + vision cone visualizations
- **F3**: Part attachment points (cubes + connector lines)
- **F4**: Body ellipsoid wireframe (shows body shape stretching)

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

## Upgrade System (35 Total)

| Rarity | Count | Examples | Mechanic |
|--------|-------|----------|----------|
| Common | 6 | +HP, +Speed, +Damage, Quick Heal, Nimble | Stat boosts |
| Uncommon | 7 | Shield, Regen, Thorn Skin, Rejuvenate | Passive effects |
| Rare | 8 | Fireball, Freeze, Spear Throw, Vampiric, Evasion | Abilities + advanced |
| Epic | 9 | Laser Eyes, Berserk, Colossal, Spike Armor | Powerful passives |
| Legendary | 8 | WRATH (2× dmg), PHOENIX (revive), OVERDRIVE (scaling dmg), SPEED DEMON (3× spd), DEATH BOMB (AoE explode), MUTATION SURGE (all abilities) | Game-changing |

---

## Abilities (9 Total)

| Ability | Colour | Range | Cooldown | Triggered By |
|---------|--------|-------|----------|--------------|
| Fireball | Orange | 12 | 2.5s | 1 arm (default) |
| Spear | Brown | 16 | 2.8s | 2+ arms |
| Snipe | Red | 18 | 3.5s | Eyes |
| Freeze | Azure | 10 | 5s | Upgrade |
| Laser | Magenta | 14 | 3.2s | Eye part |
| Dash | White | 8 | 3s | Wings |
| Shockwave | Yellow | 5 | 4s | Horns |
| Heal | Lime | Self | 7s | Upgrade |
| Shield | Cyan | Self | 5.5s | Upgrade |

---

## Architecture Vision

### Current (v5)
- **Part placement**: flat list on 24-point socket grid
- **Attachment**: guaranteed socket snaps prevent floating
- **Animation**: simple sine wave oscillation per limb
- **Save format**: CreatureData with normalized positions

### Near-term Roadmap (1-2 sprints)
- [ ] Socket grid UI visualization (ring indicators for snapping)
- [ ] Per-part animation phase offsets (no two arms swing identically)
- [ ] CoM dot fixes for body shape axes
- [ ] Difficulty selector UI in sculptor

### Medium-term (2-4 sprints)
**Part chains**: Add `parent_socket_id` to PartData
- Forearm attaches to arm tip socket
- Creates hierarchy: body → arm → forearm → claw
- Scene graph structure instead of flat list

**Auto-joint generation**:
- Detect part chains (2+ parts in sequence)
- 2-bone IK solver: given foot target, compute hip/knee angles
- Removes hardcoded animation, enables real walking

**Skeleton preview**:
- Wireframe bones connecting attached parts
- Shown during sculptor editing for feedback

### Long-term (4+ sprints)
- **Panda3D animation clips**: pre-authored walk/attack/idle animations
- **Creature DNA**: breed two creatures to combine traits
- **Multiplayer arena**: 1v1 creature battles with ranked leaderboard
- **Environment creator**: click-to-place terrain, custom obstacle layouts
- **Physics**: mass/weight system affects speed, knockback, inertia

---

## Save Format (v5)

Auto-migrates from v1-v4. Persists to `saves/my_creature.json`:

```json
{
  "name": "My Morphling",
  "body_size": 0.5,
  "body_sx": 1.0,  // width scale
  "body_sy": 1.0,  // height scale
  "body_sz": 1.0,  // depth scale
  "parts": [
    {
      "type": "arm",
      "px": 0.52, "py": 0.05, "pz": 0,  // normalized position
      "rot_y": 90.0,
      "scale": 1.0,
      "color_idx": -1,  // -1 = inherit body color
      "socket_id": 2    // index into socket grid (-1 = freeform)
    }
  ],
  "spine_crystals": 42,
  "forge_dmg_bonus": 15.0,
  "forge_hp_bonus": 30.0,
  "forge_spd_bonus": 0.4,
  "forge_lucky": true,
  "forge_iron_start": false,
  "difficulty": "hard",
  "wins": 3,
  "kills": 247,
  "best_score": 8450,
  "bonus_budget": 4,
  "version": 5
}
```

---

## Adding Content

### New Part
```python
# in parts.py
@register('claw', 'CLAW', c8(200,80,80), mirror_default=True, mut_key='arms')
def _claw(parent, bc, s, ep, sx, sy, sz):
    pivot = Entity(parent=parent, position=ep)
    pivot._anim_attr = 'rotation_z'
    pivot._anim_amp = 20.0
    pivot._anim_freq = 1.3
    # ... build claw geometry ...
    return [pivot]
```

### New Upgrade
```python
# in upgrades.py
_mk('berserk_plus', 'MIGHTY WRATH', '+80% damage when HP < 50%', 'epic',
    lambda m: setattr(m, '_berserk_threshold', 0.50) or setattr(m, '_berserk_mult', 1.80))
```

### New Ability
```python
# in abilities.py
'laser_burst': AbilityDef(c8(255,0,220), 16, 3.2, 'Fires twin laser pulses')

# in arena.py Morphling.use_ability()
elif ab == 'laser_burst':
    for offset in [-0.3, 0.3]:
        Projectile(self, tgt, 'laser', speed=20, damage=self.effective_damage*0.8, arena=self.arena, ...)
```

---

## Known Limitations & Future Work

- Body collider is always round (socket grid bypasses this, but true deformable mesh is future work)
- No player-controlled movement (creature is fully AI-driven)
- No persistent global leaderboard (only single best-score per creature)
- Upgrade cards can't be selected via 1/2/3 keyboard shortcuts yet (wiring pending)
- No sound effects or music
- Environment obstacles are static (future: interactive environment creator)
- Vision system is full 360° (future: 270° vision cones with alert states)

---

## Performance

- **Tested on**: Windows 11, RTX 3070
- **Typical FPS**: 60+ in sculptor, 30-60+ in arena (scales with enemy count)
- **Memory**: ~200MB typical
- **Save file**: ~5KB per creature

---

## Development & Contribution

The codebase is organized around three main pillars:
1. **Data** (`creature_data.py`, `sockets.py`): how creatures are defined
2. **Creation** (`sculptor.py`, `parts.py`, `render.py`): how they're built
3. **Combat** (`arena.py`, `morphling`, `upgrades.py`): how they fight

Each system is self-contained but tightly coupled via the `CreatureData` model.
Adding new parts, upgrades, or abilities requires changes to just 1-2 files.

---

**Built with Python 3.12 • Ursina (Panda3D) • Inspired by Spore**

https://github.com/Kwoolford/morphlings-arena
