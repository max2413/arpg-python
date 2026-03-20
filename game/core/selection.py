"""
selection.py - Handles target picking and targeting logic.
URSINA Y-UP VERSION
"""

import math
from panda3d.core import Point2, Point3, Vec3

from game.runtime import get_runtime

class SelectionManager:
    def __init__(self, app):
        self.app = app
        self.selected_target = None
        self.tab_target_range = 96.0
        self.tab_target_min_dot = 0.45
        self.click_target_radius = 0.08

    def set_selected_target(self, target):
        if self.selected_target is target: return
        if self.selected_target: self.selected_target.set_targeted(False)
        self.selected_target = target
        if self.selected_target:
            self.selected_target.set_targeted(True)
            self.app.hud.show_prompt(f"Targeted {self.selected_target.get_target_name()}")
        else:
            self.app.player.clear_auto_attack()
            self.app.hud.clear_target()

    def pick_target(self):
        runtime = get_runtime()
        if runtime is None or not runtime.input_state.has_mouse():
            return
        mouse = runtime.input_state.mouse_position()
        best, best_score = None, None
        screen_pt = Point2()
        active = self.app._active_level
        if not active: return

        for h in active.hostiles:
            if not h.is_targetable(): continue
            world_pt = h.get_target_point()
            # Relative to camera (Panda3D native coords: Y is depth)
            camera_pt = self.app.cam.getRelativePoint(self.app.render, Point3(world_pt.x, world_pt.y, world_pt.z))
            if camera_pt.y <= 0: continue
            if not self.app.app.camLens.project(camera_pt, screen_pt): continue
            score = (screen_pt.x - mouse.x)**2 + (screen_pt.y - mouse.y)**2
            if score > self.click_target_radius: continue
            if best_score is None or score < best_score:
                best, best_score = h, score
        self.set_selected_target(best)

    def on_tab_target(self):
        player_pos = self.app.player.get_pos()
        h_rad = math.radians(self.app.player.get_heading())
        # URSINA Y-UP: Forward on XZ plane
        forward = Vec3(math.sin(h_rad), 0, math.cos(h_rad))
        best, best_score = None, None
        active = self.app._active_level
        if not active: return

        for h in active.hostiles:
            if not h.is_targetable(): continue
            to_t = h.get_target_point() - player_pos
            to_t.y = 0
            dist = to_t.length()
            if dist <= 0.001 or dist > self.tab_target_range: continue
            to_t.normalize()
            dot = forward.dot(to_t)
            if dot < self.tab_target_min_dot: continue
            score = dot * 100.0 - dist
            if best_score is None or score > best_score:
                best, best_score = h, score
        if best: self.set_selected_target(best)
        else: self.app.hud.show_prompt("No enemy in front")

    def update(self):
        if self.selected_target and not self.selected_target.is_targetable():
            self.set_selected_target(None)
