# Ursina Port Status

## Summary

The port is real, but not finished.

The project is no longer "a Panda3D game with a little Ursina around it." It is now mostly a Ursina-led runtime with Panda3D/Bullet still handling lower-level world and physics responsibilities. That is the correct direction, and the major architecture shift has already happened.

## What Is In Good Shape

- Ursina owns app bootstrap and the main update flow.
- A shared runtime layer is in place.
- The always-visible HUD shell is on Ursina.
- The pause menu is on Ursina.
- The dev menu is on Ursina.
- The skills window is on Ursina.
- Inventory and equipment are on first-pass Ursina windows.
- The crafting and recipe browser is on Ursina.
- The bank is on a first-pass Ursina window.
- The vendor is on a first-pass Ursina window.
- Rendering and world-attachment issues are much improved from the earlier mixed state.
- Coordinate-system cleanup is far enough along that the game is playable again.

## What Is Still Incomplete

- Many UI surfaces are first-pass functional, not polished.
- Window layout, focus, z-order, and coexistence still need cleanup in places.
- Right-click and context-menu interactions are not yet restored on the new Ursina windows.
- Hover item details and tooltip parity are not yet restored in the new flows.
- Quantity-prompt parity is not yet ported.
- Vendor, bank, and crafting interactions still need polish and consistency work.
- Some old DirectGUI log/debug leftovers still exist.
- Worldgen and interactable regressions still need continued stabilization as they show up.

## Practical Assessment

If summarized in one line:

- The runtime port is mostly successful.
- The gameplay UI port is past the halfway point.
- The remaining work is mostly interaction parity, window polish, and cleanup rather than fundamental engine migration.

## Rough Completion Estimate

- Engine/runtime migration: 75-85%
- Player-facing UI migration: 60-70%
- Overall "feels finished and consistent": lower than those numbers, because polish and parity work now account for a large share of the remaining effort.

## Recommended Next Focus

The next work should continue slice-by-slice rather than doing a big-bang sweep.

Recommended priorities:

1. Stabilize bank and vendor layouts/interactions.
2. Restore quantity prompt parity.
3. Restore hover details/tooltips and context-style interactions where needed.
4. Continue removing remaining DirectGUI holdouts.
5. Finish UI consistency and usability polish after interaction parity is restored.
