"""
Arena combat scene: Morphling (combatant), Projectile, and Arena (orchestrator).

Wave state machine:
    wave_start  → countdown, then spawn enemies
    fighting    → AI runs, player fights
    wave_clear  → brief pause after all enemies die
    upgrade_pick → player chooses 1 of 3 upgrades (game paused)
    intermission → upgrade applied, optional budget banner, waiting for next wave
    game_over   → player dead

Enemy scaling:
    Each wave adds more enemies, bigger bodies, and more randomly-placed parts.
    By wave 10 enemies look grotesque; by wave 20 they are comically over-mutated.

Upgrade system:
    After every wave the player picks from 3 rarity-weighted upgrades.
    Rarer upgrades appear more often as waves increase.
    Every BUDGET_INTERVAL waves, +BUDGET_AMOUNT is added to the creator budget.

TODO: add sound effects (hit, death, wave start, upgrade pick)
TODO: add screen-shake on heavy hits
TODO: add a persistent run-summary screen between waves (show all upgrades held)
TODO: distinguish player-controlled movement from AI (WASD player control)
TODO: add arena hazards / environmental obstacles at higher waves
TODO: visual indicator on player when berserk/overdrive passive is active
"""
from ursina import (
    Entity, Text, Button, Vec3, camera, color, time, destroy, invoke,
    held_keys, lerp, clamp, curve, application, raycast, sequence, Wait,
)
import random, math

from config import c8, ca, ARENA_SIZE, PALETTE
from creature_data import CreatureData
from abilities import ABILITIES, ALL_AB, PART_ABILITY
from render import build_creature, build_body_base, add_eyes, collect_anim_pivots
from waves import (
    wave_enemy_count, generate_enemy_cd, total_budget_bonus,
    BUDGET_INTERVAL, BUDGET_AMOUNT,
)
from upgrades import pick_upgrades, RARITY_RGB
from debug import DebugOverlay
from environment import ArenaEnvironment


def _rr(lo, hi): return lo + random.random() * (hi - lo)
def _rc():       return random.choice(PALETTE)


# ── Wave state constants ─────────────────────────────────────────────────────
_FIGHTING     = 'fighting'
_WAVE_CLEAR   = 'wave_clear'
_UPGRADE_PICK = 'upgrade_pick'
_SHOP         = 'shop'          # in-arena shop between waves
_INTERMISSION = 'intermission'   # upgrade applied; waiting for next-wave invoke
_WAVE_START   = 'wave_start'
_GAME_OVER    = 'game_over'
_SMITE_MODE   = 'smite_targeting'  # player aiming smite ability

_WAVE_CLEAR_DELAY = 1.2   # seconds between last kill and upgrade screen
_WAVE_START_DELAY = 2.8   # seconds of "WAVE N" banner before enemies spawn


# ════════════════════════════════════════════════════════════════════════════
# Projectile
# ════════════════════════════════════════════════════════════════════════════

class Projectile(Entity):
    def __init__(self, owner, target, kind, speed, damage, arena, origin_pos=None):
        if kind == 'spear':       mdl, sz = 'cube',   Vec3(0.07, 0.07, 0.55)
        elif kind == 'laser':     mdl, sz = 'sphere', 0.14
        elif kind == 'fireball':  mdl, sz = 'sphere', 0.28
        else:                     mdl, sz = 'sphere', 0.18

        # Use provided origin position or default to creature center + offset
        if origin_pos is None:
            origin_pos = owner.position + Vec3(0, 0.9, 0)

        super().__init__(model=mdl, color=ABILITIES[kind].color, scale=sz,
                         position=origin_pos)
        self.owner, self.target = owner, target
        self.kind, self.speed, self.damage = kind, speed, damage
        self.life  = 5.0
        self.arena = arena
        arena.projectiles.append(self)

    def update(self):
        if self.arena.paused: return
        if not self.target or not getattr(self.target, 'alive', False):
            self._remove(); return
        self.life -= time.dt
        if self.life <= 0: self._remove(); return
        aim = self.target.position + Vec3(0, 0.6, 0) - self.position
        d = aim.length()
        if d < 0.6:
            if self.kind == 'freeze':
                self.target.frozen_timer = 2.5
            self.target.take_damage(self.damage, attacker=self.owner)
            self._remove(); return
        self.position += aim.normalized() * self.speed * time.dt
        if self.kind == 'spear':
            self.look_at(self.target.position + Vec3(0, 0.6, 0))

    def _remove(self):
        if self in self.arena.projectiles:
            self.arena.projectiles.remove(self)
        destroy(self)


# ════════════════════════════════════════════════════════════════════════════
# Morphling
# ════════════════════════════════════════════════════════════════════════════

class Morphling(Entity):
    """Combat creature. AI-driven enemies and the player share this class.

    Upgrade effect fields (set by upgrades.py apply lambdas):
        _regen_rate   float   HP per second passively restored
        _lifesteal    float   fraction of damage dealt converted to healing
        _berserk      bool    +60% damage when HP < 40%
        _overdrive    bool    damage scales with missing HP (up to 3×)
        _phoenix      bool    one-time death-prevention revive at 50% HP
        _deathbomb    bool    AOE explosion on death

    TODO: add a visible status icon above health bar for active passives
    TODO: _berserk visual (red tint / glow when active)
    TODO: _overdrive visual (damage numbers scale up)
    """

    def __init__(self, arena, position=None, is_player=False, cd: CreatureData = None):
        if position is None:
            position = Vec3(_rr(-ARENA_SIZE+3, ARENA_SIZE-3), 0.5,
                            _rr(-ARENA_SIZE+3, ARENA_SIZE-3))
        super().__init__(position=position)
        self.arena        = arena
        self.is_player    = is_player
        self.cd           = cd
        self.alive        = True
        self.melee_cd     = 0.0
        self.morph_timer  = _rr(5, 10)
        self.wander_timer = _rr(1, 3)
        self.wander_dir   = Vec3(random.uniform(-1,1), 0, random.uniform(-1,1)).normalized()
        self.target       = None
        self.frozen_timer = 0.0
        self.shield_timer = 0.0
        self.winner       = False
        self.vision_cone  = 360.0  # Full vision by default, upgradeable

        # Upgrade effect fields — all start neutral
        self._regen_rate = 0.0
        self._lifesteal  = 0.0
        self._berserk    = False
        self._overdrive  = False
        self._phoenix    = False
        self._deathbomb  = False

        if cd:
            self.max_health    = cd.max_health
            self.speed         = cd.speed
            self.bs            = cd.bs
            self.base_damage   = cd.base_damage
            self.aggro_range   = cd.aggro_range
            self.abilities     = list(cd.get_abilities())
            self.dodge_chance  = cd.dodge_chance
            self.spike_reflect = cd.spike_reflect
        else:
            self.max_health    = _rr(70, 130)
            self.speed         = _rr(2.5, 5.5)
            self.bs            = _rr(0.65, 1.1)
            self.base_damage   = _rr(8, 18)
            self.aggro_range   = _rr(8, 16)
            self.abilities     = random.sample(ALL_AB, random.randint(1, 3))
            self.dodge_chance  = 0.0
            self.spike_reflect = 0.0

        self.health = self.max_health
        self.ab_cd  = {a: 0.0 for a in self.abilities}
        # Part-based ability cooldowns: maps (part_index, ability) → cooldown time
        self.part_ab_cd = {}
        self._build()

    # ── derived stats ──────────────────────────────────────────────────────
    @property
    def damage_mult(self):
        """Multiplicative damage modifier from passive upgrades."""
        mult = 1.0
        if self._berserk and self.health < self.max_health * 0.40:
            mult *= 1.6
        if self._overdrive and self.max_health > 0:
            missing = 1.0 - (self.health / self.max_health)
            mult *= (1.0 + missing * 2.0)
        return mult

    @property
    def effective_damage(self):
        return self.base_damage * self.damage_mult

    # ── visuals ────────────────────────────────────────────────────────────
    def _build(self):
        for ch in self.children[:]: destroy(ch)
        self.hb_bg = self.hb_fill = self.hb_root = None
        self._anim_pivots = []
        self._anim_time   = 0.0
        self.part_ab_cd.clear()
        self.part_wraps = {}  # part_idx → wrap entity (for attack origination)
        if self.cd:
            _, _, self._anim_pivots = build_creature(self, self.cd)
            # Collect part wrap entities for attack origination
            for child in self.children:
                if hasattr(child, '_part_idx'):
                    self.part_wraps[child._part_idx] = child
            # Build part-based ability cooldowns: each part grants an ability
            for part_idx, pd in enumerate(self.cd.get_parts()):
                ab = PART_ABILITY.get(pd.type)
                if ab:
                    self.part_ab_cd[(part_idx, ab)] = 0.0
        else:
            self._random_visual()
        self._make_hbar()
        self._make_ab_icons()
        if self.is_player:
            # Yellow crown marker so the player can always spot their creature
            Entity(parent=self, model='sphere', color=color.yellow,
                   scale=self.bs*0.18, position=Vec3(0, self.bs*1.35, 0))

    def _random_visual(self):
        enemy_cd = generate_enemy_cd(self.arena.wave)
        _, _, self._anim_pivots = build_creature(self, enemy_cd)

    def _make_hbar(self):
        """Health bar: a parented root that holds the bg + fill so they stay aligned.
        The fill anchors at the LEFT edge so it shrinks rightward as health drops."""
        by = self.bs * 1.55 + 0.5
        # Root: positions and billboards together so bg/fill never disconnect
        self.hb_root = Entity(parent=self, position=Vec3(0, by, 0), billboard=True)
        # Single dark background quad (acts as the bar's frame)
        Entity(parent=self.hb_root, model='quad', color=c8(20, 20, 20),
               scale=Vec3(1.55, 0.18, 1), z=0.002)
        # Fill quad — anchored at left edge so scaling shrinks toward the left
        # by adjusting x position relative to its scale
        self._hb_full_w = 1.50
        self.hb_fill = Entity(
            parent=self.hb_root, model='quad',
            color=color.lime if not self.is_player else c8(0, 220, 255),
            scale=Vec3(self._hb_full_w, 0.14, 1),
            position=Vec3(0, 0, 0),
            origin=(-0.5, 0),  # left-anchored so scaling looks correct
        )
        # Re-position the fill so its origin is at the left edge of the background
        self.hb_fill.x = -self._hb_full_w / 2
        self.hb_bg = None  # legacy field

    def _update_hbar(self):
        if not self.hb_fill: return
        r = max(0, self.health / self.max_health)
        self.hb_fill.scale_x = self._hb_full_w * r
        if not self.is_player:
            self.hb_fill.color = (color.lime   if r > 0.6 else
                                  color.orange  if r > 0.3 else color.red)

    def _make_ab_icons(self):
        by = self.bs * 1.55 + 0.76
        self.ab_icons = []
        n = len(self.abilities)
        for i, ab in enumerate(self.abilities):
            self.ab_icons.append(
                Entity(parent=self, model='quad', color=ABILITIES[ab].color,
                       scale=0.19, position=Vec3((i-(n-1)/2)*0.26, by, 0.02),
                       billboard=True))

    def _trigger_part_attack_anim(self, part_wrap, part_type, ability):
        """Trigger attack animation for a specific body part."""
        if not part_wrap.children: return
        pivot = part_wrap.children[0]
        if not hasattr(pivot, '_anim_attr'): return

        # Different animations based on part type
        if part_type in ('arm',):  # Arms swing forward
            old_freq = getattr(pivot, '_anim_freq', 1.3)
            old_amp = getattr(pivot, '_anim_amp', 22.0)
            pivot._anim_freq = old_freq * 3.0
            pivot._anim_amp = old_amp * 2.2
            invoke(lambda: setattr(pivot, '_anim_freq', old_freq), delay=0.25)
            invoke(lambda: setattr(pivot, '_anim_amp', old_amp), delay=0.25)
        elif part_type in ('eye',):  # Eyes glow
            glow = Entity(parent=part_wrap, model='sphere', color=ABILITIES.get(ability, color.white).color,
                          scale=self.bs*0.4, opacity=0.6)
            glow.animate_scale(self.bs*0.15, duration=0.3)
            destroy(glow, delay=0.3)
        elif part_type in ('leg',):  # Legs stomp
            old_freq = getattr(pivot, '_anim_freq', 1.6)
            old_amp = getattr(pivot, '_anim_amp', 18.0)
            pivot._anim_freq = old_freq * 2.5
            pivot._anim_amp = old_amp * 1.5
            invoke(lambda: setattr(pivot, '_anim_freq', old_freq), delay=0.2)
            invoke(lambda: setattr(pivot, '_anim_amp', old_amp), delay=0.2)
        elif part_type in ('horn',):  # Horn flashes
            flash = Entity(parent=part_wrap, model='sphere', color=c8(255,200,100),
                           scale=self.bs*0.3, opacity=0.7)
            flash.animate_scale(self.bs*0.08, duration=0.25)
            destroy(flash, delay=0.25)

    # ── combat ─────────────────────────────────────────────────────────────
    @property
    def melee_range(self): return 2.0

    def use_ability(self, ab, tgt, part_idx=None):
        """Use an ability, optionally from a specific part (part-based system).
        If part_idx is provided, attack originates from that part's position."""
        dmg = self.effective_damage * 1.6
        origin_pos = self.position + Vec3(0, 0.9, 0)  # Default origin

        # For part-based attacks, calculate origin from part position and trigger animation
        part_type = None
        if part_idx is not None and part_idx in self.part_wraps:
            part_wrap = self.part_wraps[part_idx]
            if self.cd and part_idx < len(self.cd.get_parts()):
                part_type = self.cd.get_parts()[part_idx].type
                self._trigger_part_attack_anim(part_wrap, part_type, ab)

                # Calculate origin position based on part type
                if part_type == 'arm':
                    # Spear originates from hand (end of arm)
                    origin_pos = part_wrap.position + Vec3(0, -self.bs*0.56, self.bs*0.09)
                elif part_type == 'eye':
                    # Laser originates from eye
                    origin_pos = part_wrap.position + Vec3(0, 0, 0)

        if ab == 'fireball':
            Projectile(self, tgt, 'fireball', speed=10, damage=dmg, arena=self.arena,
                      origin_pos=origin_pos)
        elif ab == 'spear':
            Projectile(self, tgt, 'spear', speed=22, damage=dmg*1.4, arena=self.arena,
                      origin_pos=origin_pos)
        elif ab == 'laser':
            Projectile(self, tgt, 'laser', speed=25, damage=dmg*0.9, arena=self.arena,
                      origin_pos=origin_pos)
            Projectile(self, tgt, 'laser', speed=25, damage=dmg*0.9, arena=self.arena,
                      origin_pos=origin_pos + Vec3(0.15, 0, 0))
        elif ab == 'snipe':
            Projectile(self, tgt, 'snipe', speed=20, damage=dmg*1.5, arena=self.arena,
                      origin_pos=origin_pos)
        elif ab == 'freeze':
            Projectile(self, tgt, 'freeze', speed=8,  damage=dmg*0.4, arena=self.arena,
                      origin_pos=origin_pos)
        elif ab == 'heal':
            self.health = min(self.max_health, self.health + self.max_health*0.28)
            self._update_hbar()
            pulse = Entity(parent=self, model='sphere', color=color.lime, scale=self.bs*1.8)
            destroy(pulse, delay=0.35)
        elif ab == 'shockwave':
            r = ABILITIES['shockwave'].range
            for m in self.arena.morphlings:
                if m is self or not m.alive: continue
                d = (m.position - self.position).length()
                if d < r:
                    m.take_damage(dmg*(1-d/r), attacker=self)
            ring = Entity(position=self.position+Vec3(0,0.05,0),
                          model='sphere', color=color.yellow, scale=0.3, rotation_x=90)
            ring.animate_scale(r*2.2, duration=0.45, curve=curve.linear)
            destroy(ring, delay=0.45)
        elif ab == 'shield':
            self.shield_timer = 2.8
            aura = Entity(parent=self, model='sphere',
                          color=ca(100,200,255,60), scale=self.bs*1.7)
            destroy(aura, delay=2.8)
        elif ab == 'dash':
            if tgt:
                d = tgt.position - self.position; d.y = 0
                if d.length() > 0.1:
                    self.position += d.normalized() * 5.5
                if (tgt.position - self.position).length() < self.melee_range + 1.5:
                    tgt.take_damage(dmg*1.2, attacker=self)

        # Set cooldown (part-based or global)
        if part_idx is not None:
            self.part_ab_cd[(part_idx, ab)] = ABILITIES[ab].cooldown
        else:
            self.ab_cd[ab] = ABILITIES[ab].cooldown

    def take_damage(self, amount, attacker=None):
        if self.shield_timer > 0:
            amount *= 0.08
        if self.dodge_chance > 0 and random.random() < self.dodge_chance:
            flash = Entity(parent=self, model='sphere', color=color.white, scale=self.bs*1.2)
            destroy(flash, delay=0.18)
            return
        if self.spike_reflect > 0 and attacker and getattr(attacker, 'alive', False):
            attacker.take_damage(amount * self.spike_reflect)
        # Lifesteal: heal the attacker for a fraction of damage dealt
        if attacker and attacker._lifesteal > 0 and getattr(attacker, 'alive', False):
            heal = amount * attacker._lifesteal
            attacker.health = min(attacker.max_health, attacker.health + heal)
            if hasattr(attacker, '_update_hbar'):
                attacker._update_hbar()
        self.health -= amount
        self._update_hbar()
        if self.health <= 0:
            self.die()

    def die(self):
        # Phoenix: one-time death prevention
        if self._phoenix:
            self._phoenix = False
            self.health = self.max_health * 0.50
            self._update_hbar()
            pulse = Entity(parent=self, model='sphere',
                           color=c8(255,140,0), scale=self.bs*2.2)
            destroy(pulse, delay=0.5)
            return

        # Death Bomb: massive AOE on death
        if self._deathbomb:
            boom_r = 9.0
            for m in self.arena.morphlings:
                if m is self or not m.alive: continue
                d = (m.position - self.position).length()
                if d < boom_r:
                    m.take_damage(self.max_health * 0.65 * (1 - d/boom_r))
            ring = Entity(position=self.position, model='sphere',
                          color=c8(255,100,0), scale=0.4, rotation_x=90)
            ring.animate_scale(boom_r*2, duration=0.5, curve=curve.linear)
            destroy(ring, delay=0.5)

        self.alive = False
        if self.is_player:
            self.arena._on_player_death()
        elif self.arena.wave_state == _FIGHTING:
            self.arena.kills += 1
            self.arena.shards += 10
        if self in self.arena.morphlings:
            self.arena.morphlings.remove(self)
        destroy(self)

    def do_morph(self):
        if not self.cd:
            self.bs = _rr(0.65,1.1); self.speed = _rr(2.5,5.5)
            self.base_damage = _rr(8,18); self.aggro_range = _rr(8,16)
        self._build(); self._update_hbar()
        self.morph_timer = _rr(6, 12)

    # ── per-frame ──────────────────────────────────────────────────────────
    def update(self):
        if not self.alive or self.arena.paused: return
        if self.arena.wave_state != _FIGHTING:  return
        dt = time.dt
        self.morph_timer  -= dt
        if self.morph_timer <= 0: self.do_morph()

        # Testing nudge: push creatures toward middle to speed up combat
        dist_from_center = self.position.length()
        if dist_from_center > ARENA_SIZE * 0.6:
            nudge_dir = -self.position.normalized() * self.speed * 0.3 * dt
            self.position += nudge_dir
        self.melee_cd     = max(0, self.melee_cd     - dt)
        self.frozen_timer = max(0, self.frozen_timer - dt)
        self.shield_timer = max(0, self.shield_timer - dt)
        for ab in self.ab_cd:
            self.ab_cd[ab] = max(0, self.ab_cd[ab] - dt)
        # Tick down part-based ability cooldowns
        for key in self.part_ab_cd:
            self.part_ab_cd[key] = max(0, self.part_ab_cd[key] - dt)

        # Passive regeneration
        if self._regen_rate > 0 and self.health < self.max_health:
            self.health = min(self.max_health, self.health + self._regen_rate * dt)
            self._update_hbar()

        spd = self.speed * (0.3 if self.frozen_timer > 0 else 1.0)

        # Acquire nearest living target
        self.target = None
        best = self.aggro_range
        for m in self.arena.morphlings:
            if m is self or not m.alive: continue
            d = (m.position - self.position).length()
            if d < best: best, self.target = d, m

        tgt = self.target if (self.target and self.target.alive) else None
        if tgt:
            try:    dv = tgt.position - self.position
            except: tgt = self.target = None

        if tgt:
            dv.y = 0
            dist = dv.length()

            # Try part-based abilities (each part type has independent cooldown)
            for (part_idx, ab) in sorted(self.part_ab_cd.keys()):
                if self.part_ab_cd[(part_idx, ab)] > 0: continue
                ab_r = ABILITIES[ab].range
                if dist < ab_r and ab in ('fireball','snipe','freeze','spear','laser','dash','shockwave'):
                    self.use_ability(ab, tgt, part_idx=part_idx); break

            # Try legacy global abilities as fallback
            for ab in self.abilities:
                if self.ab_cd[ab] > 0: continue
                ab_r = ABILITIES[ab].range
                if ab == 'heal' and self.health < self.max_health * 0.45:
                    self.use_ability(ab, tgt); break
                elif ab == 'shield' and self.health < self.max_health * 0.35:
                    self.use_ability(ab, tgt); break
                elif ab == 'shockwave' and dist < ab_r:
                    self.use_ability(ab, tgt); break
                elif ab in ('fireball','snipe','freeze','spear','laser','dash') and dist < ab_r:
                    self.use_ability(ab, tgt); break
            if tgt and not tgt.alive:
                tgt = self.target = None

        if tgt:
            has_ranged = any(a in ('fireball','snipe','freeze','spear','laser')
                             for a in self.abilities)
            if has_ranged:
                pref = 7.5
                if dist > pref + 1.5:
                    move_dir = dv.normalized()
                    # Check for obstacles and steer around them
                    avoid = self.arena.environment.get_steer_direction(
                        self.position, tgt.position, self.wander_dir)
                    if avoid.length() > 0.01:
                        move_dir = (move_dir + avoid * 0.3).normalized()
                    self.position += move_dir * spd * dt
                elif dist < pref - 1.5:
                    self.position -= dv.normalized() * spd * 0.6 * dt
                else:
                    strafe = Vec3(-dv.z, 0, dv.x).normalized()
                    self.position += strafe * spd * 0.5 * dt
            else:
                if dist > self.melee_range:
                    move_dir = dv.normalized()
                    # Check for obstacles and steer around them
                    avoid = self.arena.environment.get_steer_direction(
                        self.position, tgt.position, self.wander_dir)
                    if avoid.length() > 0.01:
                        move_dir = (move_dir + avoid * 0.3).normalized()
                    self.position += move_dir * spd * dt
            if dist > 0.1:
                try: self.look_at(Vec3(tgt.x, self.y, tgt.z), axis=Vec3.forward)
                except: pass
            if dist < self.melee_range and self.melee_cd <= 0:
                if tgt.alive:
                    tgt.take_damage(self.effective_damage, attacker=self)
                self.melee_cd = 1.2

        if not tgt:
            self.wander_timer -= dt
            if self.wander_timer <= 0:
                self.wander_dir = Vec3(
                    random.uniform(-1,1), 0, random.uniform(-1,1)).normalized()
                self.wander_timer = _rr(1.5, 4)
            np = self.position + self.wander_dir * spd * 0.5 * dt
            np.x = clamp(np.x, -ARENA_SIZE+1.5, ARENA_SIZE-1.5)
            np.z = clamp(np.z, -ARENA_SIZE+1.5, ARENA_SIZE-1.5)
            self.position = np

        self.y = 0.5 + self.bs * 0.25
        self.x = clamp(self.x, -ARENA_SIZE+1.5, ARENA_SIZE-1.5)
        self.z = clamp(self.z, -ARENA_SIZE+1.5, ARENA_SIZE-1.5)
        if self.winner and self.children:
            self.children[0].color = color.yellow

        # Limb idle / walk animation
        self._anim_time += dt
        t       = self._anim_time
        anim_spd = 1.0 if tgt else 0.45
        tau     = math.pi * 2
        for pivot in self._anim_pivots:
            phase = math.pi if getattr(pivot, '_anim_px', 0) < 0 else 0.0
            phase += getattr(pivot, '_anim_phase', 0.0)
            val   = pivot._anim_amp * anim_spd * math.sin(
                        t * pivot._anim_freq * tau * anim_spd + phase)
            setattr(pivot, pivot._anim_attr, val)


# ════════════════════════════════════════════════════════════════════════════
# Arena (orchestrator)
# ════════════════════════════════════════════════════════════════════════════

class Arena:
    """Manages floor, morphlings, projectiles, HUD, camera, and wave flow."""

    # Spawn points: corners and middle zones for strategic arena placement
    SPAWN_POINTS = [
        Vec3(-ARENA_SIZE+4, 0.5, -ARENA_SIZE+4),  # Bottom-left corner (player)
        Vec3(ARENA_SIZE-4, 0.5, -ARENA_SIZE+4),   # Bottom-right corner
        Vec3(-ARENA_SIZE+4, 0.5, ARENA_SIZE-4),   # Top-left corner
        Vec3(ARENA_SIZE-4, 0.5, ARENA_SIZE-4),    # Top-right corner
        Vec3(0, 0.5, -ARENA_SIZE+4),              # Bottom-center
        Vec3(0, 0.5, ARENA_SIZE-4),               # Top-center
        Vec3(-ARENA_SIZE+4, 0.5, 0),              # Left-center
        Vec3(ARENA_SIZE-4, 0.5, 0),               # Right-center
        Vec3(0, 0.5, 0),                          # Arena center
    ]

    def __init__(self, cd, on_back):
        self.cd          = cd
        self.on_back     = on_back
        self.morphlings  = []
        self.projectiles = []
        self.kills       = 0
        self.elapsed     = 0.0
        self.active      = True
        self.paused      = False
        self.player      = None
        self._spawn_idx  = 0  # Track which spawn point was last used

        # Wave state machine
        self.wave        = 0
        self.wave_state  = _WAVE_START
        self.wave_timer  = 0.0
        self._upgrade_ents = []
        self._shop_ents    = []
        self._wave_banner  = None   # current banner Text (not in _hud_ents)

        # Currency and shop
        self.shards      = 0    # in-run currency, resets each run
        self.smite_charges = 0
        self._smite_mode = False
        self._smite_indicator = None
        self._current_upgrades = []  # Store for keyboard shortcut access

        # Camera
        self.cam_yaw     = 0.0
        self.cam_pitch   = 55.0
        self.cam_dist    = 52.0
        self.cam_tgt     = Vec3(0, 0, 0)
        self.follow_mode = False
        self.follow_ref  = None

        # Entity buckets — destroyed on exit
        self._scene_ents    = []
        self._hud_ents      = []
        self._gameover_ents = []

        # Debug visualization
        self.debug_overlay = DebugOverlay()

        # Environment
        self.environment = ArenaEnvironment()

        self._build_floor()
        self._spawn_player()
        self._build_hud()
        self._apply_cam()
        self._begin_next_wave()

    # ── floor ───────────────────────────────────────────────────────────────
    def _build_floor(self):
        floor = Entity(model='plane', scale=(ARENA_SIZE*2,1,ARENA_SIZE*2),
                       texture='white_cube', color=color.dark_gray)
        self._scene_ents.append(floor)
        # Floor collider for smite targeting
        self.floor_hit = Entity(model='plane', scale=ARENA_SIZE*2,
                                collider='box', visible=False, y=0.02)
        self._scene_ents.append(self.floor_hit)
        self._build_fence()

    def _build_fence(self):
        """Short post-and-rail fence so the camera can see over the boundary."""
        S           = ARENA_SIZE
        post_h      = 1.1
        post_w      = 0.28
        rail_h      = 0.07
        spacing     = 2.8
        post_col    = c8(110, 85,  60)
        rail_col    = c8(135, 105, 75)

        def fence_side(ax, az, bx, bz):
            length = math.hypot(bx - ax, bz - az)
            n_gaps = max(1, round(length / spacing))
            for i in range(n_gaps + 1):
                t = i / n_gaps
                self._scene_ents.append(Entity(
                    model='cube', color=post_col,
                    scale=Vec3(post_w, post_h, post_w),
                    position=Vec3(ax + (bx-ax)*t, post_h*0.5, az + (bz-az)*t)))
            cx, cz = (ax+bx)*0.5, (az+bz)*0.5
            rx = abs(bx-ax) or post_w * 0.5
            rz = abs(bz-az) or post_w * 0.5
            for ry in (post_h*0.28, post_h*0.72):
                self._scene_ents.append(Entity(
                    model='cube', color=rail_col,
                    scale=Vec3(rx, rail_h, rz),
                    position=Vec3(cx, ry, cz)))

        fence_side(-S, -S, -S,  S)
        fence_side( S, -S,  S,  S)
        fence_side(-S, -S,  S, -S)
        fence_side(-S,  S,  S,  S)

    # ── spawn ────────────────────────────────────────────────────────────────
    def _spawn_player(self):
        self.cd._sync_mutation_counts()
        # Spawn player in bottom-left corner
        player_pos = self.SPAWN_POINTS[0]
        self.player = Morphling(self, position=player_pos,
                                is_player=True, cd=self.cd)
        self.morphlings.append(self.player)
        self._spawn_idx = 1  # Start enemy spawning from next point

    # ── wave state machine ───────────────────────────────────────────────────
    def _begin_next_wave(self):
        self.wave      += 1
        self.wave_state = _WAVE_START
        self.wave_timer = _WAVE_START_DELAY
        self._show_wave_banner(f'WAVE  {self.wave}', c8(255,220,60))
        # Generate environment obstacles for this wave
        self.environment.clear()
        self.environment.generate(self.wave, ARENA_SIZE, seed=self.wave)

    def _spawn_wave_enemies(self):
        n = wave_enemy_count(self.wave)
        num_spawn_points = len(self.SPAWN_POINTS) - 1  # Exclude player spawn point
        for i in range(n):
            # Distribute enemies across spawn points, cycling through them
            spawn_idx = (self._spawn_idx + i) % num_spawn_points
            if spawn_idx == 0:
                spawn_idx = 1  # Skip player corner (index 0)
            spawn_pos = self.SPAWN_POINTS[spawn_idx]
            # Add small random offset so enemies don't overlap exactly
            offset = Vec3(random.uniform(-1, 1), 0, random.uniform(-1, 1)) * 0.8
            final_pos = spawn_pos + offset
            self.morphlings.append(Morphling(self, position=final_pos,
                                            cd=generate_enemy_cd(self.wave)))
        self._spawn_idx = (self._spawn_idx + n) % num_spawn_points
        if self._spawn_idx == 0:
            self._spawn_idx = 1
        self.wave_state = _FIGHTING

    def _on_wave_clear(self):
        self.wave_state = _WAVE_CLEAR
        self.wave_timer = _WAVE_CLEAR_DELAY
        self._show_wave_banner(
            f'WAVE  {self.wave}  CLEAR!', c8(100,255,120),
            duration=_WAVE_CLEAR_DELAY)

    def _show_upgrades(self):
        self.wave_state = _UPGRADE_PICK
        self.paused     = True
        self._current_upgrades = pick_upgrades(self.wave, count=3)
        self._build_upgrade_ui(self._current_upgrades)

    def _apply_upgrade(self, upgrade):
        """Apply chosen upgrade, show shop, then continue."""
        self._clear_upgrade_ui()
        self.paused     = True
        self.wave_state = _SHOP

        if self.player and self.player.alive:
            try:
                upgrade.apply(self.player)
            except Exception as exc:
                print(f'[upgrade] apply error ({upgrade.key}): {exc}')
            self.player._update_hbar()

        # Show shop after upgrade
        self._build_shop_ui()

    def _check_wave_clear(self):
        if self.wave_state != _FIGHTING: return
        if not any(not m.is_player and m.alive for m in self.morphlings):
            self._on_wave_clear()

    # ── upgrade card UI ──────────────────────────────────────────────────────
    def _build_upgrade_ui(self, upgrades):
        # TODO: animate cards sliding in from bottom
        # TODO: keyboard shortcuts (1/2/3) to pick cards without clicking
        # TODO: show current upgrade inventory somewhere on screen
        ui = camera.ui

        ov = Entity(model='quad', color=ca(0,0,0,175),
                    scale=(2.0, 1.2), position=(0,0), parent=ui)
        self._upgrade_ents.append(ov)

        hdr = Text(f'WAVE {self.wave} COMPLETE  —  CHOOSE AN UPGRADE',
                   position=(0, 0.32), scale=1.05,
                   color=c8(255,220,60), origin=(0,0), parent=ui)
        self._upgrade_ents.append(hdr)

        card_w, card_h = 0.27, 0.48
        gap = 0.04
        xs  = [-(card_w + gap), 0.0, (card_w + gap)]

        for upg, cx in zip(upgrades, xs):
            r, g, b = RARITY_RGB[upg.rarity]
            rc   = c8(r, g, b)
            dark = c8(max(0,r-80), max(0,g-80), max(0,b-80))
            dim  = c8(max(0,r//2), max(0,g//2), max(0,b//2))

            self._upgrade_ents.append(Entity(
                model='quad', color=dim,
                scale=(card_w+0.012, card_h+0.012),
                position=(cx, -0.02, 0.001), parent=ui))
            self._upgrade_ents.append(Entity(
                model='quad', color=ca(20,20,35,240),
                scale=(card_w, card_h), position=(cx, -0.02), parent=ui))

            self._upgrade_ents.append(Text(
                upg.rarity.upper(),
                position=(cx, 0.188), scale=0.70,
                color=rc, origin=(0,0), parent=ui))
            self._upgrade_ents.append(Text(
                upg.name,
                position=(cx, 0.110), scale=0.90,
                color=color.white, origin=(0,0), parent=ui))
            self._upgrade_ents.append(Entity(
                model='quad', color=dim,
                scale=(card_w*0.88, 0.003),
                position=(cx, 0.070), parent=ui))

            for li, line in enumerate(_wrap(upg.desc, 28)):
                self._upgrade_ents.append(Text(
                    line, position=(cx, 0.030 - li*0.042),
                    scale=0.58, color=c8(200,200,220),
                    origin=(0,0), parent=ui))

            self._upgrade_ents.append(Button(
                text='CHOOSE', position=(cx, -0.190),
                scale=(card_w*0.75, 0.052),
                color=dark, highlight_color=rc,
                on_click=(lambda u=upg: self._apply_upgrade(u)),
                parent=ui))

    def _clear_upgrade_ui(self):
        for e in self._upgrade_ents: destroy(e)
        self._upgrade_ents.clear()

    # ── shop system ──────────────────────────────────────────────────────────
    SHOP_ITEMS = [
        {'key': 'heal', 'name': 'Emergency Heal', 'cost': 25, 'desc': 'Restore 60% max HP instantly'},
        {'key': 'shield', 'name': 'Overclock Shield', 'cost': 35, 'desc': '3-second full damage immunity'},
        {'key': 'speed', 'name': 'Speed Elixir', 'cost': 20, 'desc': '+50% speed for 45 seconds'},
        {'key': 'smite', 'name': 'SMITE CHARGE', 'cost': 60, 'desc': 'Add 1 smite charge ability'},
        {'key': 'banish', 'name': 'Wave Banish', 'cost': 45, 'desc': 'Remove 2 random enemies next wave'},
        {'key': 'refresh', 'name': 'Refresh Upgrades', 'cost': 30, 'desc': 'Re-roll upgrade options next wave'},
    ]

    def _show_shop(self):
        if self.wave_state != _UPGRADE_PICK:
            return
        self.wave_state = _SHOP
        self.paused = True
        self._build_shop_ui()

    def _build_shop_ui(self):
        ui = camera.ui

        ov = Entity(model='quad', color=ca(0,0,0,175),
                    scale=(2.0, 1.2), position=(0,0), parent=ui)
        self._shop_ents.append(ov)

        hdr = Text(f'💎 MORPH SHOP  —  Balance: {self.shards} Shards',
                   position=(0, 0.32), scale=0.95,
                   color=c8(100,200,255), origin=(0,0), parent=ui)
        self._shop_ents.append(hdr)

        card_w, card_h = 0.27, 0.42
        gap = 0.04
        positions = [
            (-(card_w + gap), 0.12),
            (0.0, 0.12),
            (card_w + gap, 0.12),
            (-(card_w + gap), -0.20),
            (0.0, -0.20),
            (card_w + gap, -0.20),
        ]

        for item, (cx, cy) in zip(self.SHOP_ITEMS, positions):
            can_afford = self.shards >= item['cost']

            card_col = c8(60,120,180) if can_afford else c8(60,60,60)
            border_col = c8(120,200,255) if can_afford else c8(80,80,80)
            text_col = color.white if can_afford else c8(150,150,150)
            button_col = c8(40,100,160) if can_afford else c8(50,50,50)

            self._shop_ents.append(Entity(
                model='quad', color=border_col,
                scale=(card_w+0.012, card_h+0.012),
                position=(cx, cy, 0.001), parent=ui))
            self._shop_ents.append(Entity(
                model='quad', color=card_col,
                scale=(card_w, card_h), position=(cx, cy), parent=ui))

            self._shop_ents.append(Text(
                item['name'],
                position=(cx, cy+0.155), scale=0.78,
                color=text_col, origin=(0,0), parent=ui))
            self._shop_ents.append(Entity(
                model='quad', color=border_col,
                scale=(card_w*0.88, 0.003),
                position=(cx, cy+0.105), parent=ui))

            for li, line in enumerate(_wrap(item['desc'], 24)):
                self._shop_ents.append(Text(
                    line, position=(cx, cy+0.060 - li*0.036),
                    scale=0.52, color=c8(180,200,220),
                    origin=(0,0), parent=ui))

            cost_text = f"💎 {item['cost']}"
            self._shop_ents.append(Text(
                cost_text, position=(cx, cy-0.135),
                scale=0.60, color=border_col, origin=(0,0), parent=ui))

            btn = Button(
                text='BUY' if can_afford else 'LOCKED',
                position=(cx, cy-0.175),
                scale=(card_w*0.75, 0.045),
                color=button_col,
                highlight_color=c8(150,220,255) if can_afford else button_col,
                on_click=(lambda i=item: self._apply_shop_item(i)) if can_afford else None,
                parent=ui)
            if not can_afford:
                btn.disabled = True
            self._shop_ents.append(btn)

        close_btn = Button(
            text='CONTINUE', position=(0, -0.41),
            scale=(0.22, 0.055),
            color=c8(100,150,100),
            highlight_color=c8(150,200,150),
            on_click=self._close_shop,
            parent=ui)
        self._shop_ents.append(close_btn)

    def _apply_shop_item(self, item):
        key = item['key']
        if self.shards < item['cost']:
            return

        self.shards -= item['cost']

        if key == 'heal' and self.player:
            self.player.health = min(self.player.max_health,
                                     self.player.health + self.player.max_health * 0.60)
            self.player._update_hbar()
        elif key == 'shield' and self.player:
            self.player.shield_timer = 3.0
            self.player._update_hbar()
        elif key == 'speed' and self.player:
            self.player.speed *= 1.5
            invoke(lambda: setattr(self.player, 'speed', self.player.speed / 1.5), delay=45)
        elif key == 'smite':
            self.smite_charges += 1
        elif key == 'banish':
            enemies = [m for m in self.morphlings if not m.is_player and m.alive]
            to_remove = min(2, len(enemies))
            for _ in range(to_remove):
                victim = random.choice(enemies)
                enemies.remove(victim)
                victim.alive = False
                destroy(victim)
        elif key == 'refresh':
            self._current_upgrades.clear()

        self._rebuild_shop_ui()

    def _rebuild_shop_ui(self):
        self._clear_shop_ui()
        self._build_shop_ui()

    def _close_shop(self):
        self._clear_shop_ui()
        self.paused = False
        self.wave_state = _INTERMISSION

        # Grant extra creator budget every BUDGET_INTERVAL waves
        target_bonus = total_budget_bonus(self.wave)
        if target_bonus > self.cd.bonus_budget:
            gained = target_bonus - self.cd.bonus_budget
            self.cd.bonus_budget = target_bonus
            self.cd.save()
            self._show_wave_banner(
                f'+{gained} CREATOR BUDGET  (total +{target_bonus})',
                c8(255,180,50), duration=3.0)
            invoke(self._begin_next_wave, delay=3.2)
        else:
            self._begin_next_wave()

    def _clear_shop_ui(self):
        for e in self._shop_ents: destroy(e)
        self._shop_ents.clear()

    # ── smite ability ────────────────────────────────────────────────────────
    def _enter_smite_mode(self):
        if self.smite_charges <= 0 or self.wave_state != _FIGHTING:
            return
        if self._smite_mode:
            return
        self._smite_mode = True
        self._show_smite_indicator()

    def _show_smite_indicator(self):
        if self._smite_indicator:
            destroy(self._smite_indicator)
        self._smite_indicator = Entity(
            model='circle', color=ca(255, 200, 0, 140),
            scale=1.0, y=0.01, visible=False)

    def _update_smite_indicator(self):
        if not self._smite_mode or not self._smite_indicator:
            return
        hit_info = raycast(camera.position, camera.forward(), distance=500)
        if hit_info.hit:
            self._smite_indicator.position = hit_info.world_point
            self._smite_indicator.visible = True
        else:
            self._smite_indicator.visible = False

    def _fire_smite(self, target_pos):
        if self.smite_charges <= 0:
            return
        self.smite_charges -= 1
        self._smite_mode = False
        if self._smite_indicator:
            destroy(self._smite_indicator)
            self._smite_indicator = None

        # Sword entity
        sword = Entity(model='cube', color=c8(255, 220, 60),
                       scale=Vec3(0.4, 5.0, 0.4),
                       position=target_pos + Vec3(0, 22, 0))
        self._scene_ents.append(sword)

        # Animate sword falling
        from ursina import sequence, Wait
        def on_land():
            destroy(sword)
            self._deal_smite_damage(target_pos)
            self._create_smite_ring(target_pos)

        sequence(
            Wait(0.1),
            sword.animate_position(target_pos + Vec3(0, 0.5, 0), duration=0.35, curve=curve.out_cubic),
            invoke(on_land)
        )

    def _deal_smite_damage(self, center):
        for m in self.morphlings[:]:
            if not m.alive:
                continue
            dist = (m.position - center).length()
            if dist < 5.0:
                damage = 250
            elif dist < 9.0:
                damage = 100
            else:
                continue
            m.take_damage(damage, attacker=self.player)

    def _create_smite_ring(self, center):
        ring = Entity(model='circle', color=ca(255, 200, 0, 180),
                      scale=0.1, y=0.02, position=center)
        self._scene_ents.append(ring)
        from ursina import sequence, Wait
        sequence(
            ring.animate_scale(6.0, duration=0.4, curve=curve.out_cubic),
            invoke(lambda: destroy(ring) if ring in self._scene_ents else None)
        )

    def _cancel_smite(self):
        self._smite_mode = False
        if self._smite_indicator:
            destroy(self._smite_indicator)
            self._smite_indicator = None

    # ── wave banner ──────────────────────────────────────────────────────────
    def _show_wave_banner(self, msg, col, duration=2.0):
        """Show a transient centred banner. Managed separately from _hud_ents."""
        if self._wave_banner:
            destroy(self._wave_banner)
            self._wave_banner = None
        banner = Text(msg, position=(0, 0.10), scale=2.0,
                      color=col, origin=(0,0), parent=camera.ui)
        self._wave_banner = banner

        def _clear(b=banner):
            # Only clear if it's still the same banner we scheduled
            if self._wave_banner is b:
                destroy(b)
                self._wave_banner = None
        invoke(_clear, delay=duration)

    # ── HUD ─────────────────────────────────────────────────────────────────
    def _build_hud(self):
        self.wave_txt   = Text('', position=(-0.85, 0.47), scale=0.82, color=c8(255,220,80))
        self.count_text = Text('', position=(-0.85, 0.42), scale=0.72, color=color.white)
        self.score_txt  = Text('', position=(-0.85, 0.37), scale=0.68, color=c8(200,255,200))
        self.kills_txt  = Text('', position=(-0.85, 0.32), scale=0.64, color=c8(180,255,180))
        self.budget_txt = Text('', position=(-0.85, 0.27), scale=0.60, color=c8(255,180,50))
        self.shards_txt = Text('', position=(0.65, -0.45), scale=0.56, color=c8(100,200,255))
        self.hud_hint   = Text(
            'WASD:Pan  Q/E:Orbit  Z/X:Tilt  Scroll:Zoom  '
            'F:Follow  P:Pause  C:Creator  R:Reset  B:Shop  M:Smite',
            position=(-0.85,-0.47), scale=0.48, color=color.white)
        self._hud_ents += [self.wave_txt, self.count_text, self.score_txt,
                           self.kills_txt, self.budget_txt, self.shards_txt, self.hud_hint]

    # ── cleanup ──────────────────────────────────────────────────────────────
    def destroy_all(self):
        self.debug_overlay.destroy_all()
        self.environment.destroy_all()
        for m in self.morphlings[:]:  destroy(m)
        for p in self.projectiles[:]: destroy(p)
        for e in self._scene_ents:    destroy(e)
        for e in self._hud_ents:      destroy(e)
        for e in self._gameover_ents: destroy(e)
        self._clear_upgrade_ui()
        self._clear_shop_ui()
        self._cancel_smite()
        if self._wave_banner:
            destroy(self._wave_banner)
            self._wave_banner = None
        self.morphlings.clear()
        self.projectiles.clear()

    # ── camera ──────────────────────────────────────────────────────────────
    def _apply_cam(self):
        ry = math.radians(self.cam_yaw)
        rp = math.radians(self.cam_pitch)
        camera.x = self.cam_tgt.x - self.cam_dist * math.cos(rp) * math.sin(ry)
        camera.y = self.cam_tgt.y + self.cam_dist * math.sin(rp)
        camera.z = self.cam_tgt.z - self.cam_dist * math.cos(rp) * math.cos(ry)
        camera.rotation_x = self.cam_pitch
        camera.rotation_y = self.cam_yaw
        camera.rotation_z = 0

    # ── death callbacks ──────────────────────────────────────────────────────
    def _on_player_death(self):
        self.active     = False
        self.wave_state = _GAME_OVER
        self._clear_upgrade_ui()
        self.paused     = False
        invoke(self._show_gameover, delay=0.6)

    def _clear_gameover(self):
        for e in self._gameover_ents: destroy(e)
        self._gameover_ents.clear()

    def _show_gameover(self, victory=False):
        self._clear_gameover()
        score = self.kills * 10 + int(self.elapsed // 5) + self.wave * 25
        panel = Entity(model='quad', color=ca(0,0,0,200),
                       scale=(0.75,0.62), position=(0,0), parent=camera.ui)
        self._gameover_ents.append(panel)
        title = '** VICTORIOUS! **' if victory else 'DEFEATED'
        self._gameover_ents.append(Text(
            title, position=(0,-0.04), scale=2.2,
            color=color.gold if victory else color.red,
            origin=(0,0), parent=camera.ui))
        self._gameover_ents.append(Text(
            f'Reached Wave {self.wave}   Kills: {self.kills}   Time: {int(self.elapsed)}s',
            position=(0,-0.09), scale=0.80, color=color.white,
            origin=(0,0), parent=camera.ui))
        self._gameover_ents.append(Text(
            f'Score: {score}',
            position=(0,-0.13), scale=0.90, color=c8(255,220,80),
            origin=(0,0), parent=camera.ui))

        best = self.cd.best_score
        if score > best:
            self.cd.best_score = score
            self.cd.save()
            self._gameover_ents.append(Text(
                f'NEW BEST: {score}!', position=(0,-0.17),
                scale=0.88, color=color.yellow, origin=(0,0), parent=camera.ui))
        else:
            self._gameover_ents.append(Text(
                f'Best: {best}', position=(0,-0.17),
                scale=0.80, color=color.gray, origin=(0,0), parent=camera.ui))

        def _retry():
            self._clear_gameover()
            self._reset_arena()

        self._gameover_ents.append(Button(
            text='Try Again', position=(-0.10,-0.21),
            scale=(0.16,0.055), color=color.azure,
            on_click=_retry, parent=camera.ui))
        self._gameover_ents.append(Button(
            text='Back to Creator', position=(0.10,-0.21),
            scale=(0.18,0.055), color=color.orange,
            on_click=self.on_back, parent=camera.ui))

    def _reset_arena(self):
        for m in self.morphlings[:]: destroy(m)
        for p in self.projectiles[:]: destroy(p)
        self._clear_upgrade_ui()
        self._clear_shop_ui()
        self._cancel_smite()
        if self._wave_banner:
            destroy(self._wave_banner)
            self._wave_banner = None
        self.morphlings.clear()
        self.projectiles.clear()
        self.kills      = 0
        self.elapsed    = 0.0
        self.active     = True
        self.wave       = 0
        self.wave_state = _WAVE_START
        self.wave_timer = 0.0
        self.paused     = False
        self.shards     = 0
        self.smite_charges = 0
        self._spawn_player()
        self._begin_next_wave()

    # ── input / update ──────────────────────────────────────────────────────
    def on_input(self, key):
        # Debug overlays (always available)
        if key == 'f1': self.debug_overlay.toggle_hitboxes(); return
        if key == 'f2': self.debug_overlay.toggle_aggro(); return
        if key == 'f3': self.debug_overlay.toggle_attachment(); return
        if key == 'f4': self.debug_overlay.toggle_body_ellipsoid(); return
        # ESC always quits or cancels smite
        if key == 'escape':
            if self._smite_mode:
                self._cancel_smite()
                return
            application.quit()
            return
        # Smite targeting mode
        if self._smite_mode:
            if key == 'left mouse up':
                hit_info = raycast(camera.position, camera.forward(), distance=500)
                if hit_info.hit:
                    self._fire_smite(hit_info.world_point)
            return
        # All other inputs blocked while upgrade cards are visible
        if self.wave_state == _UPGRADE_PICK:
            return
        if key == 'm':   self._enter_smite_mode()
        elif key == 'b': self._show_shop()
        elif key == 'r': self._reset_arena()
        elif key == 'p': self.paused = not self.paused
        elif key == 'c': self.on_back()
        elif key == 'f':
            self.follow_mode = not self.follow_mode
            if not self.follow_mode: self._apply_cam()
        elif key == 'scroll up':
            self.cam_dist = max(15, self.cam_dist - 3)
            if not self.follow_mode: self._apply_cam()
        elif key == 'scroll down':
            self.cam_dist = min(90, self.cam_dist + 3)
            if not self.follow_mode: self._apply_cam()

    def on_update(self):
        if self.active and not self.paused:
            self.elapsed += time.dt

        # Wave state machine
        if not self.paused:
            if self.wave_state == _WAVE_START:
                self.wave_timer -= time.dt
                if self.wave_timer <= 0:
                    self._spawn_wave_enemies()
            elif self.wave_state == _WAVE_CLEAR:
                self.wave_timer -= time.dt
                if self.wave_timer <= 0:
                    self._show_upgrades()
            elif self.wave_state == _FIGHTING:
                self._check_wave_clear()

        # HUD labels
        enemies = [m for m in self.morphlings if not m.is_player and m.alive]
        state_label = {
            _WAVE_START:   '  [INCOMING…]',
            _WAVE_CLEAR:   '  [WAVE CLEAR]',
            _UPGRADE_PICK: '  [PICK UPGRADE]',
            _SHOP:         '  [SHOP]',
            _INTERMISSION: '',
            _FIGHTING:     '',
            _GAME_OVER:    '',
        }.get(self.wave_state, '')
        self.wave_txt.text   = f'WAVE  {self.wave}{state_label}'
        self.count_text.text = f'Enemies: {len(enemies)}' + ('  [PAUSED]' if self.paused else '')
        self.score_txt.text  = (f'Score: {self.kills*10+int(self.elapsed//5)+self.wave*25}'
                                 f'  (Best: {self.cd.best_score})')
        self.kills_txt.text  = f'Kills: {self.kills}   Survived: {int(self.elapsed)}s'
        bonus = self.cd.bonus_budget
        nxt   = BUDGET_INTERVAL - (self.wave % BUDGET_INTERVAL) if self.wave % BUDGET_INTERVAL else BUDGET_INTERVAL
        self.budget_txt.text = (f'Creator Bonus: +{bonus} pt'
                                f'  (next +{BUDGET_AMOUNT} in {nxt} wave{"s" if nxt!=1 else ""})')
        self.shards_txt.text = f'💎 {self.shards} Shards' + (f'  | Smite: {self.smite_charges}' if self.smite_charges > 0 else '')

        # Update smite indicator if targeting
        if self._smite_mode:
            self._update_smite_indicator()

        if self.paused: return

        # Update debug visualizations
        self.debug_overlay.update_hitboxes(self.morphlings)
        self.debug_overlay.update_aggro(self.morphlings)
        # For attachment view, prepare creature data tuples
        if self.debug_overlay.show_attachment and self.player:
            creatures_data = []
            for m in self.morphlings:
                if hasattr(m, 'cd'):
                    sx = getattr(m.cd, 'body_sx', 1.0)
                    sy = getattr(m.cd, 'body_sy', 1.0)
                    sz = getattr(m.cd, 'body_sz', 1.0)
                    creatures_data.append((m, m.cd.bs, (sx, sy, sz), m.cd.get_parts()))
            self.debug_overlay.update_attachment(creatures_data)
        self.debug_overlay.update_body_ellipsoid(self.morphlings)

        # Camera pan / orbit
        dt      = time.dt
        pan_spd = self.cam_dist * 0.55
        ry      = math.radians(self.cam_yaw)
        fwd     = Vec3( math.sin(ry), 0,  math.cos(ry))   # toward camera look target
        right   = Vec3( math.cos(ry), 0, -math.sin(ry))   # camera's local right
        if held_keys['w'] or held_keys['up arrow']:    self.cam_tgt += fwd   * pan_spd * dt
        if held_keys['s'] or held_keys['down arrow']:  self.cam_tgt -= fwd   * pan_spd * dt
        if held_keys['a'] or held_keys['left arrow']:  self.cam_tgt -= right * pan_spd * dt
        if held_keys['d'] or held_keys['right arrow']: self.cam_tgt += right * pan_spd * dt
        self.cam_tgt.x = clamp(self.cam_tgt.x, -ARENA_SIZE, ARENA_SIZE)
        self.cam_tgt.z = clamp(self.cam_tgt.z, -ARENA_SIZE, ARENA_SIZE)
        if held_keys['q']: self.cam_yaw   -= 55*dt
        if held_keys['e']: self.cam_yaw   += 55*dt
        if held_keys['z']: self.cam_pitch  = min(88, self.cam_pitch+45*dt)
        if held_keys['x']: self.cam_pitch  = max(5,  self.cam_pitch-45*dt)

        if self.follow_mode:
            alive = [m for m in self.morphlings if m.alive]
            if alive:
                if self.follow_ref not in alive: self.follow_ref = alive[0]
                self.cam_tgt = lerp(self.cam_tgt, self.follow_ref.position, dt*6)
            else:
                self.follow_mode = False

        self._apply_cam()


# ── helpers ──────────────────────────────────────────────────────────────────

def _wrap(text: str, width: int) -> list:
    """Naive word-wrap: split text into lines of at most `width` characters."""
    words = text.split()
    lines, cur = [], ''
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + ' ' + w).strip()
    if cur:
        lines.append(cur)
    return lines
