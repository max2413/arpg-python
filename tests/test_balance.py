"""Regression tests for pure balance math."""

import unittest

from game.systems import balance


class BalanceMathTests(unittest.TestCase):
    def test_xp_curve_is_monotonic(self):
        values = [balance.level_to_xp(level) for level in range(1, 21)]
        self.assertEqual(values[0], 0)
        for earlier, later in zip(values, values[1:]):
            self.assertGreaterEqual(later, earlier)

    def test_xp_to_level_round_trips_at_level_boundaries(self):
        for level in range(1, 15):
            xp = balance.level_to_xp(level)
            self.assertEqual(balance.xp_to_level(xp), level)
            if level > 1:
                self.assertEqual(balance.xp_to_level(xp - 1), level - 1)

    def test_player_and_enemy_hp_increase_with_level(self):
        for level in range(1, 20):
            self.assertGreater(
                balance.player_max_hp(level + 1),
                balance.player_max_hp(level),
            )
            self.assertGreater(
                balance.enemy_max_hp(level + 1),
                balance.enemy_max_hp(level),
            )

    def test_damage_reduction_is_bounded(self):
        self.assertEqual(balance.damage_reduction(0), 0.0)
        self.assertGreater(balance.damage_reduction(50), 0.0)
        self.assertLess(balance.damage_reduction(50), 1.0)
        self.assertLess(balance.damage_reduction(5000), 1.0)

    def test_style_damage_bonus_is_positive_and_magic_is_not_weaker_than_melee(self):
        for level in (1, 5, 10, 20):
            melee = balance.style_damage_bonus(level, "melee")
            ranged = balance.style_damage_bonus(level, "ranged")
            magic = balance.style_damage_bonus(level, "magic")
            self.assertGreater(melee, 0)
            self.assertGreater(ranged, 0)
            self.assertGreater(magic, 0)
            self.assertGreaterEqual(magic, melee)

    def test_creature_armor_scales_with_level(self):
        for level in range(1, 20):
            self.assertGreaterEqual(
                balance.creature_armor_for_level(level + 1),
                balance.creature_armor_for_level(level),
            )

    def test_creature_runtime_stats_scale_with_level(self):
        low = balance.creature_runtime_stats({"level": 2})
        high = balance.creature_runtime_stats({"level": 8})
        self.assertGreater(high["max_health"], low["max_health"])
        self.assertGreater(high["armor"], low["armor"])
        self.assertGreater(high["melee_damage"], low["melee_damage"])

    def test_creature_roles_and_scaling_modify_runtime_stats(self):
        standard = balance.creature_runtime_stats({"level": 5})
        passive = balance.creature_runtime_stats({"level": 5, "role": "passive"})
        bruiser = balance.creature_runtime_stats({"level": 5, "role": "bruiser"})
        self.assertLess(passive["max_health"], standard["max_health"])
        self.assertEqual(passive["melee_damage"], 0.0)
        self.assertGreater(bruiser["max_health"], standard["max_health"])
        self.assertGreater(bruiser["armor"], standard["armor"])

    def test_explicit_creature_stat_overrides_win(self):
        stats = balance.creature_runtime_stats(
            {
                "level": 4,
                "role": "ranged",
                "combat": {"style": "ranged"},
                "stats": {"max_health": 123.0, "ranged_damage": 17.0},
            }
        )
        self.assertEqual(stats["max_health"], 123.0)
        self.assertEqual(stats["ranged_damage"], 17.0)

    def test_benchmark_rows_have_expected_shape(self):
        rows = balance.benchmark_rows((1, 5, 10, 20))
        self.assertEqual([row["level"] for row in rows], [1, 5, 10, 20])
        for row in rows:
            self.assertIn("xp_required", row)
            self.assertIn("player_hp", row)
            self.assertIn("enemy_hp", row)
            self.assertIn("ttk", row)
            self.assertGreater(row["player_hp"], 0)
            self.assertGreater(row["enemy_hp"], 0)
            self.assertGreater(row["ttk"], 0)


if __name__ == "__main__":
    unittest.main()
