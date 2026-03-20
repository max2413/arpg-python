# Item & Crafting System

## Design Intent

Strict stat progression per tier — higher tier gear is always stronger as a
baseline. Enhancement is a freeform layer on top with no tier restrictions.
A T1 item infused with a T5 enhancement is valid and interesting. Players are
never locked into a single upgrade path.

---

## Equipment Slots

| Slot | Category | Primary Stat |
|------|----------|-------------|
| Head | Armor | Defense |
| Chest | Armor | Defense (highest) |
| Legs | Armor | Defense |
| Hands | Armor | Defense + secondary |
| Feet | Armor | Defense + speed |
| Weapon | Combat | Damage |
| Off-hand | Combat | Defense or spell power |
| Ranged | Combat | Ranged damage |
| Ring | Jewelry | Utility bonus |
| Necklace | Jewelry | Utility bonus |

---

## Material Tiers

All tiers follow the same level band. Enhancement has no tier restriction —
any enhancement can be applied to any tier of base item.

| Tier | Level Band | Smithing/LW/Tailoring/Fletching Level |
|------|------------|--------------------------------------|
| 1 | 1–5 | 1 |
| 2 | 6–10 | 10 |
| 3 | 11–15 | 15 |
| 4 | 16–20 | 20 |
| 5 | 21–25 | 30 |

---

## Blacksmithing

### Forge Fuel

Wood fuels the basic forge for T1–T2 smelting. Coal is required for T3 and
above — wood does not burn hot enough. Exact fueling mechanic TBD.

| Forge | Fuel | Unlocks |
|-------|------|---------|
| Basic Forge | Wood logs | T1–T2 smelting |
| Coal Forge | Coal | T3–T5 smelting |

### Smelting (Ore → Bar)

| Bar | Ingredients | Fuel | Smithing Lvl |
|-----|------------|------|-------------|
| Copper Bar | Copper Ore x2 | Wood | 1 |
| Iron Bar | Iron Ore x2 | Wood | 10 |
| Steel Bar | Iron Ore x2 + Coal x1 | Coal | 15 |
| Mithril Bar | Mithril Ore x3 | Coal | 20 |
| Adamant Bar | Adamant Ore x3 + Coal x2 | Coal | 30 |

### Weapons (per tier, all use that tier's bar)

| Weapon | Bars | Notes |
|--------|------|-------|
| Dagger | x1 | Fast, low damage |
| Sword | x2 | Balanced |
| Mace | x2 | Slower, bonus vs armor |
| Axe | x2 | High damage, lower accuracy |
| Two-handed Sword | x4 | No off-hand, highest melee damage |
| Shield | x2 + Wood x1 | Off-hand, defense focused |

### Armor (per tier, all use that tier's bar)

| Piece | Bars | Slot |
|-------|------|------|
| Helm | x2 | Head |
| Platebody | x5 | Chest |
| Platelegs | x3 | Legs |
| Gauntlets | x1 | Hands |
| Sabatons | x1 | Feet |

### Jewelry (Blacksmithing + Gem)

Any gem can be set into any tier of band. The gem determines the bonus,
the band determines the base defense value.

| Band | Bars | Smithing Lvl | Slot |
|------|------|-------------|------|
| Copper Band | Copper Bar x1 | 5 | Ring or Necklace |
| Iron Band | Iron Bar x1 | 10 | Ring or Necklace |
| Steel Band | Steel Bar x1 | 15 | Ring or Necklace |
| Mithril Band | Mithril Bar x1 | 20 | Ring or Necklace |
| Adamant Band | Adamant Bar x1 | 30 | Ring or Necklace |

| Gem | Source | Ring Bonus | Necklace Bonus |
|-----|--------|------------|----------------|
| Flint | Mining byproduct | +2 defense | +2% XP gain |
| Jasper | Mining (lv 10) | +5 defense | +5% XP gain |
| Garnet | Mining (lv 15) | +3% all stats | +8% XP gain |
| Sapphire | Mining (lv 20) | +6% all stats | +10% gathering speed |
| Ruby | Mining (lv 25) | +10% all stats | +15% gathering speed |
| Diamond | Rare world drop | +12% all stats | +20% gathering speed |

### Armor Painting (Enhancement — no tier restriction)

Dyes drop from enemies and world nodes. Any dye can be applied to any tier
of plate armor. Painted armor retains its dye slot permanently — can be
repainted with a new dye.

| Dye | Drop Source | Visual | Bonus |
|-----|------------|--------|-------|
| Rust Dye | Mining byproduct, common | Deep red | +1 defense |
| Charcoal Dye | Coal nodes, common | Matte black | +3 defense |
| Forest Dye | Foraged plants | Dark green | +2% physical resist |
| Bone Dye | Skeleton enemies | Off-white | +3% undead resist |
| Silver Dye | Mithril dust byproduct | Bright silver | +2% reflect |
| Azure Dye | Rare fish drop | Deep blue | +4% magic resist |
| Crimson Dye | Dragon enemy drop | Vivid red | +4% fire resist |
| Void Dye | Boss drop, rare | Black + purple sheen | +5% all resist |
| Chromatic Dye | Rare ore vein | Player color choice | +3% reflect |
| Gold Dye | Adamant byproduct | Gold trim | +5% reflect |

---

## Leatherworking

### Hides (Skinning → Leather)

| Material | Skinning Source | Skinning Lvl | Tier |
|----------|----------------|-------------|------|
| Scrappy Hide | Rabbits, deer, small animals | 1 | 1 |
| Cured Leather | Wolves, boar | 10 | 2 |
| Thick Hide | Bears, crocodiles | 15 | 3 |
| Drake Skin | Drakes, wyverns | 20 | 4 |
| Shadow Leather | Shadow beasts, rare | 30 | 5 |

### Armor (per tier, uses that tier's hide)

| Piece | Hides | Slot |
|-------|-------|------|
| Leather Hood | x2 | Head |
| Leather Chest | x4 | Chest |
| Leather Legs | x3 | Legs |
| Leather Gloves | x1 | Hands |
| Leather Boots | x1 | Feet |

### Ranged Gear (Leatherworking)

| Item | Materials | Notes |
|------|-----------|-------|
| Quiver | Hide x1 | Off-hand, +10% ranged speed |
| Ranger Cloak | Hide x3 | Chest slot variant, +dodge |
| Archer Gloves | Hide x1 + Feather x5 | Hands, +ranged accuracy |

### Hide Enhancement (no tier restriction)

Any special hide can enhance any tier of leather armor. The hide is consumed
on application. One enhancement slot per armor piece.

| Enhancement Hide | Source | Bonus |
|-----------------|--------|-------|
| Wolf Pelt | Wolves | +5% movement speed |
| Boar Tusk Hide | Boars | +8% physical resist |
| Bear Fur | Bears | +10% max HP |
| Croc Scale | Crocodiles | +8% poison resist |
| Drake Scale | Drakes | +12% fire resist |
| Shadow Fur | Shadow beasts | +15% dodge |
| Dragon Hide | Dragons (rare) | +20% all resist |

Dragon Hide can be applied to T1 scrappy armor. It's rare, it's powerful,
and that is the point.

---

## Tailoring

### Cloth (Farming / Mob Drops → Cloth)

| Material | Source | Tailoring Lvl | Tier |
|----------|--------|--------------|------|
| Rough Flax | Farming, common drops | 1 | 1 |
| Linen | Humanoid drops, farming | 10 | 2 |
| Silk | Rare mob drops, merchants | 15 | 3 |
| Arcane Weave | Enchanted mob drops | 20 | 4 |
| Voidweave | Boss drops, rare world nodes | 30 | 5 |

### Armor (per tier, uses that tier's cloth)

| Piece | Cloth | Slot |
|-------|-------|------|
| Cloth Hat | x2 | Head |
| Robe | x5 | Chest |
| Cloth Leggings | x3 | Legs |
| Cloth Gloves | x1 | Hands |
| Cloth Boots | x1 | Feet |

### Alchemy Infusion (Enhancement — no tier restriction)

Any potion can be infused into any tier of cloth armor. The infusion embeds
a lite passive version of the potion effect permanently. The potion is
consumed on infusion. One infusion slot per armor piece.

Infused effect strength = ~40% of the potion's active effect, always-on.

| Potion Infused | Embedded Passive |
|---------------|-----------------|
| Minor Healing Salve | +1 HP regen/sec |
| Healing Potion | +2 HP regen/sec |
| Greater Healing | +4 HP regen/sec |
| Stamina Brew | +8% stamina pool |
| Swiftness Draught | +6% move speed |
| Iron Skin | +6% physical resist |
| Mana Infusion | +10% mana regen |
| Arcane Surge | +8% spell damage |
| Berserker Draught | +10% damage, -4% defense |
| Venom Coat | Passive poison on hit (weak) |

A T1 robe infused with Arcane Surge is weaker stat-wise than a T5 Voidweave
robe but that choice is the player's to make.

---

## Fletching

### Wood (Woodcutting → Logs)

| Log | Tree Source | WC Level | Tier |
|-----|------------|----------|------|
| Pine Log | Common pine trees | 1 | 1 |
| Ash Log | Ash trees | 10 | 2 |
| Yew Log | Yew trees | 15 | 3 |
| Magic Log | Rare enchanted trees | 20 | 4 |
| Elder Log | Ancient trees, rare nodes | 30 | 5 |

### Bows & Crossbows (per tier, uses that tier's log)

| Weapon | Materials | Style | Notes |
|--------|-----------|-------|-------|
| Shortbow | Log x1 + Leather String x1 | Ranged | Fast attack speed |
| Longbow | Log x2 + Leather String x1 | Ranged | Slower, higher damage |
| Crossbow | Log x2 + Iron Bar x1 + Leather x1 | Ranged | Highest damage, slowest |
| Staff | Log x2 | Magic | Channels spells, mage weapon |
| Wand | Log x1 | Magic | Fast cast, lower spell power |

Leather String is a Leatherworking byproduct (hide scraps). The Crossbow
requires a metal bar regardless of tier — the mechanism needs metal.

### Ammunition (consumable)

| Ammo | Materials | For | Fletching Lvl |
|------|-----------|-----|--------------|
| Arrows (20) | Log x1 + Feather x5 | Bows | 1 |
| Broad Arrows (20) | Log x1 + Iron Bar x1 + Feather x5 | Longbow | 10 |
| Steel Arrows (20) | Log x1 + Steel Bar x1 + Feather x5 | Any bow | 15 |
| Bolts (20) | Iron Bar x1 + Feather x3 | Crossbow | 5 |
| Steel Bolts (20) | Steel Bar x1 + Feather x3 | Crossbow | 15 |
| Mithril Bolts (20) | Mithril Bar x1 + Feather x3 | Crossbow | 20 |

Feathers drop from Skinning birds and poultry — a small cross-skill loop
that gives Skinning secondary value for ranged players.

---

## Enchanting

Enchanting applies to weapons only. It is gated by the Magic skill level,
not crafting materials. Enchants follow a linear progression — each enchant
requires the previous tier to be learned first. One enchant per weapon,
can be overwritten at cost of the previous enchant.

| Enchant | Effect | Magic Level Required |
|---------|--------|---------------------|
| Sharpen | +5% damage | 5 |
| Flaming Edge | +fire damage on hit | 10 |
| Stunning Blow | Chance to stun on hit | 15 |
| Soul Leech | +lifesteal % | 20 |
| Ruin | +15% damage, ignore 10% defense | 30 |

Enchanting reagents (rare drops, vendor-purchased) are TBD. The intent is
a meaningful gold sink for high-tier enchants.

---

## Alchemy

### Ingredient Sources

| Ingredient | Source | Notes |
|------------|--------|-------|
| Marigold | Foraging, common | Core healing ingredient |
| Belladonna | Foraging, common | Universal stabilizer |
| Bloodmoss | Foraging, uncommon | Combat potions |
| Ironbark Sap | Woodcutting byproduct | Cross-skill |
| Dragon's Tongue | Foraging, rare | High-tier healing |
| Starbloom | Night-cycle spawn, rare | Magic potions |
| Void Spore | Boss/dungeon drop | Endgame ingredient |
| Clean Water | World resource | Universal base |

### Potions

| Potion | Ingredients | Effect | Duration | Alchemy Lvl |
|--------|------------|--------|----------|-------------|
| Minor Healing Salve | Marigold + Water | Restore 30 HP | Instant | 1 |
| Healing Potion | Marigold x2 + Belladonna | Restore 80 HP | Instant | 5 |
| Greater Healing | Dragon's Tongue + Marigold x2 | Restore 200 HP | Instant | 15 |
| Stamina Brew | Belladonna + Water | +20% stamina pool | 5 min | 1 |
| Iron Skin | Ironbark Sap + Belladonna | +15% physical resist | 5 min | 10 |
| Swiftness Draught | Bloodmoss + Belladonna | +15% move speed | 3 min | 10 |
| Berserker Draught | Bloodmoss + Dragon's Tongue | +25% damage, -10% defense | 2 min | 20 |
| Mana Infusion | Starbloom + Water | +25% mana regen | 5 min | 20 |
| Venom Coat | Bloodmoss + Belladonna | Poison on hit | 10 hits | 15 |
| Arcane Surge | Void Spore + Starbloom | +20% spell damage | 2 min | 30 |

---

## Cross-Skill Dependency Map

```
Mining ──→ Coal ────────────────────→ Blacksmithing T3+ (forge fuel)
Mining ──→ Ore ─────────────────────→ Blacksmithing bars
Mining ──→ Gems ────────────────────→ Jewelry
Mining ──→ Dye byproducts ──────────→ Armor painting
Skinning ──→ Hide ──────────────────→ Leatherworking armor
Skinning ──→ Special Hide ──────────→ Leatherworking enhancement (any tier)
Skinning ──→ Feathers ──────────────→ Fletching arrows/bolts
Skinning ──→ Hide / Meat / Feathers ─→ Crafting + Cooking + Fletching
Woodcutting ──→ Logs ───────────────→ Fletching bows/staves + forge fuel (T1-2)
Woodcutting ──→ Ironbark Sap ───────→ Alchemy
Leatherworking ──→ Leather String ──→ Fletching
Blacksmithing ──→ Metal Bars ───────→ Fletching crossbows/bolts
Alchemy ──→ Potions ────────────────→ Tailoring infusion (any tier)
Foraging ──→ Herbs ─────────────────→ Alchemy
Magic ───────────────────────────────→ Enchanting weapons
```

No skill is fully self-contained at higher tiers. Every path eventually
touches at least one other.

---

## Open Items

- Alchemy reagent costs for enchanting (gold sink TBD)
- Forge fueling mechanic (how coal is loaded/consumed)
- Farming skill path (cloth raw material supply)
- Foraging skill path (alchemy ingredient supply)
- Magic skill path (unlocks enchanting tiers)
- Arrow/bolt inventory management (stack size, quiver capacity)
- Enhancement removal mechanic (can enhancements be swapped out?)
