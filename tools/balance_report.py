"""Print a quick balance report for benchmark levels and current creature data."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CREATURES_PATH = ROOT / "data" / "creatures.json"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game.systems import balance


def _load_creatures():
    with CREATURES_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _print_header(title):
    print()
    print(title)
    print("-" * len(title))


def benchmark_report():
    _print_header("Benchmark Levels")
    for row in balance.benchmark_rows((1, 5, 10, 20)):
        print(
            "Lv {level:>2} | XP->{xp_required:<5} | Player HP {player_hp:<4} | "
            "Enemy HP {enemy_hp:<5} | Even TTK {ttk:.2f}s".format(**row)
        )


def creature_report():
    creatures = _load_creatures()
    _print_header("Creature Snapshot")
    for creature_id, data in sorted(creatures.items(), key=lambda item: item[1].get("level", 1)):
        level = int(data.get("level", 1))
        role = data.get("role", "standard")
        style = data.get("combat", {}).get("style", "melee")
        runtime_stats = balance.creature_runtime_stats(data)
        hp = runtime_stats.get("max_health", 0.0)
        armor = runtime_stats.get("armor", 0.0)
        damage = runtime_stats.get(
            f"{style}_damage",
            runtime_stats.get("melee_damage", runtime_stats.get("ranged_damage", runtime_stats.get("magic_damage", 0.0))),
        )
        benchmark_hp = balance.creature_max_hp_for_level(level)
        override_keys = sorted(data.get("stats", {}).keys())
        override_suffix = f" | Overrides {', '.join(override_keys)}" if override_keys else ""
        print(
            f"{data.get('name', creature_id):<12} Lv {level:<2} | "
            f"Role {role:<8} | Style {style:<6} | HP {hp:<7.1f} | "
            f"Armor {armor:<6.2f} | Damage {damage:<6.1f} | "
            f"HP vs Ref {hp / max(1.0, benchmark_hp):>4.0%}{override_suffix}"
        )


def level_sweep_report():
    _print_header("Level Sweep")
    for level in range(1, 16):
        print(
            f"Lv {level:>2} | Base Dmg {balance.base_damage(level):<3} | "
            f"Armor {balance.creature_armor_for_level(level):<5.2f} | "
            f"Player HP {balance.player_max_hp(level):<4} | Enemy HP Ref {balance.enemy_max_hp(level):<5}"
        )


def main():
    benchmark_report()
    creature_report()
    level_sweep_report()


if __name__ == "__main__":
    main()
