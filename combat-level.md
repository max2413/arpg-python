# Combat Level Proposal

## Summary

This proposal adds an overall combat level to the game as a rough, player-facing summary of combat readiness.

The goal is not to claim that a level 10 player and a level 10 rat are mathematically identical. The goal is to give both players and mobs a simple number that communicates rough difficulty, rough readiness, and rough placement in the world.

In this model:

- Combat level is a readability and scaling tool.
- Real combat power still comes from combat skills, gear, and creature stat blocks.
- Matching levels imply rough parity, not exact fairness.

## Design Goals

- Give the player a single overall number that summarizes combat progression.
- Make mob difficulty easier to read at a glance.
- Support content tuning, spawn scaling, and zone recommendations.
- Preserve the existing skill-based progression model instead of replacing it.
- Keep the system simple enough that players can understand what the number means.

## Core Model

### Player Combat Level

Player combat level is derived only from the combat skills:

- `Melee`
- `Ranged`
- `Magic`
- `Defense`

Non-combat skills such as gathering and crafting do not contribute to combat level.

This keeps the number focused on what it is meant to represent: fighting readiness.

### Creature Combat Level

Creature combat level is assigned manually in creature data through a `level` field.

This level is a tuning label for expected threat, not a strict formula output. A creature's real strength still comes from its actual stat block, AI behavior, and role. The level is there to communicate intended danger and to support easier balancing and scaling.

## What a Level Means

A combat level should be interpreted as a rough measure of combat proportionality.

- A level 10 player means: this character is roughly ready for level 10 combat content.
- A level 10 rat means: this rat variant is intended to be a reasonable threat within that same general band.

It does not mean:

- equal health
- equal damage
- equal move set
- equal AI complexity
- equal fight duration

It means the two are broadly meant to belong in the same combat bracket.

This is intentionally close to the RuneScape idea of combat level: a rough, useful shorthand rather than a perfect theorem of combat balance.

## Why This Fits This Game

This project already has a progression model that maps well to this approach.

- Player power already comes from combat skill levels plus equipped gear.
- Creatures already use hand-authored stat blocks.
- Combat styles are already separated into `Melee`, `Ranged`, `Magic`, and `Defense`.

Because of that, a rough summary level is a better fit than a fully simulation-derived level. The project is already authored and tuned in a practical way. A manually guided combat level respects that structure and makes it easier to communicate it to the player.

## Candidate Player Formulas

The player formula should stay simple, readable, and easy to tune.

### Option A: Weighted Highest Style + Defense

```text
combat_level = floor((max(melee, ranged, magic) * 0.7) + (defense * 0.3))
```

Why it works:

- rewards specialization cleanly
- gives defense a meaningful but secondary role
- is easy to explain to players and easy to tune

This is the recommended default for v1.

### Option B: Highest Style + Half of Defense

```text
combat_level = floor(max(melee, ranged, magic) + (defense * 0.5))
```

Why it works:

- feels more generous
- makes defensive progression more visible
- produces larger numbers faster

Downside:

- can overstate general combat readiness
- makes defense disproportionately influential in some builds

### Option C: Average of Best Style and Defense

```text
combat_level = floor((max(melee, ranged, magic) + defense) / 2)
```

Why it works:

- very easy to reason about
- keeps offense and defense visually balanced

Downside:

- can feel too flat
- does not distinguish strong offensive specialization clearly enough

## Recommended Formula

The recommended v1 formula is:

```text
combat_level = floor((max(melee, ranged, magic) * 0.7) + (defense * 0.3))
```

Reasons:

- It mirrors the intended design well: offense drives combat identity, defense smooths durability.
- It is easy to communicate in UI and documentation.
- It avoids implying that all combat styles must be leveled evenly.
- It fits the current repo, where players typically express strength through one main offensive style plus general survivability.

## Creature Level Guidance

Creatures should get a manual `level` field in `data/creatures.json`.

That number should be tuned against actual fight feel, not derived automatically from stats in v1.

Suggested guidance:

- Start with species fantasy and role.
- Compare the creature to the expected player combat band it should challenge.
- Adjust the creature level after practical testing, not just spreadsheet logic.

Examples:

- `deer`: low-level passive creature
- `scout`: early to mid hostile
- `ranger`: early to mid hostile with ranged pressure
- `wolf`: stronger early hostile or low-mid hostile

This approach also leaves room for future variants. A rat does not have to be forever low-level. A diseased cave rat, elite rat, or zone-specific rat can be much higher level if its intended danger justifies it.

## Relationship to Gear

Gear still matters a lot for actual combat performance.

That is acceptable.

Combat level should not try to fully encode every power swing from gear in v1. Doing so would make the number harder to explain, less stable, and more likely to mislead.

Recommended v1 stance:

- combat level comes from combat skills only
- gear affects actual performance, not the displayed combat level

Possible future enhancement:

- add a small item-power adjustment for unusually strong endgame gear

That should stay out of the first version unless the lack of gear influence makes the number feel obviously wrong in playtesting.

## Usage Recommendations

Combat level should be used as a communication and content tool.

Recommended uses:

- show player combat level in the skills or stats UI
- show target creature level in labels or tooltips
- use level bands for zone recommendations
- use level bands to guide spawn scaling and encounter placement
- use level bands as one input for reward and XP balancing

Combat level should not be used for direct level-vs-level combat math in v1.

Avoid for now:

- hidden hit chance penalties
- hidden damage multipliers
- automatic "too high level to fight" suppression

The game already has functioning stat-based combat. Hidden level math would make balance harder to reason about and would blur the purpose of the number.

## Public Interface and Data Changes

This proposal implies the following future additions:

- `Skills` or a progression helper exposes a derived player combat level
- `Player` exposes `get_combat_level()`
- creature definitions gain a manual `level` field
- UI displays:
  - player combat level
  - target creature level

These changes are additive. They do not replace the existing skill progression model.

## Explicitly Out of Scope for V1

The first version should not attempt to do any of the following:

- replace skill-specific progression
- include gathering or crafting skills in combat level
- apply level-based hit chance or damage modifiers
- auto-generate creature level from stats
- fully model gear inside the combat level number

Keeping the first version narrow will make it easier to introduce, explain, and tune.

## Example Scenarios

### Example 1: Melee-Focused Player

A player with:

- `Melee 12`
- `Defense 10`
- low `Ranged`
- low `Magic`

would land around combat level 11 under the recommended formula and would be suited for early-mid melee content.

### Example 2: Creature Identity Does Not Lock Level

A wolf can be level 12 even if a basic rat is level 3.

Later, a diseased cave rat could also be level 12 if its stats, zone placement, and intended danger justify that label.

The species name does not determine the level. The intended threat band does.

### Example 3: Same Level, Different Real Performance

Two level 10 players may still perform differently if:

- one has poor gear
- one has strong gear
- one is fighting with their best combat style
- one is using an off-style setup

That is acceptable. Combat level is meant to be approximate, not perfectly predictive.

## Caveats

- Combat level is an estimate, not an exact simulation.
- Build specialization will make players of the same combat level feel different.
- Creature level is a communication and tuning tool, not a proof of fairness.
- Gear can create real power differences that the level number does not fully capture.

## Recommended Default

The preferred direction for this project is:

- RuneScape-like readability
- player combat level derived from combat skills only
- creature level assigned manually
- combat level used for UX and content scaling, not direct combat math

This gives the game a clean overall number without undermining the current skill and stat systems.

---

## Critique and Balancing Notes

### What the combat level system is actually solving

The core problem is legibility: a player sees "Ranger" and has no idea whether they will win or die. Combat level solves this by giving both the player and the creature a number on a shared scale. That goal is clear and correct.

The secondary goal, based on design intent, is to make the number a *gauge of capability* — not a perfect theorem, but enough that a player can look at the gap between their level and a creature's and make a reasonable decision.

### The gear problem needs to be addressed first

As of the current stat values, gear dominates skill in the early game by a large margin:

- Bronze Sword gives +22 melee_damage flat.
- Melee skill gives +1.5 melee_damage per level above 1.
- That means a sword is worth roughly 14-15 Melee levels of raw damage output.

The design goal is a 50/50 split between gear and skill contribution to combat power. The current numbers are closer to 90/10 in favor of gear at low levels. Until that ratio is corrected, the combat level formula will produce numbers that are actively misleading. A Melee-5 player with a sword may trivialize content labeled as "level 10," and a Melee-10 player without gear may struggle with "level 5" content.

**Balancing strategy for gear vs. skill:**

The cleanest way to approach this is to define what a "baseline" player looks like at a given combat level, then check that skill and gear each account for roughly half of total power at that baseline.

A rough method:

1. Pick a target level band (e.g., combat level 10).
2. Define what the baseline player looks like: what skill levels, what gear tier.
3. Compute total melee_damage at that baseline.
4. Strip the gear. What percentage of damage came from skills alone?
5. Strip the skills (set to 1). What percentage came from gear alone?
6. Adjust either the per-level skill bonuses or the gear item values until the split is close to 50/50 at the target band.

This does not need to be exact. A 40/60 split is fine. A 20/80 split is not — it makes the skill levels feel cosmetic.

One concrete adjustment to consider: raise the melee skill damage bonus from +1.5/level to something closer to +2.5 or +3.0/level, and reduce the flat damage on early weapons accordingly. This makes skill levels feel more meaningful without nerfing gear into irrelevance.

### The formula weights don't reflect actual stat value

The recommended formula (`max(melee, ranged, magic) * 0.7 + defense * 0.3`) treats the 0.7/0.3 split as if it reflects the relative value of offense vs. defense per level. It doesn't — it was chosen to feel reasonable.

In the actual stat system, Defense gives +10 max_health, +0.5 armor, and +0.5% block chance per level. Melee gives +1.5 damage and +0.5% parry per level. Defense is doing substantially more per level in terms of survivability than the formula's 30% weight suggests.

This is not necessarily a flaw in the formula — the weights are a tuning knob, not a theorem. But it means the formula should be validated by feel rather than by math. A defense-heavy player should look underleveled for their actual durability. If that feels wrong in play, increase the defense weight.

**For now: treat the weights as placeholders to be adjusted after the gear balance pass.** The formula structure is fine; the coefficients need empirical tuning.

### The creature legibility problem requires a reference ladder

The stated goal — "I see a Ranger, I don't know if I can win, I want to know" — requires creature levels to be anchored to a player progression ladder that players internalize quickly.

Manual assignment without a reference ladder produces drift. When you add the tenth creature, you will not remember what level 8 felt like when you assigned it to the Scout six months ago.

**Suggested approach: define a small fixed ladder and assign all creatures relative to it.**

Example ladder (adjust numbers to match your actual XP curve):

| Level | Meaning |
|-------|---------|
| 1–3   | Tutorial threat. New player wins with no gear and no skill. |
| 4–7   | Early game. Requires basic gear or a few skill levels to fight comfortably. |
| 8–12  | Mid-early. A player with one skill at 8–10 and decent gear should be roughly matched. |
| 13–20 | Mid game. Requires deliberate progression to not die quickly. |
| 20+   | Late game. Reserved for now. |

With this ladder, assigning Deer = 2, Scout = 6, Ranger = 6, Wolf = 9 becomes a statement with a shared reference point. "Scout is an early-game threat requiring basic gear to fight safely" is now encoded in the number.

Revisit the ladder after each major content addition. The point is not to get it perfect now — it is to have a shared anchor so future assignments stay consistent.

### The three-option formula section should be trimmed

Option A has been chosen. Options B and C add noise for anyone reading this doc in the future. Either remove them or reframe them as "rejected alternatives with reasons," so the rationale for Option A is clear without suggesting the choice is still open.

### Summary of recommended actions

1. **Do a gear vs. skill balance pass before tuning creature levels.** The combat level number will not be meaningful until the 50/50 power split is approximately correct.
2. **Define a small reference ladder for creature levels** and assign the four existing creatures to it. Use this as the anchor for all future assignments.
3. **Treat formula weights as post-balance-pass tuning knobs**, not final values. Revisit them after gear and skill numbers are more stable.
4. **Cut the alternative formula options** from the main doc or move them to an appendix.
5. **Consider raising the per-level skill damage bonus** to make skill progression feel meaningful relative to gear.

---

## Developer Feedback (Post-Research)

After reviewing the current codebase and balance, here are my additional thoughts:

1.  **Gear Power vs. Skill Level**: The "90/10" gear-to-skill power ratio is a significant risk. At current values, a level 1 player with a Greatsword (+35) is nearly 3x as powerful as a level 10 player (+13.5 from skills) fighting unarmed. Combat Level will need an "Item Power" component or a significant rebalance of base item stats to be a reliable guide.
2.  **Stat Utility**: Defense is currently very high value per level (+10 HP is 10% of base health). The 30% weight in the combat formula might under-represent how much harder a high-defense player is to kill compared to a glass cannon of the same level.
3.  **UI Feedback**: Showing the level in the target HUD is essential. However, we should also consider color-coding the level (e.g., green for -3 levels, yellow for parity, red for +3 levels) to provide instant visual threat assessment.
4.  **Specialization**: The `max(melee, ranged, magic)` approach is perfect for this game, as it encourages players to experiment with different styles without "ruining" their combat level by being a jack-of-all-trades.
