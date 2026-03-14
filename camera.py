"""
camera.py — Third-person orbit camera with mouse look.
"""

import builtins
from panda3d.core import Vec3, NodePath, WindowProperties


PITCH_MIN = -20.0
PITCH_MAX = 70.0
MOUSE_SENSITIVITY = 0.2   # degrees per pixel
CAM_DISTANCE = 15.0
CAM_HEIGHT = 5.0


class CameraController:
    def __init__(self, cam, player):
        self.cam = cam
        self.player = player
        self._ui_open = False

        app = builtins.base
        app.disableMouse()

        # Pivot sits at player position; camera is a child of pivot
        self.pivot = NodePath("cam_pivot")
        self.pivot.reparentTo(app.render)
        self.pivot.setPos(0, 0, 2)

        self.cam.reparentTo(self.pivot)
        self.cam.setPos(0, -CAM_DISTANCE, CAM_HEIGHT)
        self.cam.lookAt(self.pivot)

        self._heading = 0.0   # degrees
        self._pitch = 20.0    # degrees

        self._win = app.win
        self._mouse_watcher = app.mouseWatcherNode

        # Track last pixel position for delta
        props = self._win.getProperties()
        self._cx = props.getXSize() // 2
        self._cy = props.getYSize() // 2
        self._win.movePointer(0, self._cx, self._cy)
        self._last_x = self._cx
        self._last_y = self._cy
        self._skip_frame = False

    def set_ui_open(self, open_state):
        """Call with True when any UI opens, False when it closes."""
        if open_state == self._ui_open:
            return  # no change — don't re-trigger recenter/skip
        self._ui_open = open_state
        props = WindowProperties()
        if open_state:
            props.setCursorHidden(False)
            self._win.requestProperties(props)
        else:
            props.setCursorHidden(True)
            self._win.requestProperties(props)
            # Re-center and skip one frame so the large delta isn't applied
            self._recenter()
            self._skip_frame = True

    def _recenter(self):
        props = self._win.getProperties()
        cx = props.getXSize() // 2
        cy = props.getYSize() // 2
        self._win.movePointer(0, cx, cy)

    def update(self, player_pos):
        if not self._ui_open:
            if self._skip_frame:
                # Skip one frame after UI close to discard the large re-center delta
                self._skip_frame = False
                self._recenter()
            elif self._mouse_watcher.hasMouse():
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

        # Apply to pivot
        self.pivot.setPos(player_pos.x, player_pos.y, player_pos.z + 2)
        self.pivot.setHpr(self._heading, -self._pitch, 0)

    def get_heading(self):
        return self._heading
