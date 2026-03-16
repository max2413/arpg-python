"""
selection.py - Handles target picking and targeting logic.
"""

import math
from panda3d.core import Point2, Point3, Vec3

class SelectionManager:
    def __init__(self, app):
        self.app = app
        self.selected_target = None
        self.tab_target_range = 96.0
        self.tab_target_min_dot = 0.45

    def set_selected_target(self, target):
        if self.selected_target is target:
            return
        
        if self.selected_target is not None:
            self.selected_target.set_targeted(False)
            
        self.selected_target = target
        
        if self.selected_target is not None:
            self.selected_target.set_targeted(True)
            self.app.hud.show_prompt(f"Targeted {self.selected_target.get_target_name()}")
        else:
            self.app.player.clear_auto_attack()
            self.app.hud.clear_target()

    def pick_target(self):
        if not self.app.mouseWatcherNode.hasMouse():
            return

        mouse = self.app.mouseWatcherNode.getMouse()
        best = None
        best_score = None
        screen_pt = Point2()

        active_level = self.app._active_level
        if not active_level:
            return

        for hostile in active_level.hostiles:
            if not hostile.is_targetable():
                continue
            world_pt = hostile.get_target_point()
            camera_pt = self.app.cam.getRelativePoint(self.app.render, Point3(world_pt.x, world_pt.y, world_pt.z))
            if camera_pt.y <= 0:
                continue
            if not self.app.camLens.project(camera_pt, screen_pt):
                continue
            dx = screen_pt.x - mouse.x
            dy = screen_pt.y - mouse.y
            score = dx * dx + dy * dy
            if score > 0.03:
                continue
            if best_score is None or score < best_score:
                best = hostile
                best_score = score

        self.set_selected_target(best)

    def on_tab_target(self):
        player_pos = self.app.player.get_pos()
        heading_rad = math.radians(self.app.player.get_heading())
        forward = Vec3(-math.sin(heading_rad), math.cos(heading_rad), 0)
        best = None
        best_score = None

        active_level = self.app._active_level
        if not active_level:
            return

        for hostile in active_level.hostiles:
            if not hostile.is_targetable():
                continue
            to_target = hostile.get_target_point() - player_pos
            to_target.z = 0
            distance = to_target.length()
            if distance <= 0.001 or distance > self.tab_target_range:
                continue
            to_target.normalize()
            dot = forward.dot(to_target)
            if dot < self.tab_target_min_dot:
                continue
            score = dot * 100.0 - distance
            if best_score is None or score > best_score:
                best = hostile
                best_score = score

        if best is not None:
            self.set_selected_target(best)
        else:
            self.app.hud.show_prompt("No enemy in front")

    def update(self):
        if self.selected_target is not None and not self.selected_target.is_targetable():
            self.set_selected_target(None)
