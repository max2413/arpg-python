"""
camera.py — Third-person follow camera with optional right-click free look.
"""

import builtins
from panda3d.core import Point3, Vec3, NodePath, WindowProperties


PITCH_MIN = -20.0
PITCH_MAX = 70.0
MOUSE_SENSITIVITY = 0.2   # degrees per pixel
CAM_DISTANCE = 20.0
CAM_HEIGHT = 5.0
CAM_ADVANCE_SNAP_SPEED = 720.0
CAM_TURN_FOLLOW_SPEED = 360.0
CAM_MOVE_FOLLOW_SPEED = 240.0
CAM_COLLISION_PADDING = 0.6
CAM_MIN_DISTANCE = 4.0
CAM_DISTANCE_RETURN_SPEED = 18.0


class CameraController:
    def __init__(self, cam, player, bullet_world):
        self.cam = cam
        self.player = player
        self.bullet_world = bullet_world
        self._ui_open = False
        self._free_look = False
        self._current_distance = CAM_DISTANCE

        app = builtins.base
        app.disableMouse()
        app.accept("mouse3", self._set_free_look, [True])
        app.accept("mouse3-up", self._set_free_look, [False])

        # Pivot sits at player position; camera is a child of pivot
        self.pivot = NodePath("cam_pivot")
        self.pivot.reparentTo(app.render)
        self.pivot.setPos(0, 0, 2)

        self.cam.reparentTo(self.pivot)
        self.cam.setPos(0, -CAM_DISTANCE, CAM_HEIGHT)
        self.cam.lookAt(self.pivot)

        self._heading = 0.0   # degrees
        self._pitch = 0.0    # degrees

        self._win = app.win
        self._mouse_watcher = app.mouseWatcherNode

        self._skip_frame = False
        self._set_cursor_hidden(False)

    def set_ui_open(self, open_state):
        """Call with True when any UI opens, False when it closes."""
        if open_state == self._ui_open:
            return  # no change — don't re-trigger recenter/skip
        self._ui_open = open_state
        if open_state:
            self._set_cursor_hidden(False)
            self._free_look = False
        else:
            self._set_cursor_hidden(False)

    def _recenter(self):
        props = self._win.getProperties()
        cx = props.getXSize() // 2
        cy = props.getYSize() // 2
        self._win.movePointer(0, cx, cy)

    def _set_cursor_hidden(self, hidden):
        props = WindowProperties()
        props.setCursorHidden(hidden)
        self._win.requestProperties(props)

    def _set_free_look(self, enabled):
        if self._ui_open:
            self._free_look = False
            self._set_cursor_hidden(False)
            return
        self._free_look = enabled
        self._set_cursor_hidden(enabled)
        if enabled:
            self._recenter()
            self._skip_frame = True

    def update(self, dt, player_pos, player_heading, player_advancing, player_moving, player_turning):
        if not self._ui_open and self._free_look and not player_moving and not player_turning and self._mouse_watcher.hasMouse():
            if self._skip_frame:
                self._skip_frame = False
                self._recenter()
            else:
                props = self._win.getProperties()
                cx = props.getXSize() // 2
                cy = props.getYSize() // 2

                ptr = self._win.getPointer(0)
                dx = ptr.getX() - cx
                dy = ptr.getY() - cy

                self._heading -= dx * MOUSE_SENSITIVITY
                self._pitch -= dy * MOUSE_SENSITIVITY
                self._pitch = max(PITCH_MIN, min(PITCH_MAX, self._pitch))

                self._recenter()
        else:
            follow_speed = 0.0
            if player_advancing:
                follow_speed = CAM_ADVANCE_SNAP_SPEED
            elif player_turning:
                follow_speed = CAM_TURN_FOLLOW_SPEED
            elif player_moving:
                follow_speed = CAM_MOVE_FOLLOW_SPEED

            if follow_speed > 0.0:
                self._heading = self._approach_angle(self._heading, player_heading, follow_speed * dt)

        # Apply to pivot
        self.pivot.setPos(player_pos.x, player_pos.y, player_pos.z + 2)
        self.pivot.setHpr(self._heading, -self._pitch, 0)
        self._update_camera_obstruction(dt)

    def get_heading(self):
        return self._heading

    def _update_camera_obstruction(self, dt):
        ideal_local = Vec3(0, -CAM_DISTANCE, CAM_HEIGHT)
        ideal_world = self.pivot.getPos(self.pivot.getParent()) + self.pivot.getQuat(self.pivot.getParent()).xform(ideal_local)
        pivot_world = self.pivot.getPos(self.pivot.getParent())
        ray_start = Point3(pivot_world.x, pivot_world.y, pivot_world.z + 0.35)
        ray_end = Point3(ideal_world.x, ideal_world.y, ideal_world.z)

        hit_distance = None
        result = self.bullet_world.rayTestClosest(ray_start, ray_end)
        if result.hasHit():
            hit_node = result.getNode()
            if hit_node != self.player.char_node and "ghost" not in hit_node.getName().lower():
                hit_pos = result.getHitPos()
                hit_vec = Vec3(hit_pos.x - ray_start.x, hit_pos.y - ray_start.y, hit_pos.z - ray_start.z)
                total_vec = Vec3(ray_end.x - ray_start.x, ray_end.y - ray_start.y, ray_end.z - ray_start.z)
                total_len = max(0.001, total_vec.length())
                hit_distance = max(CAM_MIN_DISTANCE, hit_vec.length() - CAM_COLLISION_PADDING)
                hit_distance = min(CAM_DISTANCE, hit_distance)

        target_distance = CAM_DISTANCE if hit_distance is None else hit_distance
        if target_distance < self._current_distance:
            self._current_distance = target_distance
        else:
            self._current_distance = min(
                target_distance,
                self._current_distance + CAM_DISTANCE_RETURN_SPEED * dt,
            )

        self.cam.setPos(0, -self._current_distance, CAM_HEIGHT)
        self.cam.lookAt(self.pivot)

    def _approach_angle(self, current, target, step):
        delta = (target - current + 180.0) % 360.0 - 180.0
        delta = max(-step, min(step, delta))
        return current + delta
