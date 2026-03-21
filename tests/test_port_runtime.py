"""Regression tests for the Ursina-facing port boundary and Y-up fixes."""

import unittest
from unittest.mock import patch

from panda3d.core import Vec3
from ursina import time as ursina_time

from game.runtime import RuntimeContext, get_runtime, set_runtime
from game.app import Game
from game.services.bank import Bank
from game.services.crafting import CraftingStation
from game.services.vendor import BUYBACK_QUEUE, Vendor
from game.systems.inventory import Inventory
from game.ui.hud import HUD
from game.world.resources import DEPLETED, HARVESTING, ResourceNode


class _DummyApp:
    mouseWatcherNode = None


class _DummyPlayer:
    def __init__(self, pos):
        self._pos = pos

    def get_pos(self):
        return self._pos

    def play_work_animation(self):
        return None


class _DummyHud:
    def __init__(self):
        self.prompt = ""
        self.inventory_refreshed = False
        self.skills_refreshed = False

    def show_prompt(self, msg):
        self.prompt = msg

    def clear_prompt_if(self, msg):
        if self.prompt == msg:
            self.prompt = ""

    def show_cast_progress(self, *_args):
        return None

    def hide_cast_progress(self):
        return None

    def refresh_inventory(self):
        self.inventory_refreshed = True

    def refresh_skills(self):
        self.skills_refreshed = True


class _DummySkills:
    def __init__(self):
        self.calls = []

    def add_xp(self, skill_name, amount):
        self.calls.append((skill_name, amount))


class _DummyQuestManager:
    def __init__(self):
        self.actions = []

    def notify_action(self, action, target):
        self.actions.append((action, target))


class _DummyGame:
    def __init__(self):
        self.inventory = Inventory(size=4)
        self.skills = _DummySkills()


class _DummyCraftingUi:
    def __init__(self):
        self.open_calls = []
        self.skill_calls = []
        self.hide_calls = 0
        self.opened = False

    def open(self, station_type, station_obj):
        self.open_calls.append((station_type, station_obj))
        self.opened = True

    def open_skill(self, skill_name):
        self.skill_calls.append(skill_name)
        self.opened = True

    def hide(self):
        self.hide_calls += 1
        self.opened = False

    def is_open(self):
        return self.opened


class _DummyHudCraftingUi(_DummyCraftingUi):
    pass


class _DummyLevelObject:
    def __init__(self):
        self.calls = []

    def update(self, *args):
        self.calls.append(args)


class PortRuntimeTests(unittest.TestCase):
    def tearDown(self):
        set_runtime(None)

    def test_runtime_context_exposes_input_adapter(self):
        runtime = RuntimeContext(_DummyApp(), object(), object())
        self.assertIsNotNone(runtime.input_state)

    def test_crafting_station_uses_xz_ground_distance(self):
        hud = _DummyHud()
        station = CraftingStation.__new__(CraftingStation)
        station.pos = Vec3(0, 0, 0)
        station.ui_open = False
        station._prompt_shown = False
        station._in_range = False
        station.prompt_text = "Press E to use"

        CraftingStation.update(station, 0.0, Vec3(0, 999, 4.5), hud)

        self.assertTrue(station._in_range)
        self.assertEqual(hud.prompt, station.prompt_text)

    def test_resource_harvest_uses_runtime_inventory_and_skills(self):
        app = _DummyApp()
        game = _DummyGame()
        runtime = RuntimeContext(app, game, object())
        runtime.player = _DummyPlayer(Vec3(0, 0, 0))
        runtime.hud = _DummyHud()
        runtime.quest_manager = _DummyQuestManager()
        set_runtime(runtime)

        resource = ResourceNode.__new__(ResourceNode)
        resource.pos = Vec3(0, 0, 0)
        resource.item_id = "pine_log"
        resource.skill = "Woodcutting"
        resource.harvest_time = 1.0
        resource.xp_reward = 10
        resource.verb = "chop"
        resource.resource_name = "Pine Tree"
        resource.state = HARVESTING
        resource.harvest_timer = 0.95
        resource.respawn_timer = 0.0
        resource.respawn_time = 15.0
        resource.depleted_delay = 2.0
        resource.in_range = True
        resource._prompt_shown = True
        resource._prompt_text = "Hold E to chop Pine Tree"
        resource._showing_cast_progress = False
        resource._e_held = True
        resource._set_depleted_look = lambda: None
        resource._reset_look = lambda: None
        resource._build_visuals = lambda: None

        original_dt = ursina_time.dt
        ursina_time.dt = 0.1
        try:
            ResourceNode.update(resource)
        finally:
            ursina_time.dt = original_dt

        self.assertEqual(game.inventory.count_item("pine_log"), 1)
        self.assertEqual(game.skills.calls, [("Woodcutting", 10)])
        self.assertEqual(runtime.quest_manager.actions, [("gather", "any")])
        self.assertEqual(resource.state, DEPLETED)
        self.assertTrue(runtime.hud.inventory_refreshed)
        self.assertTrue(runtime.hud.skills_refreshed)

    def test_vendor_patrol_target_stays_on_ground_plane(self):
        vendor = Vendor.__new__(Vendor)
        vendor.ui_open = False
        vendor.static_idle = False
        vendor._state = "idle"
        vendor._patrol_wait = 0.0
        vendor.patrol_center = Vec3(1, 2, 3)
        vendor._target_pos = Vec3(1, 2, 3)
        vendor._animate = lambda *_args, **_kwargs: None
        vendor.update_prompt = lambda *_args, **_kwargs: None

        with patch("game.services.vendor.random.uniform", side_effect=[0.0, 5.0]):
            Vendor.update(vendor, 0.1, Vec3(0, 0, 0), _DummyHud())

        self.assertEqual(vendor._target_pos.y, 2)
        self.assertEqual(vendor._target_pos.z, 3)
        self.assertEqual(vendor._target_pos.x, 6)

    def test_crafting_station_uses_runtime_game_fallback_for_ui(self):
        runtime = RuntimeContext(_DummyApp(), object(), object())
        runtime.game = type("GameStub", (), {"crafting_ui": _DummyCraftingUi()})()
        runtime.crafting_ui = None
        set_runtime(runtime)

        station = CraftingStation.__new__(CraftingStation)
        station.station_type = "forge"
        station.ui_open = False

        CraftingStation.open_ui(station)

        self.assertTrue(station.ui_open)
        self.assertEqual(runtime.game.crafting_ui.open_calls, [("forge", station)])

        CraftingStation.close_ui(station)

        self.assertFalse(station.ui_open)
        self.assertEqual(runtime.game.crafting_ui.hide_calls, 1)

    def test_hud_skill_recipe_button_uses_app_crafting_ui(self):
        crafting_ui = _DummyCraftingUi()
        hud = HUD.__new__(HUD)
        hud.app = type("AppStub", (), {"crafting_ui": crafting_ui})()
        hud.player = None

        HUD._open_skill_recipes(hud, "Alchemy")

        self.assertEqual(crafting_ui.skill_calls, ["Alchemy"])

    def test_hud_skill_recipe_button_prefers_player_game_app(self):
        game_crafting_ui = _DummyCraftingUi()
        hud = HUD.__new__(HUD)
        hud.app = type("UrsinaAppStub", (), {})()
        hud.player = type("PlayerStub", (), {"_app": type("GameStub", (), {"crafting_ui": game_crafting_ui})()})()

        HUD._open_skill_recipes(hud, "Fletching")

        self.assertEqual(game_crafting_ui.skill_calls, ["Fletching"])

    def test_hud_skill_recipe_button_keeps_skills_window_open(self):
        crafting_ui = _DummyCraftingUi()
        hud = HUD.__new__(HUD)
        hud.app = type("AppStub", (), {"crafting_ui": crafting_ui})()
        hud.player = None
        hud._skill_visible = True

        HUD._open_skill_recipes(hud, "Blacksmithing")

        self.assertTrue(hud._skill_visible)
        self.assertEqual(crafting_ui.skill_calls, ["Blacksmithing"])

    def test_bank_transfer_methods_move_items_between_inventories(self):
        bank = Bank.__new__(Bank)
        bank.player_inv = Inventory(size=4)
        bank.bank_inv = Inventory(size=4)
        bank._save = lambda: None
        bank.refresh_ui = lambda: None
        bank._window = None
        bank.player_inv.add_item("pine_log", 5)

        self.assertTrue(Bank.deposit_from_inventory(bank, 0, 3))
        self.assertEqual(bank.player_inv.count_item("pine_log"), 2)
        self.assertEqual(bank.bank_inv.count_item("pine_log"), 3)

        self.assertTrue(Bank.withdraw_to_inventory(bank, 0, 2))
        self.assertEqual(bank.player_inv.count_item("pine_log"), 4)
        self.assertEqual(bank.bank_inv.count_item("pine_log"), 1)

    def test_bank_auto_select_defaults_prefers_first_filled_slots(self):
        bank = Bank.__new__(Bank)
        bank.player_inv = Inventory(size=4)
        bank.bank_inv = Inventory(size=4)
        bank._selected_player_slot = None
        bank._selected_bank_slot = None
        bank.player_inv.add_item("pine_log", 1)
        bank.bank_inv.add_item("copper_ore", 1)

        Bank._auto_select_defaults(bank)

        self.assertEqual(bank._selected_player_slot, 0)
        self.assertEqual(bank._selected_bank_slot, 0)

    def test_vendor_buy_sell_and_buyback_flow(self):
        vendor = Vendor.__new__(Vendor)
        vendor.player_inv = Inventory(size=8)
        vendor.vendor_data = {"stock": {"pine_log": 2}}
        vendor._selected_entry = None
        vendor._active_tab = "buy"
        vendor.refresh_ui = lambda: None
        vendor._window = None
        BUYBACK_QUEUE.clear()
        vendor.player_inv.add_item("gold", 20)

        self.assertTrue(Vendor.buy_from_stock(vendor, "pine_log", 2, 3))
        self.assertEqual(vendor.player_inv.count_item("pine_log"), 3)
        self.assertEqual(vendor.player_inv.count_item("gold"), 14)

        self.assertTrue(Vendor.sell_item_by_id(vendor, "pine_log", 1, 2))
        self.assertEqual(vendor.player_inv.count_item("pine_log"), 1)
        self.assertEqual(vendor.player_inv.count_item("gold"), 16)
        self.assertEqual(BUYBACK_QUEUE[0]["item_id"], "pine_log")
        self.assertEqual(BUYBACK_QUEUE[0]["quantity"], 2)

        self.assertTrue(Vendor.buyback_item(vendor, 0, 1))
        self.assertEqual(vendor.player_inv.count_item("pine_log"), 2)
        self.assertEqual(vendor.player_inv.count_item("gold"), 15)

    def test_game_update_frame_updates_interactables_teleporters_and_resources(self):
        game = Game.__new__(Game)
        game._paused = False
        game.bullet_world = type("BulletWorldStub", (), {"doPhysics": lambda self, dt: None})()
        game.crafting_ui = type("CraftingUiStub", (), {"update": lambda self, dt: None, "is_open": lambda self: False})()
        game.player = type(
            "PlayerStub",
            (),
            {
                "get_pos": lambda self: Vec3(1, 2, 3),
                "get_heading": lambda self: 0,
                "is_advancing": lambda self: False,
                "is_moving": lambda self: False,
                "is_turning": lambda self: False,
                "update_projectiles": lambda self, dt, hud: None,
                "get_health_display": lambda self: 10,
                "max_health": 10,
                "dead": False,
            },
        )()
        game.cam_controller = type("CameraStub", (), {"update": lambda self, *args: None, "set_ui_open": lambda self, value: None})()
        game.combat_manager = type("CombatStub", (), {"update": lambda self, dt: None})()
        game.selection_manager = type("SelectionStub", (), {"update": lambda self: None, "selected_target": None})()
        game.hud = type(
            "HudStub",
            (),
            {
                "refresh_health": lambda self, a, b: None,
                "refresh_player_level": lambda self, level: None,
                "clear_target": lambda self: None,
                "clear_range_indicators": lambda self: None,
                "refresh_combat_debug": lambda self, player, target: None,
                "clear_death": lambda self: None,
            },
        )()
        game.skills = type("SkillsStub", (), {"get_combat_level": lambda self: 1})()
        game._update_benchmark = lambda: None
        game._sync_camera_ui_state = lambda: None
        game._was_player_dead = False
        game._respawn_timer = 0.0
        teleporter = _DummyLevelObject()
        interactable = _DummyLevelObject()
        resource = _DummyLevelObject()
        active_level = type("LevelStub", (), {"teleporters": [teleporter], "interactables": [interactable], "resources": [resource]})()
        game.level_manager = type("LevelManagerStub", (), {"get_active_level": lambda self: active_level})()

        Game.update_frame(game, 0.16)

        self.assertEqual(len(teleporter.calls), 1)
        self.assertEqual(len(interactable.calls), 1)
        self.assertEqual(interactable.calls[0][0], 0.16)
        self.assertEqual(interactable.calls[0][1], Vec3(1, 2, 3))
        self.assertEqual(len(resource.calls), 1)


if __name__ == "__main__":
    unittest.main()
