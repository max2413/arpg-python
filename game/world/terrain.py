"""Terrain sampling and biome queries for the procedural world."""

import math


def _smoothstep(edge0, edge1, value):
    if edge1 == edge0:
        return 1.0 if value >= edge1 else 0.0
    t = max(0.0, min(1.0, (value - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


class TerrainField:
    def __init__(self, world_half=500, seed=42):
        self.world_half = world_half
        self.seed = seed
        self.spawn_flat_radius = 95.0
        self.spawn_blend_radius = 150.0
        self.river_paths = []
        self.river_width = 0.0
        self.forest_patches = []
        self.ore_patches = []
        self._phase_a = (seed % 97) * 0.071
        self._phase_b = (seed % 53) * 0.053
        self._phase_c = (seed % 31) * 0.097

    def _patch_factor(self, patches, x, y):
        best = 0.0
        for cx, cy, radius in patches:
            dist = math.sqrt((x - cx) * (x - cx) + (y - cy) * (y - cy))
            if dist >= radius:
                continue
            t = 1.0 - dist / radius
            # Slightly exaggerated center with a reasonably quick boundary falloff.
            factor = t * t * (1.35 - 0.35 * t)
            if factor > best:
                best = factor
        return best

    def set_river_paths(self, river_paths, river_width):
        self.river_paths = [list(path) for path in river_paths]
        self.river_width = float(river_width)

    def set_forest_patches(self, forest_patches):
        self.forest_patches = list(forest_patches)

    def set_ore_patches(self, ore_patches):
        self.ore_patches = list(ore_patches)

    def _base_height(self, x, y):
        # Broad, low rolling hills. Keep amplitudes modest for readable gameplay.
        return (
            4.2 * math.sin(x * 0.0105 + self._phase_a) * math.cos(y * 0.0085 - self._phase_b) +
            2.3 * math.sin((x + y) * 0.012 + self._phase_c) +
            1.1 * math.cos(x * 0.020 - y * 0.016 + self._phase_b)
        )

    def _distance_to_paths(self, x, y):
        best_sq = None
        for path in self.river_paths:
            for px, py in path:
                dx = x - px
                dy = y - py
                dist_sq = dx * dx + dy * dy
                if best_sq is None or dist_sq < best_sq:
                    best_sq = dist_sq
        if best_sq is None:
            return None
        return math.sqrt(best_sq)

    def forest_factor_at(self, x, y):
        if self.is_river(x, y, margin=2.0):
            return 0.0
        return self._patch_factor(self.forest_patches, x, y)

    def ore_factor_at(self, x, y):
        if self.is_river(x, y, margin=1.0):
            return 0.0
        return self._patch_factor(self.ore_patches, x, y)

    def is_river(self, x, y, margin=0.0):
        if not self.river_paths:
            return False
        distance = self._distance_to_paths(x, y)
        if distance is None:
            return False
        return distance <= (self.river_width + margin)

    def height_at(self, x, y):
        height = self._base_height(x, y)

        # Preserve a flatter play hub around origin where buildings and spawn sit.
        origin_dist = math.sqrt(x * x + y * y)
        hub_blend = _smoothstep(self.spawn_flat_radius, self.spawn_blend_radius, origin_dist)
        height *= hub_blend

        forest = self.forest_factor_at(x, y)
        ore = self.ore_factor_at(x, y)

        if forest > 0.0:
            # Forests feel like their own floor: flatter, slightly sunken, softer variation.
            forest_floor = height * (0.72 - 0.18 * forest) - 0.18 * forest
            height = height * (1.0 - forest * 0.8) + forest_floor * (forest * 0.8)

        if ore > 0.0:
            # Mining sites should read like worn exposed earth with a mild basin.
            ore_floor = height * (0.58 - 0.10 * ore) - 0.22 * ore
            height = height * (1.0 - ore * 0.85) + ore_floor * (ore * 0.85)

        # Carve a deeper river bed and keep the influence wide enough that the
        # banks taper cleanly back to the surrounding terrain instead of
        # pinching upward at the edge of the water.
        river_dist = self._distance_to_paths(x, y)
        if river_dist is not None:
            bed_inner = self.river_width * 0.35
            bed_outer = self.river_width * 1.05
            bank_outer = self.river_width + 18.0

            if river_dist <= bank_outer:
                if river_dist <= bed_inner:
                    carve = 5.5
                elif river_dist <= bed_outer:
                    t = _smoothstep(bed_inner, bed_outer, river_dist)
                    carve = 5.5 * (1.0 - t) + 2.0 * t
                else:
                    t = _smoothstep(bed_outer, bank_outer, river_dist)
                    carve = 2.0 * (1.0 - t)

                # Also damp the local hills near the river so the bank profile
                # transitions more evenly back into the terrain.
                if river_dist <= bed_outer:
                    hill_damp = 0.12
                else:
                    t = _smoothstep(bed_outer, bank_outer, river_dist)
                    hill_damp = 0.12 * (1.0 - t) + 1.0 * t
                height = height * hill_damp
                height -= carve

        return max(0.0, height)

    def normal_at(self, x, y, sample=2.0):
        hx0 = self.height_at(x - sample, y)
        hx1 = self.height_at(x + sample, y)
        hy0 = self.height_at(x, y - sample)
        hy1 = self.height_at(x, y + sample)
        nx = hx0 - hx1
        ny = hy0 - hy1
        nz = sample * 2.0
        length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        return (nx / length, ny / length, nz / length)

    def slope_at(self, x, y, sample=2.0):
        nx, ny, nz = self.normal_at(x, y, sample=sample)
        horizontal = math.sqrt(nx * nx + ny * ny)
        return horizontal / max(0.001, nz)

    def ground_color_at(self, x, y):
        forest = self.forest_factor_at(x, y)
        ore = self.ore_factor_at(x, y)
        height = self.height_at(x, y)
        if self.is_river(x, y, margin=-2.0):
            return (0.30, 0.38, 0.30, 1.0)
        if self.is_river(x, y, margin=10.0):
            return (0.44, 0.46, 0.30, 1.0)
        low = (0.48, 0.60, 0.33, 1.0)
        high = (0.58, 0.70, 0.42, 1.0)
        t = max(0.0, min(1.0, height / 8.0))
        base = tuple(low[i] * (1.0 - t) + high[i] * t for i in range(4))
        forest_tint = (0.16, 0.24, 0.12, 1.0)
        mix = min(0.72, forest * 0.68)
        colored = tuple(base[i] * (1.0 - mix) + forest_tint[i] * mix for i in range(4))
        if ore > 0.0:
            ore_tint = (0.70, 0.58, 0.34, 1.0)
            ore_mix = min(0.82, ore * 0.82)
            colored = tuple(colored[i] * (1.0 - ore_mix) + ore_tint[i] * ore_mix for i in range(4))
        return colored
