"""
Spore-style creature sculptor: click-to-place body parts on a stationary creature.

Key behaviour:
  - Body is stationary; camera spins around it (drag = yaw only, never pitches)
  - W/S move camera height; scroll zooms; pitch is locked
  - Pick a part type → ghost preview hugs the body surface → click to place
  - Mirror toggle (auto-on for arm/leg/wing/ear) places X-mirrored pairs
  - Click a placed part to select; Scale +/-, recolor, Delete, Move (reposition)
  - Body shape W/H/D axes stretch the body into non-spherical forms
  - Mutation budget enforced at placement time (base + bonus earned from waves)
  - Load-Morph dropdown loads templates from morphs.py
  - Placed arms/legs animate with idle swing in the preview
  - Yellow CoM dot tracks the weighted center of mass of placed parts

Stored part positions are NORMALIZED (body-radius units) — see creature_data.py.
The sculptor multiplies by `cd.bs` to get world placement, so changing body
size moves everything together.

TODO: undo/redo stack (Ctrl+Z / Ctrl+Y)
TODO: free-rotate selected part (R key drag while selected)
TODO: drag placed part around body surface in real-time (hold G like Blender grab)
TODO: asymmetric mirror: independent left/right part after initial placement
TODO: body mesh sculpting — pull vertices on the body sphere to make custom shapes
TODO: part layering / stacking (place a horn on top of a spike)
TODO: save multiple creature slots (not just one save file)
TODO: creature preview animation (walk cycle) mode button
"""
from ursina import (
    Entity, Text, Button, Vec3, mouse, camera, color, time, destroy, held_keys,
    application, clamp,
)
import math

from config import c8, ca, PALETTE
from creature_data import (
    CreatureData, PartData, CREATURE_NAMES, MUTATION_BUDGET,
)
from parts import PART_REGISTRY, make_part, part_types
from render import build_body_base, add_eyes
from morphs import MORPH_KEYS, make as make_morph
from debug import DebugOverlay


# How far (in normalized body-radius units) parts sit from body center.
SURFACE_R = 0.52

# Shape axis steps available via +/- buttons
SHAPE_STEPS = [0.50, 0.65, 0.80, 1.00, 1.20, 1.40, 1.60, 1.80, 2.00]


# ────────────────────────────────────────────────────────────────────────────
# Visual helpers
# ────────────────────────────────────────────────────────────────────────────

def _ghost_color(bc):
    return color.Color(bc[0], bc[1], bc[2], 0.38)


def _create_line(start, end, color_val, thickness=0.03):
    """Create a visual line using a thin stretched box."""
    direction = end - start
    dist = direction.length()
    if dist < 0.001:
        return None
    mid = (start + end) * 0.5
    line = Entity(model='cube', color=color_val,
                  position=mid, scale=Vec3(thickness, thickness, dist))
    line.look_at(end, axis=Vec3.up)
    return line


def _destroy_line(line_ent):
    """Clean up a line entity."""
    if line_ent:
        destroy(line_ent)


# ────────────────────────────────────────────────────────────────────────────
# SculptPart — a placed body part with a click-to-select collider
# ────────────────────────────────────────────────────────────────────────────

class SculptPart(Entity):
    """
    Placed part. The Entity itself is invisible — it's only the click target.
    Visual children are built as sub-entities and inherit its rotation_y.
    """

    def __init__(self, pd: PartData, body_color, body_size, sculptor, sx=1.0, sy=1.0, sz=1.0):
        super().__init__(
            model=None,           # invisible — no more outer box
            scale=body_size * 0.45,
            collider=None,        # toggled by Sculptor.set_place_mode
        )
        self.pd       = pd
        self.sculptor = sculptor
        self.body_size = body_size
        self.sx, self.sy, self.sz = sx, sy, sz
        self._vis     = []
        self._hover_glow = None
        self.position   = Vec3(pd.px * sx, pd.py * sy, pd.pz * sz) * body_size
        self.rotation_y = pd.rot_y
        self._build_visuals(body_color, body_size)

    def _build_visuals(self, body_color, body_size):
        for e in self._vis: destroy(e)
        self._vis = []
        part_bc = (PALETTE[self.pd.color_idx % len(PALETTE)]
                   if self.pd.color_idx >= 0 else body_color)
        self._vis = make_part(self, self.pd.type, part_bc, body_size,
                              scale_mult=self.pd.scale, pos=None, sx=self.sx, sy=self.sy, sz=self.sz)

    def set_hover(self, enabled):
        """Show/hide hover glow effect."""
        if enabled and not self._hover_glow:
            self._hover_glow = Entity(parent=self, model='sphere',
                                     color=ca(255,255,255,60),
                                     scale=self.body_size * 0.52)
        elif not enabled and self._hover_glow:
            destroy(self._hover_glow)
            self._hover_glow = None

    def update_for_size(self, body_color, body_size, sx=1.0, sy=1.0, sz=1.0):
        self.body_size = body_size
        self.sx, self.sy, self.sz = sx, sy, sz
        self.position = Vec3(self.pd.px * sx, self.pd.py * sy, self.pd.pz * sz) * body_size
        self.scale    = body_size * 0.45
        self._build_visuals(body_color, body_size)
        # Rebuild hover glow if it exists
        if self._hover_glow:
            destroy(self._hover_glow)
            self._hover_glow = Entity(parent=self, model='sphere',
                                     color=ca(255,255,255,60),
                                     scale=body_size * 0.52)

    def on_click(self):
        self.sculptor.select_part(self)


# ────────────────────────────────────────────────────────────────────────────
# GhostPart — placement preview that follows the cursor on the body
# ────────────────────────────────────────────────────────────────────────────

class GhostPart(Entity):
    def __init__(self):
        super().__init__(enabled=False)

    def set_type(self, ptype, body_color, body_size):
        for ch in self.children[:]: destroy(ch)
        make_part(self, ptype, _ghost_color(body_color), body_size,
                  scale_mult=1.0, pos=None, sx=1.0, sy=1.0, sz=1.0)

    def snap_to(self, surface_pos, normal):
        self.position   = surface_pos
        self.rotation_y = math.degrees(math.atan2(normal.x, normal.z))


# ────────────────────────────────────────────────────────────────────────────
# Sculptor
# ────────────────────────────────────────────────────────────────────────────

class Sculptor:

    def __init__(self, cd: CreatureData, on_fight):
        self.cd        = cd
        self.on_fight  = on_fight

        self._ents          = []
        self._scene_ents    = []
        self.placed_parts   = []
        self.selected       = None
        self.active_ptype   = None
        self.mirror_on      = False
        self._move_mode     = False   # drag selected part to new surface position

        # Undo stack — each entry is a full state snapshot dict
        self._undo_stack    = []

        # Camera — pitch is LOCKED
        self.cam_yaw   = 20.0
        self.cam_pitch = 12.0
        self.cam_dist  = 7.0
        self.cam_tgt   = Vec3(0, 0.35, 0)

        self._drag_active = False
        self._ldrag_moved = False

        # Animation clock
        self._anim_time = 0.0

        # Debug visualization
        self.debug_overlay = DebugOverlay()

        # Scene refs
        self.body_ent   = None
        self.body_vis   = None
        self.ghost      = None
        self.sel_ring   = None
        self.com_dot    = None

        # UI refs
        self.name_txt     = None
        self.size_txt     = None
        self.mirror_btn   = None
        self.budget_txt   = None
        self.sel_txt      = None
        self.stat_txt     = None
        self.part_btns    = {}
        self.morph_btns   = []
        self._morph_idx   = 0
        self._morph_label = None
        self._shape_labels = {}   # axis -> Text widget showing current value

        self._build_scene()
        self._build_ui()
        self._refresh_body()

    # ── scene ────────────────────────────────────────────────────────────────
    def _build_scene(self):
        floor = Entity(model='plane', scale=7, color=ca(25,25,45,220),
                       position=Vec3(0, -1.1, 0))
        self._scene_ents.append(floor)

        self.body_vis = Entity()
        self._scene_ents.append(self.body_vis)

        self.body_ent = Entity(model='sphere', color=ca(0,0,0,1),
                               scale=self.cd.bs * 2.0, collider='sphere')
        self._scene_ents.append(self.body_ent)

        self.ghost = GhostPart()
        self._scene_ents.append(self.ghost)

        self.sel_ring = Entity(model='sphere', color=ca(255,220,50,70),
                               scale=0.4, enabled=False)
        self._scene_ents.append(self.sel_ring)

        # Use thin boxes instead of line model for visibility
        self.attach_line = None
        self.placement_line = None

        # Center-of-mass indicator — small glowing sphere
        self.com_dot = Entity(model='sphere', color=ca(255,255,80,160),
                              scale=0.10, enabled=False)
        self._scene_ents.append(self.com_dot)

        self._set_place_mode(False)
        self._apply_cam()

    def _apply_cam(self):
        ry = math.radians(self.cam_yaw)
        rp = math.radians(self.cam_pitch)
        cx = self.cam_tgt.x - self.cam_dist * math.cos(rp) * math.sin(ry)
        cy = self.cam_tgt.y + self.cam_dist * math.sin(rp)
        cz = self.cam_tgt.z - self.cam_dist * math.cos(rp) * math.cos(ry)
        camera.position = Vec3(cx, cy, cz)
        camera.rotation_x = self.cam_pitch
        camera.rotation_y = self.cam_yaw
        camera.rotation_z = 0

    def _set_place_mode(self, active):
        if active:
            self.body_ent.collider = 'sphere'
            for sp in self.placed_parts: sp.collider = None
        else:
            self.body_ent.collider = None
            for sp in self.placed_parts: sp.collider = 'sphere'

    # ── UI helpers ───────────────────────────────────────────────────────────
    def _ui(self, cls, *a, **kw):
        kw.setdefault('parent', camera.ui)
        e = cls(*a, **kw); self._ents.append(e); return e

    def _btn(self, label, pos, size, col, action):
        return self._ui(Button, text=label, position=pos, scale=size,
                        color=col, on_click=action)

    def _txt(self, label, pos, sc=0.7, col=color.white, origin=(0,0)):
        return self._ui(Text, label, position=pos, scale=sc, color=col, origin=origin)

    # ── UI layout ────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Background panel — taller to accommodate shape controls
        self._ui(Entity, model='quad', color=ca(8,8,20,225),
                 scale=(0.46, 1.06), position=(0.645, -0.02))

        self._txt('CREATURE SCULPTOR', (0.645, 0.435), sc=0.90, col=c8(255,220,80))

        # Name
        self._txt('Name', (0.430, 0.388), sc=0.58, col=color.gray)
        self._btn('-', (0.515, 0.388), (0.036,0.036), color.dark_gray, lambda: self._cycle_name(-1))
        self.name_txt = self._txt(self.cd.name, (0.645, 0.388), sc=0.60, col=color.white)
        self._btn('+', (0.775, 0.388), (0.036,0.036), color.dark_gray, lambda: self._cycle_name(1))

        # Color
        self._txt('Color', (0.430, 0.344), sc=0.58, col=color.gray)
        for i, pc in enumerate(PALETTE):
            xi = 0.495 + i * 0.029
            self._ui(Button, position=(xi, 0.344), scale=0.023,
                     color=pc, on_click=(lambda idx=i: self._set_body_color(idx)))

        # Body size
        self._txt('Body', (0.430, 0.300), sc=0.58, col=color.gray)
        self._btn('-', (0.515, 0.300), (0.036,0.036), color.dark_gray, lambda: self._cycle_size(-1))
        self.size_txt = self._txt(self.cd.size_label(), (0.645, 0.300), sc=0.60, col=color.white)
        self._btn('+', (0.775, 0.300), (0.036,0.036), color.dark_gray, lambda: self._cycle_size(1))

        # Body shape (X/Y/Z stretch)
        self._txt('Shape', (0.430, 0.254), sc=0.56, col=color.gray)
        for col_i, (axis, label, lc) in enumerate([
            ('body_sx', 'W', c8(255,110,110)),
            ('body_sy', 'H', c8(110,255,110)),
            ('body_sz', 'D', c8(110,160,255)),
        ]):
            bx = 0.510 + col_i * 0.090
            self._txt(label, (bx,      0.254), sc=0.52, col=lc)
            self._btn('-', (bx+0.020, 0.254), (0.026,0.026), color.dark_gray,
                      (lambda a=axis: self._cycle_shape(a, -1)))
            sv = self._txt(f'{getattr(self.cd, axis):.2f}',
                           (bx+0.052, 0.254), sc=0.46, col=color.white)
            self._btn('+', (bx+0.076, 0.254), (0.026,0.026), color.dark_gray,
                      (lambda a=axis: self._cycle_shape(a, 1)))
            self._shape_labels[axis] = sv

        # Morph templates
        self._txt('-'*30, (0.645, 0.218), sc=0.48, col=c8(50,50,70))
        self._txt('LOAD MORPH', (0.555, 0.197), sc=0.50, col=c8(170,170,210))
        self._btn('-', (0.645, 0.197), (0.036, 0.036), color.dark_gray, lambda: self._cycle_morph(-1))
        self._morph_label = self._txt(MORPH_KEYS[0].upper(), (0.712, 0.197), sc=0.52, col=color.white)
        self._btn('+', (0.782, 0.197), (0.036, 0.036), color.dark_gray, lambda: self._cycle_morph(1))
        self._btn('LOAD',  (0.515, 0.162), (0.100, 0.032), c8(60,90,140),   self._load_morph)
        self._btn('CLEAR', (0.625, 0.162), (0.100, 0.032), c8(120,60,20),   self._clear_all)
        self.budget_txt = self._txt('', (0.760, 0.162), sc=0.48, col=color.lime)

        # Parts palette + mirror
        self._txt('-'*30, (0.645, 0.130), sc=0.48, col=c8(50,50,70))
        self._txt('PARTS  (pick, then click body)', (0.555, 0.110),
                  sc=0.48, col=c8(170,170,210))
        self.mirror_btn = self._btn('MIRROR: OFF', (0.785, 0.110), (0.150, 0.032),
                                     c8(60,60,80), self._toggle_mirror)

        ptypes = part_types()
        for idx, ptype in enumerate(ptypes):
            info = PART_REGISTRY[ptype]
            col_i, row_i = idx % 2, idx // 2
            x = 0.530 + col_i * 0.230
            y = 0.072 - row_i * 0.048
            b = self._btn(info['label'], (x, y), (0.175, 0.040), info['color'],
                          (lambda pt=ptype: self._pick_part(pt)))
            self.part_btns[ptype] = b

        # Selected part section
        sep_y = 0.072 - ((len(ptypes)-1)//2) * 0.048 - 0.054
        self._txt('-'*30, (0.645, sep_y),           sc=0.48, col=c8(50,50,70))
        self._txt('SELECTED', (0.645, sep_y-0.026), sc=0.56, col=c8(200,180,255))
        self.sel_txt = self._txt('none', (0.645, sep_y-0.052), sc=0.58, col=color.gray)

        sc_y = sep_y - 0.088
        self._txt('Scale', (0.465, sc_y), sc=0.52, col=color.gray)
        self._btn('-', (0.560, sc_y), (0.034,0.034), c8(160,40,40),  self._scale_down)
        self._btn('+', (0.618, sc_y), (0.034,0.034), c8(40,140,40),  self._scale_up)
        self._btn('MOVE', (0.720, sc_y), (0.100, 0.034), c8(40,80,160), self._enter_move_mode)

        col_y = sc_y - 0.038
        self._txt('Color', (0.465, col_y), sc=0.52, col=color.gray)
        for i, pc in enumerate(PALETTE[:6]):
            xi = 0.535 + i * 0.032
            self._ui(Button, position=(xi, col_y), scale=0.024, color=pc,
                     on_click=(lambda idx=i: self._set_part_color(idx)))
        self._btn('body', (0.760, col_y), (0.065, 0.028), color.dark_gray,
                  lambda: self._set_part_color(-1))

        del_y = col_y - 0.040
        self._btn('DELETE', (0.645, del_y), (0.200, 0.036),
                  c8(180,40,40), self._delete_selected)

        # Stats + bottom buttons
        self._txt('-'*30, (0.645, del_y-0.026), sc=0.48, col=c8(50,50,70))
        self.stat_txt = self._txt('', (0.645, del_y-0.048),
                                   sc=0.48, col=c8(170,210,255))

        self._btn('UNDO',   (0.462, -0.455), (0.100, 0.046), c8(70,70,110),  self._undo)
        self._btn('SAVE',   (0.583, -0.455), (0.110, 0.046), c8(50,120,50),  self._save)
        self._btn('FIGHT!', (0.724, -0.455), (0.140, 0.046), c8(180,60,30),  self.on_fight)

        self._txt('Drag: spin   W/S: height   Scroll: zoom   '
                  'Click body: place   Click part: select   Esc: cancel',
                  (-0.22, -0.47), sc=0.44, col=color.gray)

        self._refresh_stats()
        self._refresh_sel_panel()
        self._refresh_budget()
        self._update_mirror_btn()

    # ── refresh helpers ──────────────────────────────────────────────────────
    def _refresh_stats(self):
        if not self.stat_txt: return
        self.cd._sync_mutation_counts()
        abs_ = ', '.join(self.cd.get_abilities())
        self.stat_txt.text = (
            f'HP {self.cd.max_health:.0f}  SPD {self.cd.speed:.1f}  '
            f'DMG {self.cd.base_damage:.0f}  RNG {self.cd.aggro_range:.0f}\n'
            f'{abs_}'
        )

    def _refresh_sel_panel(self):
        sp = self.selected
        if self.sel_txt:
            self.sel_txt.text  = sp.pd.type.upper() if sp else 'none'
            self.sel_txt.color = color.yellow if sp else color.gray

    def _refresh_budget(self):
        if not self.budget_txt: return
        left  = self.cd.budget_left()
        total = MUTATION_BUDGET + self.cd.bonus_budget
        self.budget_txt.text  = f'BUDGET {left}/{total}'
        self.budget_txt.color = (color.lime if left > 0
                                 else color.orange if left == 0
                                 else color.red)

    def _refresh_body(self):
        for ch in self.body_vis.children[:]: destroy(ch)
        bc = PALETTE[self.cd.color_idx % len(PALETTE)]
        bs = self.cd.bs
        sx = self.cd.body_sx
        sy = self.cd.body_sy
        sz = self.cd.body_sz
        build_body_base(self.body_vis, bc, bs, sx, sy, sz)
        for sp in self.placed_parts:
            sp.update_for_size(bc, bs, sx, sy, sz)
        # Keep body collider as a sphere covering the widest axis
        self.body_ent.scale = bs * max(sx, sy, sz) * 2.0
        self._refresh_stats()
        self._refresh_budget()
        self._update_shape_labels()

    def _update_shape_labels(self):
        for axis, lbl in self._shape_labels.items():
            if lbl:
                lbl.text = f'{getattr(self.cd, axis):.2f}'

    # ── center of mass ───────────────────────────────────────────────────────
    def _compute_com(self):
        if not self.placed_parts:
            return Vec3(0, 0, 0)
        total_w = sum(sp.pd.scale for sp in self.placed_parts)
        if total_w < 0.001:
            return Vec3(0, 0, 0)
        total_p = Vec3(0, 0, 0)
        for sp in self.placed_parts:
            total_p += Vec3(sp.pd.px, sp.pd.py, sp.pd.pz) * sp.pd.scale
        return total_p / total_w * self.cd.bs

    # ── name / color / size / shape ──────────────────────────────────────────
    def _cycle_name(self, d):
        idx = CREATURE_NAMES.index(self.cd.name) if self.cd.name in CREATURE_NAMES else 0
        self.cd.name = CREATURE_NAMES[(idx + d) % len(CREATURE_NAMES)]
        if self.name_txt: self.name_txt.text = self.cd.name

    def _set_body_color(self, idx):
        self._push_undo()
        self.cd.color_idx = idx
        self._refresh_body()

    def _cycle_size(self, d):
        self._push_undo()
        steps = [0.0, 0.25, 0.5, 0.75, 1.0]
        cur = min(steps, key=lambda x: abs(x - self.cd.body_size))
        self.cd.body_size = steps[clamp(steps.index(cur) + d, 0, 4)]
        if self.size_txt: self.size_txt.text = self.cd.size_label()
        self._refresh_body()

    def _cycle_shape(self, axis, d):
        self._push_undo()
        cur = getattr(self.cd, axis)
        idx = min(range(len(SHAPE_STEPS)), key=lambda i: abs(SHAPE_STEPS[i] - cur))
        new_idx = clamp(idx + d, 0, len(SHAPE_STEPS) - 1)
        setattr(self.cd, axis, SHAPE_STEPS[new_idx])
        self._refresh_body()

    # ── mirror toggle ────────────────────────────────────────────────────────
    def _toggle_mirror(self):
        self.mirror_on = not self.mirror_on
        self._update_mirror_btn()

    def _update_mirror_btn(self):
        if self.mirror_btn:
            self.mirror_btn.text  = 'MIRROR: ON' if self.mirror_on else 'MIRROR: OFF'
            self.mirror_btn.color = (c8(60,140,60) if self.mirror_on else c8(60,60,80))

    # ── morphs ───────────────────────────────────────────────────────────────
    def _cycle_morph(self, d):
        self._morph_idx = (self._morph_idx + d) % len(MORPH_KEYS)
        self._morph_label.text = MORPH_KEYS[self._morph_idx].upper()

    def _load_morph(self):
        new_cd = make_morph(MORPH_KEYS[self._morph_idx])
        if not new_cd: return
        self._push_undo()
        new_cd.wins = self.cd.wins
        new_cd.kills = self.cd.kills
        new_cd.best_score = self.cd.best_score
        for sp in self.placed_parts[:]: destroy(sp)
        self.placed_parts.clear()
        self.cd.parts     = list(new_cd.parts)
        self.cd.name      = new_cd.name
        self.cd.color_idx = new_cd.color_idx
        self.cd.body_size = new_cd.body_size
        self.cd.body_sx = new_cd.body_sx
        self.cd.body_sy = new_cd.body_sy
        self.cd.body_sz = new_cd.body_sz
        bc = PALETTE[self.cd.color_idx % len(PALETTE)]
        bs = self.cd.bs
        sx = getattr(self.cd, 'body_sx', 1.0)
        sy = getattr(self.cd, 'body_sy', 1.0)
        sz = getattr(self.cd, 'body_sz', 1.0)
        for pd in self.cd.get_parts():
            sp = SculptPart(pd, bc, bs, self, sx, sy, sz)
            self.placed_parts.append(sp)
            self._scene_ents.append(sp)
        self.cd.parts = [sp.pd for sp in self.placed_parts]
        if self.name_txt: self.name_txt.text = self.cd.name
        if self.size_txt: self.size_txt.text = self.cd.size_label()
        self._deselect()
        self._cancel_pick()
        self._refresh_body()

    # ── part type selection ──────────────────────────────────────────────────
    def _pick_part(self, ptype):
        info = PART_REGISTRY[ptype]
        will_mirror = info['mirror_default'] or self.mirror_on
        if not self.cd.can_afford(ptype, mirrored=will_mirror):
            self._flash('No budget for that part!')
            return
        self.active_ptype = ptype
        self.mirror_on    = info['mirror_default']
        self._update_mirror_btn()
        self._deselect()
        self._exit_move_mode()
        self._set_place_mode(True)
        bc = PALETTE[self.cd.color_idx % len(PALETTE)]
        self.ghost.set_type(ptype, bc, self.cd.bs)
        for pt, btn in self.part_btns.items():
            from config import lighter
            base = PART_REGISTRY[pt]['color']
            btn.color = lighter(base, 0.3) if pt == ptype else base

    def _cancel_pick(self):
        self.active_ptype = None
        self._set_place_mode(False)
        self.ghost.enabled = False
        for pt, btn in self.part_btns.items():
            self.part_btns[pt].color = PART_REGISTRY[pt]['color']

    # ── selection ────────────────────────────────────────────────────────────
    def select_part(self, sp):
        # Turn off hover on previously selected part
        if self.selected:
            self.selected.set_hover(False)
            _destroy_line(self.attach_line)
            self.attach_line = None

        self._cancel_pick()
        self._exit_move_mode()
        self.selected = sp
        if sp:
            # Enable hover glow on selected part
            sp.set_hover(True)
            self.sel_ring.enabled  = True
            self.sel_ring.position = sp.position
            self.sel_ring.scale    = self.cd.bs * 0.60

            # Draw attachment line from body center to part
            body_center = Vec3(0, 0, 0)
            part_pos = sp.position
            self.attach_line = _create_line(body_center, part_pos,
                                           ca(255,200,100,180), thickness=0.04)
            if self.attach_line:
                self._scene_ents.append(self.attach_line)
        else:
            self.sel_ring.enabled = False
            _destroy_line(self.attach_line)
            self.attach_line = None
        self._refresh_sel_panel()

    def _deselect(self):
        self.selected = None
        self.sel_ring.enabled = False
        self._refresh_sel_panel()

    # ── move mode: drag selected part to new surface position ────────────────
    def _enter_move_mode(self):
        if not self.selected:
            self._flash('Select a part first.')
            return
        self._cancel_pick()          # clear any active placement ghost first
        self._move_mode = True
        self._set_place_mode(True)   # body collider on so we can raycast
        self._flash('Click body to reposition part.', col=c8(100,200,255), duration=2.0)

    def _exit_move_mode(self):
        self._move_mode = False
        if not self.active_ptype:
            self._set_place_mode(False)

    # ── placement ────────────────────────────────────────────────────────────
    def try_place_part(self):
        if not self.active_ptype: return
        if mouse.hovered_entity is not self.body_ent: return

        wp = mouse.world_point
        L  = wp.length()
        if L < 0.001: return
        normal      = wp / L
        surface_norm = normal * SURFACE_R
        rot_y       = math.degrees(math.atan2(normal.x, normal.z))

        bc = PALETTE[self.cd.color_idx % len(PALETTE)]
        bs = self.cd.bs

        will_mirror = self.mirror_on
        if not self.cd.can_afford(self.active_ptype, mirrored=will_mirror):
            self._flash('Out of mutation budget!')
            return

        self._push_undo()

        def add_part(px, py, pz, ry):
            pd = PartData(type=self.active_ptype, px=px, py=py, pz=pz,
                          rot_y=ry, scale=1.0, color_idx=-1)
            self.cd.parts.append(pd)
            sx = getattr(self.cd, 'body_sx', 1.0)
            sy = getattr(self.cd, 'body_sy', 1.0)
            sz = getattr(self.cd, 'body_sz', 1.0)
            sp = SculptPart(pd, bc, bs, self, sx, sy, sz)
            self.placed_parts.append(sp)
            self._scene_ents.append(sp)
            return sp

        sp = add_part(surface_norm.x, surface_norm.y, surface_norm.z, rot_y)
        if will_mirror:
            add_part(-surface_norm.x, surface_norm.y, surface_norm.z, -rot_y)

        self.select_part(sp)
        self._refresh_stats()
        self._refresh_budget()

    def _try_move_part(self):
        """Reposition the selected part to the cursor's body surface hit."""
        if not self.selected: return
        if mouse.hovered_entity is not self.body_ent: return

        wp = mouse.world_point
        L  = wp.length()
        if L < 0.001: return
        normal       = wp / L
        surface_norm = normal * SURFACE_R
        rot_y        = math.degrees(math.atan2(normal.x, normal.z))

        self._push_undo()
        sp = self.selected
        sp.pd.px    = surface_norm.x
        sp.pd.py    = surface_norm.y
        sp.pd.pz    = surface_norm.z
        sp.pd.rot_y = rot_y
        sp.position   = Vec3(sp.pd.px, sp.pd.py, sp.pd.pz) * self.cd.bs
        sp.rotation_y = rot_y
        self._exit_move_mode()
        self.select_part(sp)

    # ── selected part adjustments ────────────────────────────────────────────
    def _scale_up(self):
        if not self.selected: return
        self._push_undo()
        bc = PALETTE[self.cd.color_idx % len(PALETTE)]
        new_scale = min(3.0, self.selected.pd.scale + 0.15)
        self.selected.pd.scale = new_scale
        self.selected._build_visuals(bc, self.cd.bs)
        mirror = self._find_mirror(self.selected)
        if mirror:
            mirror.pd.scale = new_scale
            mirror._build_visuals(bc, self.cd.bs)

    def _scale_down(self):
        if not self.selected: return
        self._push_undo()
        bc = PALETTE[self.cd.color_idx % len(PALETTE)]
        new_scale = max(0.15, self.selected.pd.scale - 0.15)
        self.selected.pd.scale = new_scale
        self.selected._build_visuals(bc, self.cd.bs)
        mirror = self._find_mirror(self.selected)
        if mirror:
            mirror.pd.scale = new_scale
            mirror._build_visuals(bc, self.cd.bs)

    def _set_part_color(self, idx):
        if not self.selected: return
        self._push_undo()
        bc = PALETTE[self.cd.color_idx % len(PALETTE)]
        self.selected.pd.color_idx = idx
        self.selected._build_visuals(bc, self.cd.bs)

    def _delete_selected(self):
        if not self.selected: return
        self._push_undo()
        sp = self.selected
        if sp.pd in self.cd.parts:   self.cd.parts.remove(sp.pd)
        if sp in self.placed_parts:  self.placed_parts.remove(sp)
        if sp in self._scene_ents:   self._scene_ents.remove(sp)
        destroy(sp)
        self.select_part(None)
        self._refresh_stats()
        self._refresh_budget()

    def _clear_all(self):
        self._push_undo()
        for sp in self.placed_parts[:]: destroy(sp)
        self.placed_parts.clear()
        self.cd.parts.clear()
        self.select_part(None)
        self._refresh_stats()
        self._refresh_body()

    # ── undo ─────────────────────────────────────────────────────────────────
    def _push_undo(self):
        """Snapshot full creature state onto the undo stack (capped at 30 entries)."""
        snap = {
            'parts':     [pd.to_dict() for pd in self.cd.get_parts()],
            'color_idx': self.cd.color_idx,
            'body_size': self.cd.body_size,
            'body_sx':   self.cd.body_sx,
            'body_sy':   self.cd.body_sy,
            'body_sz':   self.cd.body_sz,
            'name':      self.cd.name,
        }
        self._undo_stack.append(snap)
        if len(self._undo_stack) > 30:
            self._undo_stack.pop(0)

    def _undo(self):
        if not self._undo_stack:
            self._flash('Nothing to undo.', col=color.gray)
            return
        snap = self._undo_stack.pop()
        for sp in self.placed_parts[:]: destroy(sp)
        self.placed_parts.clear()

        self.cd.color_idx = snap['color_idx']
        self.cd.body_size = snap['body_size']
        self.cd.body_sx   = snap['body_sx']
        self.cd.body_sy   = snap['body_sy']
        self.cd.body_sz   = snap['body_sz']
        self.cd.name      = snap['name']
        self.cd.parts     = snap['parts']

        bc = PALETTE[self.cd.color_idx % len(PALETTE)]
        bs = self.cd.bs
        sx = getattr(self.cd, 'body_sx', 1.0)
        sy = getattr(self.cd, 'body_sy', 1.0)
        sz = getattr(self.cd, 'body_sz', 1.0)
        for pd in self.cd.get_parts():
            sp = SculptPart(pd, bc, bs, self, sx, sy, sz)
            self.placed_parts.append(sp)
            self._scene_ents.append(sp)
        self.cd.parts = [sp.pd for sp in self.placed_parts]

        if self.name_txt: self.name_txt.text = self.cd.name
        if self.size_txt: self.size_txt.text = self.cd.size_label()
        self._deselect()
        self._cancel_pick()
        self._refresh_body()
        self._flash('Undone.', col=c8(200,200,255))

    # ── mirror helpers ────────────────────────────────────────────────────────
    def _find_mirror(self, sp):
        """Return the mirror partner of sp (same type, opposite px, same py/pz)."""
        for other in self.placed_parts:
            if other is sp: continue
            if other.pd.type != sp.pd.type: continue
            if (abs(other.pd.px + sp.pd.px) < 0.08 and
                    abs(other.pd.py - sp.pd.py) < 0.08 and
                    abs(other.pd.pz - sp.pd.pz) < 0.08):
                return other
        return None

    # ── save / flash ─────────────────────────────────────────────────────────
    def _save(self):
        self.cd.save()
        self._flash('Saved!', col=color.lime)

    def _flash(self, message, col=color.orange, duration=1.4):
        flash = Text(message, position=(0.555, -0.390), scale=0.80,
                     color=col, origin=(0,0), parent=camera.ui)
        self._ents.append(flash)
        destroy(flash, delay=duration)

    # ── input ────────────────────────────────────────────────────────────────
    def on_input(self, key):
        # Debug overlays (always available)
        if key == 'f1': self.debug_overlay.toggle_hitboxes(); return
        if key == 'f2': self.debug_overlay.toggle_aggro(); return
        if key == 'f3': self.debug_overlay.toggle_attachment(); return
        if key == 'f4': self.debug_overlay.toggle_body_ellipsoid(); return
        if key == 'right mouse down':
            self._drag_active = True
        elif key == 'right mouse up':
            self._drag_active = False
        elif key == 'left mouse down':
            self._ldrag_moved = False
            if not self.active_ptype and not self._move_mode:
                self._drag_active = True
        elif key == 'left mouse up':
            self._drag_active = False
            if not self._ldrag_moved:
                if self._move_mode:
                    self._try_move_part()
                elif self.active_ptype:
                    self.try_place_part()
        elif key == 'escape':
            if self._move_mode:
                self._exit_move_mode()
            elif self.active_ptype or self.selected:
                self._cancel_pick(); self._deselect()
            else:
                application.quit()
        elif key == 'delete' or key == 'backspace':
            self._delete_selected()
        elif key == 'z' and held_keys['control']:
            self._undo()
        elif key == 'scroll up':
            self.cam_dist = max(2.5, self.cam_dist - 0.45); self._apply_cam()
        elif key == 'scroll down':
            self.cam_dist = min(20.0, self.cam_dist + 0.45); self._apply_cam()

    # ── update ───────────────────────────────────────────────────────────────
    def on_update(self):
        self._anim_time += time.dt
        t = self._anim_time

        # Camera drag (yaw only)
        if self._drag_active:
            if abs(mouse.velocity[0]) > 0.0005 or abs(mouse.velocity[1]) > 0.0005:
                self._ldrag_moved = True
            self.cam_yaw += mouse.velocity[0] * 300
            self._apply_cam()

        # Camera height via W/S
        spd = 1.8 * time.dt
        if held_keys['w'] or held_keys['up arrow']:
            self.cam_tgt = Vec3(0, clamp(self.cam_tgt.y + spd, -0.5, 2.8), 0)
            self._apply_cam()
        if held_keys['s'] or held_keys['down arrow']:
            self.cam_tgt = Vec3(0, clamp(self.cam_tgt.y - spd, -0.5, 2.8), 0)
            self._apply_cam()

        # Ghost preview
        if self.active_ptype and mouse.hovered_entity is self.body_ent:
            wp = mouse.world_point
            L = wp.length()
            if L > 0.001:
                normal = wp / L
                surface_pos = normal * (self.cd.bs * SURFACE_R)
                self.ghost.snap_to(surface_pos, normal)
                self.ghost.enabled = True
                # Draw preview line from body center to placement point
                _destroy_line(self.placement_line)
                self.placement_line = _create_line(Vec3(0, 0, 0), surface_pos,
                                                  ca(200,255,100,200), thickness=0.035)
                if self.placement_line:
                    self._scene_ents.append(self.placement_line)
            else:
                self.ghost.enabled = False
                _destroy_line(self.placement_line)
                self.placement_line = None
        else:
            self.ghost.enabled = False
            _destroy_line(self.placement_line)
            self.placement_line = None

        # Selection ring follows selected part
        if self.selected and self.sel_ring.enabled:
            self.sel_ring.position = self.selected.position

        # Limb idle animation — pivots tagged with _anim_attr
        tau = math.pi * 2
        for sp in self.placed_parts:
            for e in sp._vis:
                if hasattr(e, '_anim_attr'):
                    # Left-side parts (px < 0) are pi out of phase → alternating gait
                    phase = math.pi if sp.pd.px < 0 else 0.0
                    val   = e._anim_amp * math.sin(t * e._anim_freq * tau + phase)
                    setattr(e, e._anim_attr, val)

        # Center-of-mass dot
        if self.placed_parts:
            self.com_dot.enabled  = True
            self.com_dot.position = self._compute_com()
        else:
            self.com_dot.enabled = False

        # Update debug visualizations
        self.debug_overlay.update_body_ellipsoid([self.player_morph] if hasattr(self, 'player_morph') else [])
        if self.debug_overlay.show_attachment:
            sx = getattr(self.cd, 'body_sx', 1.0)
            sy = getattr(self.cd, 'body_sy', 1.0)
            sz = getattr(self.cd, 'body_sz', 1.0)
            creatures_data = [(None, self.cd.bs, (sx, sy, sz), self.cd.get_parts())]
            self.debug_overlay.update_attachment(creatures_data)

    # ── cleanup ──────────────────────────────────────────────────────────────
    def destroy_all(self):
        self.debug_overlay.destroy_all()
        for e in self._ents:       destroy(e)
        for e in self._scene_ents: destroy(e)
        self._ents.clear()
        self._scene_ents.clear()
        self.placed_parts.clear()
