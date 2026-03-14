# Panda3D ARPG Prototype — Build Plan

## Overview

A RuneScape-inspired Python game built in Panda3D. Stick figure player, slot-based inventory and bank, resource gathering, skill progression, and an NPC vendor. No external assets — everything is built procedurally in code.

---

## Tech Stack

- **Python 3.11+**
- **Panda3D** — rendering, input, GUI, tasks
- **Panda3D Bullet** — physics, gravity, collision (bundled with Panda3D)
- **No external assets** — all geometry is procedural

---

## File Structure

```
project/
├── main.py           # Entry point, ShowBase, physics world, game loop
├── player.py         # Stick figure geometry, BulletCharacterController, WASD movement
├── camera.py         # Third-person orbit camera, mouse look
├── world.py          # Ground plane, static scenery, collision geometry
├── resources.py      # Tree, Rock, FishingSpot node classes with harvest logic
├── inventory.py      # Inventory class, item registry, skill/XP data
├── hud.py            # All DirectGUI — inventory grid, skill bars, prompts
├── bank.py           # Bank building, proximity trigger, bank UI
├── vendor.py         # NPC vendor, shop stock, buy/sell UI
└── data/
    └── save.json     # Persisted bank contents
```

---

## Item Registry

Defined once in `inventory.py`, referenced everywhere else.

```python
ITEMS = {
    "wood": {"name": "Logs",     "stackable": True, "color": (0.4, 0.2, 0.1, 1), "value": 5},
    "ore":  {"name": "Ore",      "stackable": True, "color": (0.5, 0.5, 0.5, 1), "value": 8},
    "fish": {"name": "Raw Fish", "stackable": True, "color": (0.2, 0.5, 0.8, 1), "value": 6},
    "gold": {"name": "Gold",     "stackable": True, "color": (1.0, 0.8, 0.0, 1), "value": 1},
}
```

---

## Inventory System

### Data Model

```python
class Inventory:
    def __init__(self, size=28):
        self.slots = [None] * size  # None or {"id": str, "quantity": int}
```

### Key Methods

| Method | Description |
|---|---|
| `add_item(item_id, qty)` | Stack if stackable, else fill first free slot. Returns False if full. |
| `remove_item(item_id, qty)` | Decrement quantity, clear slot if 0. |
| `move_slot(a, b)` | Swap contents of two slots. |
| `get_free_slots()` | Count of None slots. |
| `to_dict()` / `from_dict()` | Serialization for save.json. |

### Sizes

- **Player inventory** — 28 slots (4 wide × 7 tall)
- **Bank** — 80 slots (8 wide × 10 tall)

---

## Phase 1 — Foundation

**Files:** `main.py`, `world.py`, `player.py`

**Goals:**
- Panda3D window running with a Bullet physics world and gravity set
- Flat ground plane with a Bullet collision shape
- Stick figure player built from `LineSegs` (head, body, arms, legs)
- `BulletCharacterControllerNode` attached for gravity and slope handling
- WASD moves the player, Space jumps
- Player does not fall through the floor

**Stick Figure Construction (`player.py`):**
- Head: `LineSegs` drawing a circle loop at the top
- Body: vertical line down from head
- Arms: two diagonal lines from mid-body
- Legs: two lines from bottom of body
- All `LineSegs` nodes attached to a single parent `NodePath`
- `BulletCapsuleShape` wrapping the whole figure for collision

**Acceptance Test:** Player spawns, walks around, jumps, does not clip through ground.

---

## Phase 2 — Third Person Camera

**File:** `camera.py`

**Goals:**
- Mouse cursor hidden and locked to center of window
- Mouse X delta → rotate camera horizontally around player
- Mouse Y delta → pitch camera up/down (clamped to avoid flip)
- Camera positioned behind and above the player, follows their position each frame
- WASD movement direction is relative to camera facing

**Implementation Notes:**
- Create a pivot `NodePath` that sits at the player's position
- Parent the camera to the pivot at an offset (e.g. `(0, -15, 5)`)
- Each frame: update pivot position to player pos, apply mouse deltas to pivot H/P
- Pass camera heading to player movement so forward = camera forward

**Acceptance Test:** Mouse rotates view smoothly, WASD always moves relative to where you're looking.

---

## Phase 3 — World & Resource Nodes

**File:** `world.py`, `resources.py`

**Goals:**
- Simple flat world with a few raised platforms or walls for variety
- Three resource node types placed in the world
- Player can walk up, see a prompt, hold E to harvest, receive item in inventory

**Resource Node Types:**

| Node | Visual | Skill | Item | Harvest Time |
|---|---|---|---|---|
| Tree | Green cylinder + sphere top | Woodcutting | wood | 2.5s |
| Rock | Grey scaled cube cluster | Mining | ore | 3.5s |
| Fishing Spot | Animated blue plane | Fishing | fish | 4.0s |

**Each Resource Node Has:**
- A `BulletGhostNode` sphere for proximity detection (radius ~3 units)
- State machine: `IDLE → HARVESTING → DEPLETED → RESPAWNING → IDLE`
- Harvest timer counts up while E is held; awards item + XP on completion
- Respawn timer (10–30s) before node resets to IDLE
- Visual change when depleted (grey out or hide geometry)

**Acceptance Test:** Walk to tree, prompt appears, hold E, receive logs, tree goes grey, respawns after delay.

---

## Phase 4 — Inventory, Skills & HUD

**File:** `inventory.py`, `hud.py`

**Goals:**
- Slot-based inventory visible on screen, updates when items are received
- Three skills track XP and display level + progress bar
- Inventory full message when no free slots

**HUD Layout:**
- **Bottom-right** — inventory grid (4×7, 28 slots), toggle with `I`
- **Bottom-left** — skill panel showing Woodcutting / Mining / Fishing level and XP bar, toggle with `K`
- **Top-center** — contextual prompt text ("Press E to chop tree", "Inventory full", etc.)

**Skill XP Formula:**
```python
XP_PER_LEVEL = 100
level = int(skill_xp / XP_PER_LEVEL) + 1
xp_into_level = skill_xp % XP_PER_LEVEL
```

**Slot Rendering (per slot in DirectGUI):**
- `DirectButton` as the slot background (dark grey)
- Colored `DirectFrame` inside representing the item (uses item color from registry)
- `OnscreenText` in bottom-right corner for quantity if > 1
- Hover: show item name in a tooltip frame

**Acceptance Test:** Harvest items, watch inventory fill slot by slot, XP bars increase, level up message appears.

---

## Phase 5 — Bank

**File:** `bank.py`

**Goals:**
- A building in the world (simple box geometry with a sign label)
- Walking up shows "Press E to open Bank"
- Bank UI opens as a centered overlay panel
- Deposit and withdraw items between inventory and bank

**Bank UI Layout:**
- Large centered `DirectFrame` panel
- Two sections side by side:
  - **Left** — Bank slots (8×10 grid)
  - **Right** — Inventory slots (4×7 grid, mirrored from HUD)
- Click an inventory slot → deposits to first free bank slot
- Click a bank slot → withdraws to first free inventory slot
- Close with E or a close button
- Bank contents saved to `data/save.json` on every deposit/withdraw

**Acceptance Test:** Walk to bank, open UI, deposit logs, close, reopen — logs still there. Relaunch game — logs persist.

---

## Phase 6 — NPC Vendor

**File:** `vendor.py`

**Goals:**
- NPC in the world as a colored capsule with a floating name label
- Walking up shows "Press E to talk to Vendor"
- Vendor UI opens with Buy and Sell tabs
- Currency is `gold` (already in item registry)

**Shop Stock (buy prices):**

| Item | Buy Price |
|---|---|
| Logs | 8 gold |
| Ore | 12 gold |
| Raw Fish | 10 gold |

**Sell prices** = `value` field from item registry (always lower than buy).

**Vendor UI Layout:**
- Centered `DirectFrame` panel
- Tab buttons at top: **Buy** / **Sell**
- Buy tab: list of items with name, icon, price, quantity selector (1/5/10/all), Buy button
- Sell tab: player's carried items with sell price shown, Sell button per slot
- Gold count displayed at top of panel

**Acceptance Test:** Sell fish to vendor, gold increases. Buy ore with gold, ore appears in inventory, gold decreases.

---

## Build Order for Claude Code

Work through these in sequence. Each step is independently testable before moving on.

```
Step 1   main.py + world.py          Physics world, ground plane, camera placeholder
Step 2   player.py                   Stick figure + character controller + WASD + jump
Step 3   camera.py                   Third person mouse look, movement relative to camera
Step 4   resources.py (one node)     Just the Tree first — proximity, harvest, item drop
Step 5   inventory.py                Inventory class, item registry, add/remove logic
Step 6   hud.py (inventory only)     Render the 28-slot grid, update on item add
Step 7   hud.py (skills)             Add skill panel and XP bars
Step 8   resources.py (all nodes)    Add Rock and Fishing Spot
Step 9   bank.py                     Bank building, UI, deposit/withdraw, save/load
Step 10  vendor.py                   NPC, shop UI, buy/sell, gold currency
```

---

## Key Panda3D APIs to Use

| Feature | API |
|---|---|
| Physics world | `BulletWorld` with `setGravity` |
| Player controller | `BulletCharacterControllerNode` |
| Collision shapes | `BulletCapsuleShape`, `BulletPlaneShape`, `BulletBoxShape` |
| Proximity detection | `BulletGhostNode` |
| Procedural geometry | `LineSegs`, `GeomVertexData`, `CardMaker` |
| GUI elements | `DirectFrame`, `DirectButton`, `OnscreenText` |
| Mouse control | `base.disableMouse()`, `base.mouseWatcherNode.getMouse()` |
| Frame delta time | `globalClock.getDt()` |
| Input | `self.accept("e", ...)`, key maps |
| Tasks (game loop) | `self.taskMgr.add(fn, "name")` |

---

## Notes & Constraints

- Keep each file under ~200 lines where possible — prefer clarity over cleverness
- No external assets — all geometry is procedural code
- Bullet physics handles gravity and collision throughout — do not fake it manually
- The `Inventory` class is identical for player and bank — only the size differs
- All UI is toggled, never blocking — the game runs while UI is open
- `save.json` only persists bank contents — inventory resets on launch (intentional for prototype)
