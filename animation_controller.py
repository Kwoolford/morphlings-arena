"""
Animation Controller: manages animation clips, blending, and playback.

Supports:
  - Loading Panda3D animation clips (.bam files)
  - Blending between clips (idle → walk → run)
  - Speed adjustment (walk speed vs run speed)
  - State machine for animation selection

Current Status: Skeleton. Animation clips not yet integrated.
To use: Create .bam files in animations/ directory and load them here.
"""
import math
from enum import Enum
from ursina import time, Vec3


class AnimationState(Enum):
    """Creature animation states."""
    IDLE = 'idle'       # Standing still
    WALK = 'walk'       # Moving slowly
    RUN = 'run'         # Moving fast
    ATTACK = 'attack'   # Melee or ranged attack
    HURT = 'hurt'       # Taking damage
    DEATH = 'death'     # Dying animation
    CUSTOM = 'custom'   # Custom animation


class AnimationClip:
    """Represents a single animation clip."""

    def __init__(self, name: str, duration: float, loop: bool = True, bam_data=None):
        """
        Initialize animation clip.

        Args:
            name: Unique identifier (e.g., 'walk_cycle')
            duration: Length in seconds
            loop: Whether clip repeats
            bam_data: Panda3D animation data (None for placeholder)
        """
        self.name = name
        self.duration = duration
        self.loop = loop
        self.bam_data = bam_data
        self.playback_time = 0.0

    def update(self, dt: float) -> None:
        """Update playback position."""
        self.playback_time += dt

        if self.loop and self.playback_time > self.duration:
            self.playback_time = self.playback_time % self.duration
        elif not self.loop and self.playback_time > self.duration:
            self.playback_time = self.duration

    def reset(self) -> None:
        """Reset playback to start."""
        self.playback_time = 0.0

    def progress(self) -> float:
        """Return 0-1 progress through clip."""
        if self.duration < 0.001:
            return 0.0
        return min(1.0, self.playback_time / self.duration)


class AnimationController:
    """Controls animation playback and blending."""

    # Built-in animations (pre-v7, before .bam support)
    BUILT_IN_ANIMATIONS = {
        'idle': AnimationClip('idle', 2.0, loop=True),
        'walk': AnimationClip('walk', 0.8, loop=True),
        'run': AnimationClip('run', 0.5, loop=True),
    }

    def __init__(self, morphling):
        """
        Initialize animation controller.

        Args:
            morphling: The Morphling instance to control animations for
        """
        self.morphling = morphling
        self.clips = dict(self.BUILT_IN_ANIMATIONS)
        self.current_state = AnimationState.IDLE
        self.current_clip = self.clips.get('idle')
        self.next_clip = None
        self.blend_time = 0.0
        self.blend_duration = 0.3  # seconds
        self.speed_multiplier = 1.0
        self.is_blending = False

    def load_clip(self, name: str, clip: AnimationClip) -> None:
        """Register an animation clip."""
        self.clips[name] = clip

    def set_state(self, state: AnimationState, blend_time: float = 0.3) -> None:
        """
        Transition to a new animation state.

        Args:
            state: Target animation state
            blend_time: Duration of crossfade in seconds
        """
        if state == self.current_state and self.current_clip:
            return  # Already in this state

        # Map state to clip name
        clip_name = state.value
        clip = self.clips.get(clip_name)

        if clip is None:
            return  # Clip doesn't exist

        if self.current_clip is None:
            self.current_clip = clip
            self.current_state = state
        else:
            self.next_clip = clip
            self.blend_duration = blend_time
            self.blend_time = 0.0
            self.is_blending = True

        self.current_state = state

    def play_custom(self, clip_name: str, blend_time: float = 0.3) -> None:
        """Play a custom animation clip by name."""
        clip = self.clips.get(clip_name)
        if clip is None:
            return

        if self.current_clip is None:
            self.current_clip = clip
        else:
            self.next_clip = clip
            self.blend_duration = blend_time
            self.blend_time = 0.0
            self.is_blending = True

    def set_speed(self, speed_multiplier: float) -> None:
        """
        Adjust animation playback speed.

        Args:
            speed_multiplier: 1.0 = normal, 2.0 = double speed, 0.5 = half speed
        """
        self.speed_multiplier = max(0.1, speed_multiplier)

    def update(self, dt: float) -> None:
        """Update animation playback."""
        if self.current_clip is None:
            return

        # Update current clip
        self.current_clip.update(dt * self.speed_multiplier)

        # Handle blending
        if self.is_blending and self.next_clip:
            self.blend_time += dt

            if self.blend_time >= self.blend_duration:
                # Blending complete
                self.current_clip = self.next_clip
                self.next_clip = None
                self.is_blending = False
                self.current_clip.reset()
            else:
                # Blending in progress — update both clips
                blend_factor = self.blend_time / self.blend_duration
                self.next_clip.update(dt * self.speed_multiplier)
                # TODO: Blend animations per-joint
                # current_bones = extract_bones(self.current_clip.bam_data, self.current_clip.progress())
                # next_bones = extract_bones(self.next_clip.bam_data, self.next_clip.progress())
                # apply_bones(self.morphling, lerp_bones(current_bones, next_bones, blend_factor))

    def is_playing(self, state_or_name: 'AnimationState | str') -> bool:
        """Check if specific animation is currently active."""
        if isinstance(state_or_name, AnimationState):
            return self.current_state == state_or_name
        else:
            return self.current_clip and self.current_clip.name == state_or_name

    def stop(self) -> None:
        """Stop all animations."""
        if self.current_clip:
            self.current_clip.reset()
        self.next_clip = None
        self.is_blending = False
        self.current_state = AnimationState.IDLE

    # TODO: Add these methods once animation clips are integrated
    # def apply_clip_to_morphling(self) -> None:
    #     """Apply current clip's bone positions to morphling."""
    #     if not self.current_clip or not self.current_clip.bam_data:
    #         return
    #     # Extract bone transforms from .bam file at current progress
    #     # Apply to each part's rotation

    # def procedural_walk_cycle(self, forward_speed: float) -> None:
    #     """Generate procedural walk cycle using IK."""
    #     # For quad creatures:
    #     # - Compute foot target positions based on gait phase
    #     # - Solve IK for each leg
    #     # - Animate body bob and sway


def lerp_bones(bones_a: dict, bones_b: dict, t: float) -> dict:
    """
    Linearly interpolate between two bone pose dictionaries.

    Args:
        bones_a: Dict of bone_name → (position, rotation)
        bones_b: Dict of bone_name → (position, rotation)
        t: Blend factor 0-1

    Returns:
        Interpolated bone dict
    """
    result = {}

    for bone_name in bones_a:
        if bone_name not in bones_b:
            result[bone_name] = bones_a[bone_name]
            continue

        pos_a, rot_a = bones_a[bone_name]
        pos_b, rot_b = bones_b[bone_name]

        # Linear interpolation of position
        pos = pos_a + (pos_b - pos_a) * t

        # SLERP rotation (quaternion interpolation) — simplified as LERP for now
        rot = rot_a + (rot_b - rot_a) * t

        result[bone_name] = (pos, rot)

    return result
