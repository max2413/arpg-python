"""Game runtime entrypoint and top-level wiring."""

from ursina import Entity, Text, Ursina, camera, color, destroy, scene
from panda3d.bullet import BulletWorld, BulletDebugNode
from panda3d.core import (
    Vec3,
    WindowProperties,
)

from game.core.camera import CameraController
from game.core.selection import SelectionManager
from game.entities.player import Player
from game.systems.combat_manager import CombatManager
from game.systems.inventory import Inventory
from game.systems.skills import Skills
from game.systems.persistence import save_game, load_game
from game.systems.quests import QuestManager, create_tutorial_quest
from game.ui.hud import HUD
from game.ui.dev_menu import DevMenu
from game.ui.crafting_ui import CraftingUI
from game.ui.ursina_widgets import FlatButton
from game.services.crafting import load_recipes
from game.runtime import RuntimeContext, RuntimeDriver, configure_scene_lighting, set_runtime
from game.world.levels import LevelManager

RESPAWN_DELAY = 3.0
PLAYER_TEST_DROP_HEIGHT = 14.0


class Game:
    def __init__(self):
        self.app = Ursina()
        self._render_root = Entity(parent=scene)
        world_seed = 42

        props = WindowProperties()
        props.setTitle("ARPG Prototype")
        self.app.win.requestProperties(props)
        self._loading_ui = None
        self._loading_status = None
        self._show_loading_screen()
        self._update_loading_screen("Bootstrapping runtime")

        self._paused = False
        self._pause_ui = None
        self._respawn_timer = 0.0
        self._was_player_dead = False
        # URSINA Y-UP: Spawn high up on Y
        self._spawn_point = Vec3(0, PLAYER_TEST_DROP_HEIGHT, 0)
        self._collision_debug_enabled = False
        self._collision_debug_np = None
        self._benchmark_target = None
        self._benchmark_started = None

        self.bullet_world = BulletWorld()
        self.bullet_world.setGravity(Vec3(0, -25, 0))
        self._setup_collision_debug()
        self._update_loading_screen("Preparing systems")

        self.runtime = RuntimeContext(self.app, self, self.bullet_world)
        set_runtime(self.runtime)

        self.inventory = Inventory(size=28)
        self.skills = Skills()
        self.app.quest_manager = QuestManager(self)
        self.quest_manager = self.app.quest_manager
        load_game(self.inventory, self.skills, self.app.quest_manager)
        self._update_loading_screen("Configuring scene")

        self._setup_lighting()

        self.player = Player(self.render, self.bullet_world, self.inventory, terrain=None)
        self.player._app = self
        self.player.stats.skills = self.skills
        self.player.stats.recalculate()
        self.cam_controller = CameraController(self.cam, self.player, self.bullet_world)
        load_recipes()
        self.hud = HUD(self.inventory, self.skills, player=self.player, app=self.app)
        self.hud.refresh_health(self.player.get_health_display(), self.player.max_health)
        self._update_loading_screen("Building interface")
        
        self.selection_manager = SelectionManager(self)
        self.combat_manager = CombatManager(self)

        # Keep compatibility access on the Ursina app while gameplay moves to runtime services.
        self.app.player = self.player
        self.app.hud = self.hud
        self.app.selection_manager = self.selection_manager
        self.app.game = self

        if not self.app.quest_manager.active_quests and not self.app.quest_manager.completed_ids:
            self.app.quest_manager.start_quest(create_tutorial_quest())

        self.crafting_ui = CraftingUI(self)
        self._update_loading_screen("Generating world")
        self.level_manager = LevelManager(self.render, self.bullet_world, self.inventory, seed=world_seed)
        self._load_level("overworld", "default")
        self._update_loading_screen("Preparing developer tools")
        self.dev_menu = DevMenu(self)

        self.runtime.player = self.player
        self.runtime.hud = self.hud
        self.runtime.crafting_ui = self.crafting_ui
        self.runtime.quest_manager = self.quest_manager

        self.app.accept("f1", self._toggle_dev_menu)
        self._driver = RuntimeDriver(self.update_frame, self.handle_input)
        self._update_loading_screen("Ready")
        self._hide_loading_screen()

    def _toggle_dev_menu(self):
        self.dev_menu.toggle()

    def _show_loading_screen(self):
        self._loading_ui = Entity(parent=camera.ui, z=-5)
        Entity(parent=self._loading_ui, model="quad", color=color.rgba32(12, 16, 24, 255), scale=(2.2, 1.3), z=0)
        Entity(parent=self._loading_ui, model="quad", color=color.rgba32(28, 38, 54, 255), scale=(0.66, 0.28), z=-0.01)
        Text(parent=self._loading_ui, text="ARPG Prototype", origin=(0, 0), position=(0, 0.08, -0.02), scale=2.0, color=color.rgba32(235, 242, 255))
        self._loading_status = Text(
            parent=self._loading_ui,
            text="Loading...",
            origin=(0, 0),
            position=(0, -0.02, -0.02),
            scale=1.1,
            color=color.rgba32(255, 220, 90),
        )
        self._flush_loading_frame()

    def _update_loading_screen(self, message):
        if self._loading_status is None:
            return
        self._loading_status.text = message
        self._flush_loading_frame()

    def _hide_loading_screen(self):
        if self._loading_ui is not None:
            destroy(self._loading_ui)
            self._loading_ui = None
            self._loading_status = None
            self._flush_loading_frame()

    def _flush_loading_frame(self):
        try:
            self.app.step()
        except Exception:
            pass

    def _setup_lighting(self):
        lighting = configure_scene_lighting()
        self._sky = lighting["sky"]
        self._ambient = lighting["ambient"]
        self._sun = lighting["sun"]
        self._fill = lighting["fill"]
        
    def _setup_collision_debug(self):
        debug_node = BulletDebugNode("bullet_debug")
        debug_node.showWireframe(True)
        debug_node.showConstraints(True)
        debug_node.showBoundingBoxes(False)
        debug_node.showNormals(False)
        self._collision_debug_np = self.render.attachNewNode(debug_node)
        self._collision_debug_np.hide()
        self.bullet_world.setDebugNode(debug_node)

    def _toggle_collision_debug(self):
        self._collision_debug_enabled = not self._collision_debug_enabled
        if self._collision_debug_enabled:
            self._collision_debug_np.show()
            if hasattr(self, "hud"):
                self.hud.show_prompt("Collision debug: ON")
        else:
            self._collision_debug_np.hide()
            if hasattr(self, "hud"):
                self.hud.show_prompt("Collision debug: OFF")

    @property
    def render(self):
        return self._render_root

    @property
    def cam(self):
        return self.app.cam

    @property
    def _active_level(self):
        return self.level_manager.get_active_level()

    def _level_interactables(self):
        return self._active_level.interactables if self._active_level is not None else []

    def _level_ui_interactables(self):
        return [obj for obj in self._level_interactables() if hasattr(obj, "ui_open")]

    def _any_ui_open(self):
        return self._modal_ui_open() or self.hud.is_any_window_open()

    def _modal_ui_open(self):
        crafting_open = bool(self.crafting_ui.is_open()) if hasattr(self, "crafting_ui") else False
        return any(obj.ui_open for obj in self._level_ui_interactables()) or crafting_open or self._paused

    def _open_ui(self, ui_obj):
        ui_obj.open_ui()
        self.cam_controller.set_ui_open(True)

    def _sync_camera_ui_state(self):
        self.cam_controller.set_ui_open(self._modal_ui_open())

    def _open_pause(self):
        self._paused = True
        self.cam_controller.set_ui_open(True)

        self._pause_ui = Entity(parent=camera.ui)
        Entity(parent=self._pause_ui, model="quad", color=color.rgba(0, 0, 0, 180), scale=(2, 2), z=1)
        panel = Entity(parent=self._pause_ui, model="quad", color=color.rgba(18, 20, 24, 242), scale=(0.34, 0.40), z=0)
        Text(parent=panel, text="Paused", origin=(0, 0), position=(0, 0.36, -0.02), scale=2.0, color=color.white)
        for idx, (label, callback, tint) in enumerate([
            ("Resume", self._close_pause, color.rgba32(56, 132, 72)),
            ("Save Game", self._save_current_game, color.rgba32(56, 92, 138)),
            ("Regenerate World", self._regenerate_overworld, color.rgba32(120, 92, 38)),
            ("Exit Game", self._exit_game, color.rgba32(156, 42, 42)),
        ]):
            FlatButton(
                parent=panel,
                text=label,
                scale=(0.78, 0.14),
                position=(0, 0.12 - idx * 0.18, -0.02),
                color_value=tint,
                highlight_color=tint.tint(.15),
                pressed_color=tint.tint(-.1),
                text_scale=1.2,
                on_click=callback,
            )

    def _save_current_game(self):
        save_game(self.inventory, self.skills, self.app.quest_manager)
        if hasattr(self, "hud"):
            self.hud.show_prompt("Game Saved")

    def _exit_game(self):
        self._save_current_game()
        self.app.userExit()

    def _close_pause(self):
        self._paused = False
        if self._pause_ui:
            destroy(self._pause_ui)
            self._pause_ui = None
        self._sync_camera_ui_state()

    def _close_level_ui(self):
        closed = False
        if hasattr(self, "crafting_ui") and self.crafting_ui.is_open():
            self.crafting_ui.hide()
            closed = True
        for obj in self._level_ui_interactables():
            if obj.ui_open:
                obj.close_ui()
                closed = True
        if closed:
            self._sync_camera_ui_state()
        return closed

    def _load_level(self, level_id, entry_key, force_regenerate=False):
        self.selection_manager.set_selected_target(None)
        self._benchmark_target = None
        self._benchmark_started = None
        self.player.clear_auto_attack()
        self.player._clear_projectiles()
        self._close_level_ui()
        spawn = self.level_manager.load_level(level_id, entry_key, hud=self.hud, force_regenerate=force_regenerate)
        self.player.terrain = self._active_level.world.terrain if self._active_level and self._active_level.world else None
        # spawn is (x, height, z) in our new mental model? 
        # LevelManager needs to return Y-up spawn.
        self._spawn_point = Vec3(*spawn)
        self.player.respawn((self._spawn_point.x, self._spawn_point.y, self._spawn_point.z))
        self.hud.clear_prompt()
        self.hud.clear_target()
        self.hud.clear_range_indicators()
        self._sync_camera_ui_state()

    def _regenerate_overworld(self):
        self.level_manager.clear_saved_overworld()
        self._close_pause()
        self._load_level("overworld", "default", force_regenerate=True)

    def start_benchmark(self, target, expected_level=None):
        self._benchmark_target = target
        from panda3d.core import ClockObject
        self._benchmark_started = ClockObject.get_global_clock().get_frame_time()
        target_level = target.get_level() if hasattr(target, "get_level") else expected_level
        self.hud.set_benchmark_summary(
            f"Benchmark active vs {target.get_target_name()} Lv {target_level}"
        )

    def _update_benchmark(self):
        if self._benchmark_target is None:
            return
        from panda3d.core import ClockObject
        now = ClockObject.get_global_clock().get_frame_time()
        if self._benchmark_started is None:
            self._benchmark_started = now
        elapsed = max(0.0, now - self._benchmark_started)
        if self.player.dead:
            name = self._benchmark_target.get_target_name() if self._benchmark_target is not None else "target"
            self.hud.set_benchmark_summary(f"Failed vs {name} after {elapsed:.1f}s")
            self._benchmark_target = None
            self._benchmark_started = None
            return
        if getattr(self._benchmark_target, "dead", False):
            self.hud.set_benchmark_summary(
                f"Victory vs {self._benchmark_target.get_target_name()} in {elapsed:.1f}s"
            )
            self._benchmark_target = None
            self._benchmark_started = None

    def _on_e_pressed(self):
        if self._paused or self.player.dead:
            return
        if self._close_level_ui():
            return
        for teleporter in self._active_level.teleporters:
            if teleporter.try_interact():
                self._load_level(teleporter.destination_level_id, teleporter.destination_entry_key)
                return
        for interactable in self._level_interactables():
            if getattr(interactable, "_in_range", False):
                self._open_ui(interactable)
                return
        for hostile in self._active_level.hostiles:
            if hostile.try_player_interact(self.player, self.inventory, self.hud):
                return
        for resource in self._active_level.resources:
            resource._on_e_pressed()

    def _on_mouse1(self):
        if self._paused or self.player.dead or self._any_ui_open():
            return
        self.selection_manager.pick_target()

    def _on_e_released(self):
        if self.player.dead:
            return
        for resource in self._active_level.resources:
            resource._on_e_released()

    def _on_escape(self):
        if self._close_level_ui():
            return
        if self._paused:
            self._close_pause()
            return
        self._open_pause()

    def _on_melee_ability(self):
        self.combat_manager.begin_auto_attack("melee", "Target too far for melee")

    def _on_ranged_ability(self):
        self.combat_manager.begin_auto_attack("ranged", "Target too far for ranged")

    def handle_input(self, key):
        key = key.lower()
        if key == "i":
            self.hud.toggle_inventory()
        elif key == "c":
            self.hud.toggle_equipment()
        elif key == "k":
            self.hud.toggle_skills()
        elif key == "l":
            self.hud.toggle_game_log()
        elif key == "j":
            self.hud.toggle_combat_log()
        elif key == "f4":
            self.hud.toggle_combat_debug()
        elif key == "escape":
            self._on_escape()
        elif key == "e":
            self._on_e_pressed()
        elif key == "e up":
            self._on_e_released()
        elif key == "left mouse down":
            self._on_mouse1()
        elif key == "tab":
            self.selection_manager.on_tab_target()
        elif key == "1":
            self._on_melee_ability()
        elif key == "2":
            self._on_ranged_ability()
        elif key == "f3":
            self._toggle_collision_debug()

    def update_frame(self, dt):
        if self._paused:
            return

        self.bullet_world.doPhysics(dt)

        self.crafting_ui.update(dt)
        player_pos = self.player.get_pos()
        for teleporter in self._active_level.teleporters:
            teleporter.update()
        for interactable in self._level_interactables():
            interactable.update(dt, player_pos, self.hud)
        for resource in self._active_level.resources:
            resource.update()
        self.cam_controller.update(
            dt,
            player_pos,
            self.player.get_heading(),
            self.player.is_advancing(),
            self.player.is_moving(),
            self.player.is_turning(),
        )

        self.combat_manager.update(dt)
        self.selection_manager.update()
        self._update_benchmark()

        self.player.update_projectiles(dt, self.hud)
        self.hud.refresh_health(self.player.get_health_display(), self.player.max_health)
        self.hud.refresh_player_level(self.skills.get_combat_level())

        target = self.selection_manager.selected_target
        if target is not None:
            distance = self.player.distance_to(target.get_target_point())
            self.hud.refresh_target(
                target.get_target_name(),
                target.health,
                target.max_health,
                target.get_level() if hasattr(target, "get_level") else None,
                self.skills.get_combat_level(),
                target_role=getattr(target, "role", "normal")
            )
            self.hud.refresh_range_indicators(
                distance <= self.player.melee_ability_range,
                distance <= self.player.ranged_ability_range,
            )
        else:
            self.hud.clear_target()
            self.hud.clear_range_indicators()

        self.hud.refresh_combat_debug(self.player, target)

        if self.player.dead:
            if not self._was_player_dead:
                self._respawn_timer = RESPAWN_DELAY
                self._was_player_dead = True
            self._respawn_timer = max(0.0, self._respawn_timer - dt)
            self.hud.show_death(self._respawn_timer)
            self.hud.show_prompt("You are dead")
            if self._respawn_timer <= 0.0:
                self.player.respawn((self._spawn_point.x, self._spawn_point.y, self._spawn_point.z))
                self.hud.refresh_health(self.player.get_health_display(), self.player.max_health)
                self.hud.clear_death()
                self.hud.clear_prompt_if("You are dead")
                self._was_player_dead = False
        else:
            self._respawn_timer = 0.0
            self._was_player_dead = False
            self.hud.clear_death()

        self._sync_camera_ui_state()


def main():
    game = Game()
    game.app.run()
