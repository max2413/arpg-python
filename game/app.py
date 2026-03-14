"""Game runtime entrypoint and top-level wiring."""

from direct.showbase.ShowBase import ShowBase
from direct.gui.DirectGui import DirectFrame, DirectButton, OnscreenText
from panda3d.bullet import BulletWorld
from panda3d.core import Point2, Point3, TextNode, Vec3, WindowProperties

from game.core.camera import CameraController
from game.entities.player import Player
from game.services.bank import Bank
from game.services.vendor import Vendor
from game.systems.inventory import Inventory
from game.ui.hud import HUD
from game.world.world import World
from game.world.worldgen import generate_world

RESPAWN_DELAY = 3.0


class Game(ShowBase):
    def __init__(self):
        super().__init__()

        props = WindowProperties()
        props.setTitle("ARPG Prototype")
        self.win.requestProperties(props)

        self._paused = False
        self._pause_ui = None
        self._respawn_timer = 0.0
        self._was_player_dead = False
        self._selected_target = None

        self.bullet_world = BulletWorld()
        self.bullet_world.setGravity(Vec3(0, 0, -25))

        self.inventory = Inventory(size=28)
        self.world = World(self.render, self.bullet_world)
        self.player = Player(self.render, self.bullet_world, self.inventory)
        self.cam_controller = CameraController(self.cam, self.player)
        self.hud = HUD(self.inventory)
        self.hud.refresh_health(self.player.get_health_display(), self.player.max_health)

        self.resources, self.hostiles = generate_world(self.render, self.bullet_world, seed=42)
        self.bank = Bank(self.render, self.bullet_world, (20, 0, 0), self.inventory)
        self.vendor = Vendor(self.render, self.bullet_world, (-20, 0, 0), self.inventory)

        self.accept("i", self.hud.toggle_inventory)
        self.accept("k", self.hud.toggle_skills)
        self.accept("escape", self._on_escape)
        self.accept("e", self._on_e_pressed)
        self.accept("e-up", self._on_e_released)
        self.accept("mouse1", self._on_mouse1)
        self.accept("1", self._on_melee_ability)
        self.accept("2", self._on_ranged_ability)

        self.taskMgr.add(self.update, "game_update")

    def _any_ui_open(self):
        return self.bank.ui_open or self.vendor.ui_open or self._paused

    def _open_ui(self, ui_obj):
        ui_obj.open_ui()
        self.cam_controller.set_ui_open(True)

    def _sync_camera_ui_state(self):
        self.cam_controller.set_ui_open(self._any_ui_open())

    def _open_pause(self):
        self._paused = True
        self.cam_controller.set_ui_open(True)

        self._pause_ui = DirectFrame(
            frameColor=(0, 0, 0, 0.7),
            frameSize=(-0.5, 0.5, -0.35, 0.35),
            pos=(0, 0, 0),
        )
        OnscreenText(
            text="Paused",
            parent=self._pause_ui,
            pos=(0, 0.22),
            scale=0.08,
            fg=(1, 1, 1, 1),
            align=TextNode.ACenter,
        )
        DirectButton(
            parent=self._pause_ui,
            text="Resume",
            scale=0.06,
            pos=(0, 0, 0.05),
            command=self._close_pause,
            frameColor=(0.2, 0.5, 0.2, 1),
            text_fg=(1, 1, 1, 1),
        )
        DirectButton(
            parent=self._pause_ui,
            text="Exit Game",
            scale=0.06,
            pos=(0, 0, -0.12),
            command=self.userExit,
            frameColor=(0.6, 0.1, 0.1, 1),
            text_fg=(1, 1, 1, 1),
        )

    def _close_pause(self):
        self._paused = False
        if self._pause_ui:
            self._pause_ui.destroy()
            self._pause_ui = None
        self._sync_camera_ui_state()

    def _on_e_pressed(self):
        if self._paused or self.player.dead:
            return
        if self.bank.ui_open:
            self.bank.close_ui()
            self._sync_camera_ui_state()
            return
        if self.vendor.ui_open:
            self.vendor.close_ui()
            self._sync_camera_ui_state()
            return
        if self.bank._in_range:
            self._open_ui(self.bank)
            return
        if self.vendor._in_range:
            self._open_ui(self.vendor)
            return
        for hostile in self.hostiles:
            if hostile.try_player_interact(self.player, self.inventory, self.hud):
                return
        for resource in self.resources:
            resource._on_e_pressed()

    def _on_mouse1(self):
        if self._paused or self.player.dead or self._any_ui_open():
            return
        self._pick_target()

    def _on_e_released(self):
        if self.player.dead:
            return
        for resource in self.resources:
            resource._on_e_released()

    def _on_escape(self):
        if self.bank.ui_open:
            self.bank.close_ui()
            self._sync_camera_ui_state()
            return
        if self.vendor.ui_open:
            self.vendor.close_ui()
            self._sync_camera_ui_state()
            return
        if self._paused:
            self._close_pause()
            return
        self._open_pause()

    def _on_melee_ability(self):
        self._use_targeted_ability(
            self.player.melee_ability_range,
            self.player.melee_ability_damage,
            "Target too far for melee",
            projectile=False,
        )

    def _on_ranged_ability(self):
        self._use_targeted_ability(
            self.player.ranged_ability_range,
            self.player.ranged_ability_damage,
            "Target too far for ranged",
            projectile=True,
        )

    def _use_targeted_ability(self, max_range, damage, fail_msg, projectile):
        if self._paused or self.player.dead:
            return
        target = self._selected_target
        if target is None or not target.is_targetable():
            self.hud.show_prompt("No target selected")
            return

        distance = self.player.distance_to(target.get_target_point())
        if distance > max_range:
            self.hud.show_prompt(fail_msg)
            return

        self.player.face_target(target.get_target_point())
        if projectile:
            self.player.fire_target_projectile(target, damage)
        else:
            target.take_damage(damage, self.hud)

    def _set_selected_target(self, hostile):
        if self._selected_target is hostile:
            return
        if self._selected_target is not None:
            self._selected_target.set_targeted(False)
        self._selected_target = hostile
        if self._selected_target is not None:
            self._selected_target.set_targeted(True)
            self.hud.show_prompt(f"Targeted {self._selected_target.get_target_name()}")
        else:
            self.hud.clear_target()

    def _pick_target(self):
        if not self.mouseWatcherNode.hasMouse():
            return

        mouse = self.mouseWatcherNode.getMouse()
        best = None
        best_score = None
        screen_pt = Point2()

        for hostile in self.hostiles:
            if not hostile.is_targetable():
                continue
            world_pt = hostile.get_target_point()
            camera_pt = self.cam.getRelativePoint(self.render, Point3(world_pt.x, world_pt.y, world_pt.z))
            if camera_pt.y <= 0:
                continue
            if not self.camLens.project(camera_pt, screen_pt):
                continue
            dx = screen_pt.x - mouse.x
            dy = screen_pt.y - mouse.y
            score = dx * dx + dy * dy
            if score > 0.03:
                continue
            if best_score is None or score < best_score:
                best = hostile
                best_score = score

        self._set_selected_target(best)

    def update(self, task):
        if self._paused:
            return task.cont

        dt = globalClock.getDt()  # noqa: F821 - Panda3D global
        dt = min(dt, 0.05)

        self.bullet_world.doPhysics(dt)

        self.player.update(dt, self.cam_controller.pivot)
        player_pos = self.player.get_pos()
        self.cam_controller.update(
            dt,
            player_pos,
            self.player.char_np.getH(),
            self.player.is_advancing(),
            self.player.is_moving(),
        )

        for resource in self.resources:
            resource.update(dt, player_pos, self.player, self.inventory, self.hud)

        self.bank.update(dt, player_pos, self.hud)
        self.vendor.update(dt, player_pos, self.hud)
        for hostile in self.hostiles:
            hostile.update(dt, self.player, self.hud)
        self.player.update_projectiles(dt, self.hud)
        self.hud.refresh_health(self.player.get_health_display(), self.player.max_health)

        if self._selected_target is not None and not self._selected_target.is_targetable():
            self._set_selected_target(None)
        elif self._selected_target is not None:
            distance = self.player.distance_to(self._selected_target.get_target_point())
            self.hud.refresh_target(
                self._selected_target.get_target_name(),
                self._selected_target.health,
                self._selected_target.max_health,
            )
            self.hud.refresh_range_indicators(
                distance <= self.player.melee_ability_range,
                distance <= self.player.ranged_ability_range,
            )
        else:
            self.hud.clear_target()
            self.hud.clear_range_indicators()

        if self.player.dead:
            if not self._was_player_dead:
                self._respawn_timer = RESPAWN_DELAY
                self._was_player_dead = True
            self._respawn_timer = max(0.0, self._respawn_timer - dt)
            self.hud.show_death(self._respawn_timer)
            self.hud.show_prompt("You are dead")
            if self._respawn_timer <= 0.0:
                self.player.respawn((0, 0, 0))
                self.hud.refresh_health(self.player.get_health_display(), self.player.max_health)
                self.hud.clear_death()
                self.hud.clear_prompt_if("You are dead")
                self._was_player_dead = False
        else:
            self._respawn_timer = 0.0
            self._was_player_dead = False
            self.hud.clear_death()

        self._sync_camera_ui_state()
        return task.cont


def main():
    game = Game()
    game.run()
