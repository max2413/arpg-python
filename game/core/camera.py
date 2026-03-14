"""
camera.py — Third-person follow camera with optional right-click free look.
"""

import builtins
from panda3d.core import Vec3, NodePath, WindowProperties


PITCH_MIN = -20.0
PITCH_MAX = 70.0
MOUSE_SENSITIVITY = 0.2   # degrees per pixel
CAM_DISTANCE = 20.0
CAM_HEIGHT = 5.0
CAM_ADVANCE_SNAP_SPEED = 720.0
CAM_TURN_FOLLOW_SPEED = 360.0
CAM_MOVE_FOLLOW_SPEED = 240.0


class CameraController:
    def __init__(self, cam, player):
        self.cam = cam
        self.player = player
        self._ui_open = False
        self._free_look = False

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
        if not self._ui_open:
            if self._free_look and not player_moving and not player_turning and self._mouse_watcher.hasMouse():
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

    def get_heading(self):
        return self._heading

    def _approach_angle(self, current, target, step):
        delta = (target - current + 180.0) % 360.0 - 180.0
        delta = max(-step, min(step, delta))
        return current + delta
