"""Debug visualization system for hitboxes, aggro ranges, and part attachment points."""
from ursina import Entity, Vec3, color, destroy, time, camera
import math


class DebugOverlay:
    """Manages togglable debug visualizations for the game."""

    def __init__(self):
        self.show_hitboxes = False
        self.show_aggro = False
        self.show_attachment = False
        self.show_body_ellipsoid = False

        self.hitbox_ents = []
        self.aggro_ents = []
        self.attachment_ents = []
        self.ellipsoid_ents = []

    def toggle_hitboxes(self):
        """Show/hide hitbox visualization (collision spheres around creatures)."""
        self.show_hitboxes = not self.show_hitboxes
        if not self.show_hitboxes:
            self.clear_hitboxes()

    def toggle_aggro(self):
        """Show/hide aggro range visualization (rings around creatures)."""
        self.show_aggro = not self.show_aggro
        if not self.show_aggro:
            self.clear_aggro()

    def toggle_attachment(self):
        """Show/hide part attachment visualization (cubes and lines)."""
        self.show_attachment = not self.show_attachment
        if not self.show_attachment:
            self.clear_attachment()

    def toggle_body_ellipsoid(self):
        """Show/hide body shape ellipsoid wireframe."""
        self.show_body_ellipsoid = not self.show_body_ellipsoid
        if not self.show_body_ellipsoid:
            self.clear_ellipsoid()

    def clear_hitboxes(self):
        """Destroy all hitbox entities."""
        for e in self.hitbox_ents:
            destroy(e)
        self.hitbox_ents = []

    def clear_aggro(self):
        """Destroy all aggro range entities."""
        for e in self.aggro_ents:
            destroy(e)
        self.aggro_ents = []

    def clear_attachment(self):
        """Destroy all attachment visualization entities."""
        for e in self.attachment_ents:
            destroy(e)
        self.attachment_ents = []

    def clear_ellipsoid(self):
        """Destroy all ellipsoid wireframe entities."""
        for e in self.ellipsoid_ents:
            destroy(e)
        self.ellipsoid_ents = []

    def destroy_all(self):
        """Clean up all debug visualizations."""
        self.clear_hitboxes()
        self.clear_aggro()
        self.clear_attachment()
        self.clear_ellipsoid()

    def update_hitboxes(self, morphlings):
        """Update hitbox visualization for all morphlings."""
        if not self.show_hitboxes:
            return
        self.clear_hitboxes()
        for m in morphlings:
            if hasattr(m, 'melee_range'):
                ring = self._make_ring_wireframe(m.position, m.melee_range, color.red)
                if ring:
                    self.hitbox_ents.extend(ring)

    def update_aggro(self, morphlings):
        """Update aggro range visualization for all morphlings."""
        if not self.show_aggro:
            return
        self.clear_aggro()
        for m in morphlings:
            if hasattr(m, 'aggro_range') and m.alive:
                is_in_combat = m.target is not None
                ring_color = color.red if is_in_combat else color.gray
                ring = self._make_ring_wireframe(m.position, m.aggro_range, ring_color)
                if ring:
                    self.aggro_ents.extend(ring)
                # Also draw vision cone if creature has vision_cone attribute
                if hasattr(m, 'vision_cone') and m.vision_cone < 360:
                    cone = self._make_vision_cone(m, ring_color)
                    if cone:
                        self.aggro_ents.extend(cone)

    def update_attachment(self, creatures_with_parts):
        """Update part attachment visualization. Expects list of (creature, body_size, body_sx/sy/sz, parts) tuples."""
        if not self.show_attachment:
            return
        self.clear_attachment()
        for creature_data in creatures_with_parts:
            if len(creature_data) < 4:
                continue
            creature, bs, body_scales, parts = creature_data[0], creature_data[1], creature_data[2], creature_data[3]
            sx, sy, sz = body_scales if len(body_scales) == 3 else (1.0, 1.0, 1.0)
            for pd in parts:
                # Part attachment point in normalized coordinates, scaled by body shape
                attach_pos = Vec3(pd.px * sx, pd.py * sy, pd.pz * sz) * bs
                world_pos = creature.position + attach_pos
                # Draw a small cube at the attachment point
                cube = Entity(model='cube', color=color.yellow, scale=0.1,
                            position=world_pos, lifetime=0.016)
                self.attachment_ents.append(cube)
                # Draw a line from creature center to attachment
                line = self._make_line(creature.position, world_pos, color.cyan, thickness=0.02)
                if line:
                    self.attachment_ents.append(line)

    def update_body_ellipsoid(self, morphlings):
        """Update body ellipsoid wireframe visualization."""
        if not self.show_body_ellipsoid:
            return
        self.clear_ellipsoid()
        for m in morphlings:
            if hasattr(m, 'cd'):
                bs = m.cd.bs
                sx = getattr(m.cd, 'body_sx', 1.0)
                sy = getattr(m.cd, 'body_sy', 1.0)
                sz = getattr(m.cd, 'body_sz', 1.0)
                wireframe = self._make_ellipsoid_wireframe(m.position, bs, sx, sy, sz, color.magenta)
                self.ellipsoid_ents.extend(wireframe)

    def _make_ring_wireframe(self, center, radius, ring_color, segments=16):
        """Create a ring of line segments at the given radius."""
        if radius <= 0:
            return []
        ents = []
        for i in range(segments):
            angle1 = (i / segments) * math.pi * 2
            angle2 = ((i + 1) / segments) * math.pi * 2
            p1 = center + Vec3(math.cos(angle1) * radius, 0, math.sin(angle1) * radius)
            p2 = center + Vec3(math.cos(angle2) * radius, 0, math.sin(angle2) * radius)
            line = self._make_line(p1, p2, ring_color, thickness=0.02)
            if line:
                ents.append(line)
        return ents

    def _make_vision_cone(self, creature, cone_color, segments=8):
        """Create a pie-slice visualization of the creature's vision cone."""
        if not hasattr(creature, 'vision_cone') or creature.vision_cone >= 360:
            return []
        ents = []
        vision_range = getattr(creature, 'aggro_range', 12.0)
        half_cone = creature.vision_cone / 2.0
        # Get creature's facing direction (assume +Z is forward)
        facing = Vec3(0, 0, 1)  # Default facing
        for i in range(segments):
            angle1 = math.radians(-half_cone + (i / segments) * creature.vision_cone)
            angle2 = math.radians(-half_cone + ((i + 1) / segments) * creature.vision_cone)
            # Rotate around Y axis
            p1 = creature.position + Vec3(
                math.sin(angle1) * vision_range,
                0,
                math.cos(angle1) * vision_range
            )
            p2 = creature.position + Vec3(
                math.sin(angle2) * vision_range,
                0,
                math.cos(angle2) * vision_range
            )
            line = self._make_line(p1, p2, cone_color, thickness=0.015)
            if line:
                ents.append(line)
            # Radial lines
            line2 = self._make_line(creature.position, p1, cone_color, thickness=0.010)
            if line2:
                ents.append(line2)
        return ents

    def _make_ellipsoid_wireframe(self, center, bs, sx, sy, sz, wf_color, segments=12):
        """Create a wireframe ellipsoid."""
        ents = []
        # XZ plane rings at different Y values
        for y_ratio in (-0.5, 0.0, 0.5):
            y_pos = center.y + y_ratio * bs * sy
            for i in range(segments):
                angle1 = (i / segments) * math.pi * 2
                angle2 = ((i + 1) / segments) * math.pi * 2
                p1 = center + Vec3(
                    math.cos(angle1) * bs * sx * 0.5,
                    y_ratio * bs * sy * 0.5,
                    math.sin(angle1) * bs * sz * 0.5
                )
                p2 = center + Vec3(
                    math.cos(angle2) * bs * sx * 0.5,
                    y_ratio * bs * sy * 0.5,
                    math.sin(angle2) * bs * sz * 0.5
                )
                line = self._make_line(p1, p2, wf_color, thickness=0.015)
                if line:
                    ents.append(line)
        return ents

    def _make_line(self, start, end, line_color, thickness=0.03):
        """Create a visual line using a thin stretched box."""
        direction = end - start
        dist = direction.length()
        if dist < 0.001:
            return None
        mid = (start + end) * 0.5
        line = Entity(model='cube', color=line_color,
                    position=mid, scale=Vec3(thickness, thickness, dist),
                    lifetime=0.016)
        line.look_at(end, axis=Vec3.up)
        return line
