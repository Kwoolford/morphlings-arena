# Morphlings Arena — Development Roadmap

## Completed Features

### Phase 1: Foundation (v1-v4)
- ✅ Creature sculptor with socket grid attachment
- ✅ Wave-based arena combat
- ✅ 35+ tiered upgrades
- ✅ Procedural enemy generation
- ✅ Debug visualization overlays

### Phase 2a: Currency & Economy (v5)
- ✅ Two-tier currency system (Morph Shards + Spine Crystals)
- ✅ In-arena shop with 6 purchasable items
- ✅ Smite ability with ground targeting
- ✅ Difficulty selector (Easy/Normal/Hard/Nightmare)

### Phase 2b: Polish & Socket System (v6)
- ✅ Socket grid visualization (24 attachment points)
- ✅ Socket snapping for guaranteed clean attachment
- ✅ Per-instance animation phase offsets
- ✅ Skeleton preview visualization (bones between parts)
- ✅ Part chains data structure (parent_socket_id field)

---

## Planned Features

### Part Chains & Hierarchical Rendering (Sprint 1-2)

**Status**: Data structure complete. Rendering pending.

**Goal**: Enable part attachment chains: body → arm → forearm → claw

**Implementation**:
1. **Render Changes** (`render.py`):
   - Modify `build_creature()` to respect parent_socket_id
   - For each part, compute world position from parent's output socket
   - Apply parent's rotation when positioning child parts
   - Build scene graph instead of flat part list

2. **Sculptor Changes** (`sculptor.py`):
   - Allow clicking on existing parts to set them as parents
   - Visual indicator showing parent/child relationships
   - Prevent cycles (part can't be parent of its own ancestor)
   - Move/delete cascades through chains

3. **Arena Changes** (`arena.py`):
   - Apply parent rotations when updating animation
   - Cascade movement when parent moves (for future procedural animation)

**Data Model** (already in `creature_data.py` v6):
```python
@dataclass
class PartData:
    # ... existing fields ...
    parent_socket_id: int = -1  # -1 = attached to body; >=0 = attached to parent part's socket
```

---

### 2-Bone IK Solver (Sprint 2-3)

**Status**: Architecture designed. Not yet implemented.

**Goal**: Auto-solve knee/elbow joints when foot/hand target moves

**Algorithm**: Analytical 2-bone IK (FABRIK or law of cosines)
- Input: hip position, foot target, bone lengths
- Output: knee position and angles
- Works for any part chain of length 2 (e.g., thigh+calf)

**Implementation** (`ik_solver.py` — new file):
```python
class IKSolver:
    def solve_2bone(hip_pos: Vec3, target: Vec3, 
                    bone1_len: float, bone2_len: float) -> tuple[Vec3, Vec3]:
        """Solve 2-bone chain given root, target, and bone lengths.
        
        Returns: (knee_pos, foot_pos)
        """
        # Calculate distances and angles using law of cosines
        # Handle unreachable targets by clamping bone2 extension
        # Return joint positions suitable for animation
```

**Integration Points**:
1. `render.py`: Apply IK results when rendering creatures with leg chains
2. `arena.py`: On each frame, compute foot target from animation path
3. `sculptor.py`: Show IK preview in skeleton visualization

**Benefits**:
- No more hardcoded animation constants
- Legs follow terrain/animation path naturally
- Procedural walk cycles generated from IK

---

### Animation Clip Support (Sprint 3-4)

**Status**: Architecture designed. Not yet implemented.

**Goal**: Support Panda3D animation files (.bam) for walk/attack/idle cycles

**Structure** (`animations/` directory):
```
animations/
├── walk_cycle.bam      # 1.2s loop (30 fps)
├── run_cycle.bam       # 0.6s loop (30 fps)
├── attack_swing.bam    # 0.8s one-shot
├── idle_sway.bam       # 2.0s loop
└── death_ragdoll.bam   # 1.5s one-shot
```

**Implementation** (`animation_controller.py` — new file):
```python
class AnimationClip:
    name: str
    duration: float
    loop: bool
    clip: BamFile  # Panda3D animation

class AnimationController:
    def play(clip_name: str, blend_time: float = 0.3):
        """Play animation with optional fade-in."""
    
    def set_speed(speed_mult: float):
        """Real-time speed adjustment for run vs. walk."""
    
    def is_playing(clip_name: str) -> bool:
```

**Integration**:
1. `morphling.py`: Replace sine-wave animation with clip playback
2. Load clips on creature spawn
3. Blend between clips (idle→walk→run→attack) based on state

**Clip Creation Workflow** (external, documented):
1. Model creature in Blender
2. Rig with bone armature
3. Key animation frames
4. Export as .bam file via Panda3D exporter
5. Place in `animations/` directory

---

## Architecture: From Linear to Hierarchical

### Current (v6): Socket Grid
```
Body (center)
├── Arm1 @ socket 5
├── Arm2 @ socket 5 (mirrored)
├── Leg1 @ socket 10
└── Leg2 @ socket 10 (mirrored)
```
Parts are flat list. Animation: simple sine wave per part.

### Phase 3: Part Chains
```
Body (center)
├── Arm1 @ socket 5
│   └── Forearm1 @ arm1's socket 1
│       └── Claw1 @ forearm1's socket 2
├── Leg1 @ socket 10
│   └── Shin1 @ leg1's socket 2
│       └── Foot1 @ shin1's socket 2
```
Parts form tree. Animation: base sine + IK chain solving.

### Phase 4: Animation Clips
```
Body (center)
  [WALK_CYCLE animation]
  ├── Arm1 (motion captured from .bam)
  ├── Leg1 (IK solver follows foot track)
  └── Body (procedural sway)
```
Animations drive motion; IK solves constraints.

---

## Remaining Milestones

| Feature | Effort | Impact | Blocker |
|---------|--------|--------|---------|
| Part chains rendering | 1 sprint | HIGH | None |
| 2-bone IK solver | 1 sprint | HIGH | Part chains |
| Animation clip system | 1 sprint | MEDIUM | Panda3D setup |
| Blend trees (idle→walk→run) | 0.5 sprint | MEDIUM | Anim clips |
| Procedural walk cycle generator | 1 sprint | MEDIUM | IK solver |
| Environmental interaction (terrain following) | 1 sprint | LOW | IK solver |

**Critical Path**: Part chains → IK solver → Animation clips

**Estimated Time to Feature Complete**: 3-4 sprints (6-8 weeks)

---

## Known Limitations & Workarounds

1. **Body shape doesn't affect child positions**: Stretching body_sx/sy/sz won't deform part chains. Workaround: keep body shape normal.
2. **No soft IK/dampening**: Joints snap to solve. Future: add damping for springy motion.
3. **Animation clips require external tools**: Must use Blender + Panda3D exporter. Workaround: provide template .blend file.

---

## Testing Strategy

### Unit Tests (`tests/` directory)
- `test_ik_solver.py`: Verify 2-bone IK for edge cases (unreachable targets, zero length bones)
- `test_part_chains.py`: Verify parent/child positioning and cascade operations

### Integration Tests
- Sculptor: Create multi-part creature, toggle skeleton, verify positions
- Arena: Spawn creature with chains, verify animation applies correctly
- IK: Verify feet follow animation path without penetrating terrain

### Manual Testing
- Create complex creature (quad with tail + horns)
- Toggle skeleton preview, verify bone visualization
- Play arena run, watch IK solve as creature walks
- Load animation clip, verify blending between states

---

## Reference: Part Chain Example

**Creature**: Quadruped with tail

**Data** (`creature_data.py`):
```json
{
  "parts": [
    {"type": "leg", "socket_id": 8,  "parent_socket_id": -1},  // front-left leg on body
    {"type": "leg", "socket_id": 9,  "parent_socket_id": -1},  // front-right leg on body
    {"type": "leg", "socket_id": 20, "parent_socket_id": -1},  // back-left leg on body
    {"type": "leg", "socket_id": 21, "parent_socket_id": -1},  // back-right leg on body
    {"type": "tail", "socket_id": 1, "parent_socket_id": -1},  // tail at back
    {"type": "spike", "socket_id": 3, "parent_socket_id": 1}   // spike on tail (parent=tail)
  ]
}
```

**Rendering**:
```
Leg @ socket 8: position = body_center + socket_offset
Spike @ tail socket 3:
  - parent_leg = part where socket_id=1
  - parent_rotation = tail's current rotation
  - position = parent.position + parent.rotation * offset
```

---

**Last Updated**: 2026-04-28  
**Next Review**: After part chains implementation
