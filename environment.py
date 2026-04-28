"""Arena environment generation — obstacles and terrain."""
from ursina import Entity, Vec3, color, destroy
import random
import math


class ArenaEnvironment:
    """Generates and manages arena obstacles for dynamic gameplay."""

    def __init__(self):
        self.obstacles = []  # List of (position, radius) tuples for AI queries
        self.entities = []   # Visual entity references for cleanup

    def generate(self, wave, arena_size, seed=None):
        """Generate obstacles based on wave number. Higher waves = more/bigger obstacles."""
        self.clear()
        if seed is not None:
            random.seed(seed)

        # Scale obstacle count and size with wave difficulty
        if wave <= 5:
            # Early waves: few small rocks
            count = random.randint(4, 8)
            sizes = [(0.6, color.gray) for _ in range(count)]
        elif wave <= 15:
            # Mid waves: more rocks and some pillars
            rock_count = random.randint(8, 15)
            pillar_count = random.randint(2, 4)
            sizes = [(0.6, color.gray) for _ in range(rock_count)]
            sizes += [(0.4, color.color(0.5, 0.5, 0.6)) for _ in range(pillar_count)]
            count = len(sizes)
        else:
            # Late waves: many obstacles including crystals
            rock_count = random.randint(10, 20)
            pillar_count = random.randint(4, 8)
            crystal_count = random.randint(2, 4)
            sizes = [(0.6, color.gray) for _ in range(rock_count)]
            sizes += [(0.4, color.color(0.5, 0.5, 0.6)) for _ in range(pillar_count)]
            sizes += [(0.5, color.color(0.7, 0.7, 0.3)) for _ in range(crystal_count)]
            count = len(sizes)

        # Place obstacles avoiding player spawn area and arena center
        placed = 0
        attempts = 0
        max_attempts = count * 5
        while placed < count and attempts < max_attempts:
            x = random.uniform(-arena_size + 5, arena_size - 5)
            z = random.uniform(-arena_size + 5, arena_size - 5)
            # Avoid center area (player spawn and combat zone)
            if abs(x) < 8 or abs(z) < 8:
                attempts += 1
                continue
            # Check overlap with existing obstacles
            pos = Vec3(x, 0, z)
            radius, color_val = sizes[placed]
            overlaps = False
            for obs_pos, obs_radius in self.obstacles:
                dist = (pos - obs_pos).length()
                if dist < (radius + obs_radius) * 1.5:  # Safety margin
                    overlaps = True
                    break
            if not overlaps:
                self._place_obstacle(pos, radius, color_val)
                self.obstacles.append((pos, radius))
                placed += 1
            attempts += 1

    def _place_obstacle(self, position, radius, obs_color):
        """Create a visual obstacle entity."""
        # Use a combination of cubes and spheres for varied shapes
        if random.random() < 0.6:
            # Rock: sphere
            ent = Entity(model='sphere', color=obs_color, scale=radius * 2,
                        position=position, collider=None)
        else:
            # Pillar: tall cube
            ent = Entity(model='cube', color=obs_color, scale=Vec3(radius, radius * 2, radius),
                        position=position, collider=None)
        self.entities.append(ent)

    def get_obstacles(self):
        """Return list of obstacle (position, radius) tuples for AI queries."""
        return self.obstacles[:]

    def is_path_blocked(self, start, end, min_clearance=2.0):
        """Check if a straight-line path is blocked by obstacles."""
        direction = end - start
        dist = direction.length()
        if dist < 0.001:
            return False
        direction = direction / dist

        for obs_pos, obs_radius in self.obstacles:
            # Calculate closest point on path segment to obstacle center
            to_obstacle = obs_pos - start
            proj_dist = max(0, min(dist, to_obstacle.dot(direction)))
            closest_point = start + direction * proj_dist
            # Check if obstacle blocks path
            gap = (obs_pos - closest_point).length() - obs_radius
            if gap < min_clearance:
                return True
        return False

    def get_steer_direction(self, position, target, current_heading):
        """Get a steering nudge to avoid obstacles in the path to target."""
        if self.is_path_blocked(position, target):
            # Steer perpendicular to current heading
            right = Vec3(-current_heading.z, 0, current_heading.x)
            if random.random() < 0.5:
                return right
            else:
                return -right
        return Vec3(0, 0, 0)

    def clear(self):
        """Remove all obstacles."""
        for ent in self.entities:
            destroy(ent)
        self.entities = []
        self.obstacles = []

    def destroy_all(self):
        """Cleanup."""
        self.clear()
