"""Third-person follow camera with optional right-click free look."""

from panda3d.core import Point3, Vec3, NodePath, WindowProperties

from game.runtime import get_runtime
PITCH_MIN = -20.0
PITCH_MAX = 70.0
MOUSE_SENSITIVITY = 0.2
CAM_DISTANCE = 20.0
CAM_HEIGHT = 5.0
CAM_ADVANCE_SNAP_SPEED = 720.0
CAM_TURN_FOLLOW_SPEED = 540.0
CAM_MOVE_FOLLOW_SPEED = 480.0
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
        runtime = get_runtime()
        app = runtime.app if runtime is not None else None
        if app is not None:
            app.disableMouse()

        self.pivot = NodePath("cam_pivot")
        if runtime is not None:
            self.pivot.reparentTo(runtime.scene)
        self.pivot.setPos(0, 2, 0)

        self.cam.reparentTo(self.pivot)
        self.cam.setPos(0, CAM_HEIGHT, -CAM_DISTANCE)
        self.cam.lookAt(self.pivot)

        self._heading = 0.0
        self._pitch = 0.0

        self._win = app.win if app is not None else None
        self._mouse_watcher = app.mouseWatcherNode if app is not None else None
        self._skip_frame = False
        if self._win is not None:
            self._set_cursor_hidden(False)

    def set_ui_open(self, open_state):
        if open_state == self._ui_open: return
        self._ui_open = open_state
        self._set_cursor_hidden(False)
        if open_state: self._free_look = False

    def _recenter(self):
        if self._win is None:
            return
        props = self._win.getProperties()
        self._win.movePointer(0, props.getXSize() // 2, props.getYSize() // 2)

    def _set_cursor_hidden(self, hidden):
        if self._win is None:
            return
        props = WindowProperties()
        props.setCursorHidden(hidden)
        self._win.requestProperties(props)

    def _set_free_look(self, enabled):
        if self._ui_open: self._free_look = False; self._set_cursor_hidden(False); return
        self._free_look = enabled; self._set_cursor_hidden(enabled)
        if enabled: self._recenter(); self._skip_frame = True

    def update(self, dt, player_pos, player_heading, player_advancing, player_moving, player_turning):
        runtime = get_runtime()
        if runtime is not None:
            desired = runtime.input_state.is_held("right mouse")
            if desired != self._free_look:
                self._set_free_look(desired)

        if self._mouse_watcher is not None and not self._ui_open and self._free_look and self._mouse_watcher.hasMouse():
            if self._skip_frame: self._skip_frame = False; self._recenter()
            else:
                props = self._win.getProperties(); cx, cy = props.getXSize() // 2, props.getYSize() // 2
                ptr = self._win.getPointer(0)
                dx, dy = ptr.getX() - cx, ptr.getY() - cy
                
                # Mouse moves camera heading (CCW)
                self._heading -= dx * MOUSE_SENSITIVITY
                self._pitch -= dy * MOUSE_SENSITIVITY
                self._pitch = max(PITCH_MIN, min(PITCH_MAX, self._pitch))
                self._recenter()
        else:
            # Automatic follow logic
            follow_spd = 0.0
            if player_advancing: follow_spd = CAM_ADVANCE_SNAP_SPEED
            elif player_turning: follow_spd = CAM_TURN_FOLLOW_SPEED
            elif player_moving: follow_spd = CAM_MOVE_FOLLOW_SPEED
            
            if follow_spd > 0.0:
                self._heading = self._approach_angle(self._heading, -player_heading, follow_spd * dt)

        # Apply to pivot (Y-up)
        self.pivot.setPos(player_pos.x, player_pos.y + 2, player_pos.z)
        self.pivot.setHpr(self._heading, -self._pitch, 0)
        self._update_camera_obstruction(dt)

    def get_heading(self): return self._heading

    def _update_camera_obstruction(self, dt):
        ideal_local = Vec3(0, CAM_HEIGHT, -CAM_DISTANCE)
        parent = self.pivot.getParent()
        ideal_world = self.pivot.getPos(parent) + self.pivot.getQuat(parent).xform(ideal_local)
        pivot_world = self.pivot.getPos(parent)
        ray_start = Point3(pivot_world.x, pivot_world.y + 0.35, pivot_world.z)
        ray_end = Point3(ideal_world.x, ideal_world.y, ideal_world.z)

        hit_dist = None
        res = self.bullet_world.rayTestClosest(ray_start, ray_end)
        if res.hasHit():
            node = res.getNode()
            if node != self.player.char_node and "ghost" not in node.getName().lower():
                hit_pos = res.getHitPos()
                hit_vec = hit_pos - ray_start
                hit_dist = max(CAM_MIN_DISTANCE, hit_vec.length() - CAM_COLLISION_PADDING)
                hit_dist = min(CAM_DISTANCE, hit_dist)

        target_dist = CAM_DISTANCE if hit_dist is None else hit_dist
        if target_dist < self._current_distance: self._current_distance = target_dist
        else: self._current_distance = min(target_dist, self._current_distance + CAM_DISTANCE_RETURN_SPEED * dt)

        self.cam.setPos(0, CAM_HEIGHT, -self._current_distance)
        self.cam.lookAt(self.pivot)

    def _approach_angle(self, current, target, step):
        delta = (target - current + 180.0) % 360.0 - 180.0
        return current + max(-step, min(step, delta))
