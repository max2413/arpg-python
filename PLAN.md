# Panda3D ARPG Prototype — Current Dev Plan

## Purpose

This document replaces the original phase-by-phase bootstrap plan.

The project is no longer at the "build the prototype from scratch" stage. The codebase now has a playable loop with movement, gathering, inventory, bank/vendor UI, hostile mobs, target selection, basic abilities, death/respawn, loot, and procedural world generation.

Use this file as:

- a current-state snapshot for developers joining the project
- a map of the major systems and how they interact
- a backlog guide for the next rounds of work
- a record of practical constraints and known rough edges

---

## Current State

### Implemented

- Panda3D app bootstraps through `main.py`
- Bullet world with gravity and character controller
- Large procedural overworld with:
  - forests
  - ore patches
  - meandering rivers
  - fishing spots
  - hostile mob placement
- Procedural resource nodes:
  - trees
  - rocks
  - fishing spots
- Resource harvesting with depletion and respawn
- Inventory with stacking items and skill XP
- Toggleable HUD inventory and skills panels
- Bank building with banker NPC and persistent bank storage
- Vendor NPC with buy/sell UI
- Procedural hostile mobs:
  - `Scout` melee enemy
  - `Spitter` ranged enemy
- Hostile patrol, aggro, leash, death, loot, and respawn
- Player health, natural regen, death, and respawn
- Click targeting for hostiles
- Two targeted abilities:
  - `1` melee
  - `2` ranged projectile
- Target HUD with target health and debug target arrow
- Camera with follow behavior and right-click free look

### Partially Implemented / Rough

- Movement and camera feel are still being tuned
- Combat is functional but still prototype-grade
- No formal questing, equipment, stats, or spell system
- No save/load for player inventory, skills, or world state
- No authored world regions, only procedural scatter
- Hostile AI is intentionally simple
- UI layout is functional but not yet cohesive

### Not Yet Implemented

- Equipment / gear / character sheet
- Multi-ability combat system with cooldown UI
- Threat tables, cast times, buffs, debuffs
- Enemy faction logic or spawn families
- Audio
- FX polish
- Save/load beyond bank contents
- Robust test coverage

---

## Current File Map

```text
main.py        Runtime entrypoint and system wiring
player.py      Player controller, health/regen, targeted projectile logic
camera.py      Follow camera, snap-behind behavior, right-click free look
world.py       Ground plane, boundary walls, static scenery collision
worldgen.py    Procedural resources, rivers/decals, hostile spawning/culling
resources.py   Resource nodes and shared procedural geometry helpers
inventory.py   Item registry, inventory logic, skill XP model
hud.py         Main HUD, health bars, target frame, debug range indicators
follower.py    Hostile AI, loot, respawn, melee/ranged enemy behavior
npc.py         Shared helpers for non-hostile NPCs and labels
bank.py        Bank building, banker NPC, persistent bank UI
vendor.py      Vendor NPC and shop UI
test_movement.py  Experimental / local movement test script
data/save.json Bank persistence only
```

---

## Runtime Architecture

### Main Loop

`main.py` owns the high-level runtime:

- creates `ShowBase`
- configures `BulletWorld`
- instantiates `World`, `Player`, `CameraController`, `HUD`, `Bank`, `Vendor`
- calls `generate_world()` to create resources and hostiles
- routes input
- advances physics and per-frame updates

Update order is currently:

1. Bullet physics
2. Player
3. Camera
4. Resources
5. Bank and vendor prompts
6. Hostiles
7. Player projectiles
8. HUD refresh and death/respawn handling

This ordering matters. If combat or prompt behavior starts feeling inconsistent, check `main.py` first before assuming a bug inside the individual actor.

### Shared Geometry Strategy

The project avoids external art assets. Most visuals are built from:

- `LineSegs`
- handmade `GeomVertexData` meshes
- `CardMaker`
- simple `NodePath` composition

Box and sphere helpers currently live in `resources.py` and are reused by multiple modules. This works, but it is not a clean long-term ownership boundary. A future refactor should likely move pure geometry helpers into a dedicated module.

### Prompt Ownership

The prompt line in `hud.py` is shared across the whole game. Multiple systems can write to it:

- resources
- bank
- vendor
- hostile interactions
- player death
- targeting feedback

Because it is single-owner UI with many writers, prompt stomping is possible. `clear_prompt_if()` helps, but there is still no formal priority system.

---

## Controls

Current intended controls:

- `W` move forward
- `S` move backward
- `A` turn left
- `D` turn right
- `Shift` sprint
- `Space` jump
- `Mouse1` target hostile
- `1` use melee ability on target
- `2` use ranged ability on target
- `E` interact / harvest / attack / loot / open NPC UI depending on context
- `I` toggle inventory panel
- `K` toggle skills panel
- `Mouse3` hold for free-look camera
- `Escape` close open UI or open pause menu

Important: input behavior has been one of the most actively changed areas in the prototype. Treat movement feel as unstable until it has had a deliberate cleanup pass.

---

## Gameplay Systems

### World Generation

`worldgen.py` currently generates a large square world around the origin.

Key behaviors:

- clears a safe spawn radius around `(0, 0)`
- places forest clusters
- places ore patches with tan ground decals
- generates rivers with blue ribbon decals
- places fishing spots along river curves
- spawns both scouts and spitters
- culls trees, rocks, and hostiles if they land on rivers

The world generator uses separate seeded RNG streams per subsystem, which is good. It means changing one subsystem does not automatically reshuffle all others.

### Resources

`resources.py` implements a base `ResourceNode` with:

- proximity check
- hold-`E` harvesting
- depletion
- delayed respawn
- XP reward and inventory grant

Current resource types:

- `Tree` -> `wood` / `Woodcutting`
- `Rock` -> `ore` / `Mining`
- `FishingSpot` -> `fish` / `Fishing`

### Inventory and Skills

`inventory.py` still uses a simple but serviceable structure:

- `slots`: list of `None` or `{id, quantity}`
- stackable items merge into existing stacks
- skills are tracked as XP totals by name

Current items:

- `wood`
- `ore`
- `fish`
- `gold`

Current skills:

- `Woodcutting`
- `Mining`
- `Fishing`

### Bank and Vendor

`bank.py` now contains a more intentional building rather than a placeholder box.

The bank includes:

- a procedural structure
- banker NPC inside the building
- bank UI with deposit/withdraw
- persistence to `data/save.json`

`vendor.py` provides:

- reusable humanoid NPC visuals through `npc.py`
- buy/sell UI
- gold-driven transactions

Only the bank persists right now.

### Hostiles and Combat

`follower.py` is the current hostile module and includes both enemy types.

`Follower`:

- patrols around a patrol center
- aggros within range
- chases and melees the player
- drops loot
- falls over on death
- respawns after a timer

`Spitter` extends `Follower` and adds:

- ranged projectile attacks on cooldown

Player combat currently works like this:

- click a hostile to target it
- press `1` for melee if in range
- press `2` for ranged if in range
- ranged spawns a small projectile that travels to the target

This is already closer to tab-target combat than action combat, but it is still only the first pass.

### Player State

`player.py` currently owns:

- character controller movement
- health
- regen after no recent damage
- death state
- respawn state
- outgoing targeted projectiles

The player model has already been upgraded beyond the original stick figure:

- thicker limbs/body
- spherical head matching the NPC style
- debug direction arrow above the head

---

## HUD State

`hud.py` now includes:

- top prompt text
- player health bar
- target frame with target health
- inventory popup panel
- skills popup panel
- left-side menu buttons for inventory and skills
- bottom-center debug range indicators
- death message

The HUD is useful for prototyping, but layout ownership is ad hoc. There is no single design pass behind it yet, so expect future rework.

---

## Known Issues And Risks

### 1. Movement / camera tuning is still fragile

This has been the highest-churn area recently. Small changes in:

- player heading logic
- sprint handling
- camera follow speed
- camera snap behavior

can create large feel regressions quickly.

Before making changes here:

1. read `player.py`
2. read `camera.py`
3. verify how `main.py` passes movement state into the camera

Do not assume "movement bug" and "camera bug" are separate.

### 2. Prompt conflicts are real

Several systems write to the same prompt text. This can cause:

- message flicker
- one system clearing another system's prompt
- dead-player or UI prompts fighting with nearby interactables

A future prompt manager with priorities would help.

### 3. UI refresh responsibilities are spread around

Inventory, target HUD, health, prompts, and death UI are refreshed from different places. The current approach works, but it is easy to forget a refresh call when adding a new interaction.

### 4. Geometry helpers are duplicated

`make_box_geom()` in `world.py` and `_make_box_geom()` in `resources.py` are parallel implementations. This is manageable now but should eventually be consolidated.

### 5. Persistence is narrow

Only the bank persists. Everything else is runtime-only.

### 6. No reliable local automated verification yet

There is a `test_movement.py`, but there is no meaningful automated test suite. Most validation is still manual in-engine testing.

---

## Developer Notes

### Ground rules

- no external art assets
- keep geometry procedural
- prefer simple readable code over clever abstractions
- be careful with Panda3D backface culling on custom geometry
- avoid broad rewrites in `player.py` and `camera.py` without testing feel in-engine

### If you add a new NPC

Start with `npc.py`:

- use `InteractableNpc` if it is a proximity interaction NPC
- use `build_humanoid_npc()` for a quick visual baseline
- use `attach_billboard_label()` for floating text

### If you add a new hostile type

Start with `follower.py` and `worldgen.py`:

- subclass `Follower` if patrol/aggro/death/loot flow is similar
- add spawning rules in `worldgen.py`
- verify river culling still removes bad placements
- update targeting behavior only if the new enemy should be non-targetable or special-case

### If you add a new item

Update `inventory.py` first. Most UI and trading code depends on the central `ITEMS` registry.

### If you touch combat ranges

You likely need to review all of:

- `player.py` ability ranges
- `hud.py` range indicators
- `follower.py` aggro / attack / projectile distances

### If you touch UI opening/closing

Check `main.py` camera UI state handling. The camera changes behavior when UI is open, and that is easy to break accidentally.

---

## Suggested Near-Term Backlog

### Priority 1: Stabilize control feel

- fix remaining sprint-turn edge cases
- decide whether movement is permanently tank-style or camera-relative
- clean up camera follow vs right-click freelook behavior
- remove debug-only behavior once the control model is locked

### Priority 2: Clean combat pass

- add explicit cooldown display for abilities
- add hit feedback and damage numbers
- improve enemy death/readability
- decide whether `E` remains a contextual attack/loot key
- add clearer target acquisition feedback

### Priority 3: System cleanup

- centralize geometry helpers
- centralize prompt priority handling
- reduce UI refresh duplication
- split large modules if needed after behavior stabilizes

### Priority 4: Content pass

- more enemy variants
- more items and drops
- more buildings and service NPCs
- denser biome identity in world generation

### Priority 5: Persistence

- save player inventory
- save skill XP
- decide whether hostile/resource state should persist

---

## Longer-Term Direction

If the project continues toward a fuller ARPG / MMO-lite feel, a reasonable arc would be:

1. lock movement/camera/combat fundamentals
2. formalize abilities, cooldowns, and stats
3. expand world content and NPC roles
4. add persistence and progression
5. only then spend heavier effort on presentation polish

Right now the biggest leverage is still system clarity, not content volume.

---

## Recommended Next Docs

`PLAN.md` is now the high-level current-state document. Good follow-up docs would be:

- `COMBAT.md` for target/combat rules
- `WORLDGEN.md` for generation rules and tuning knobs
- `UI.md` for HUD ownership and panel behavior
- `KNOWN_ISSUES.md` for active regressions during rapid iteration

Those are optional, but they would keep `PLAN.md` from turning into a dump of implementation detail over time.
