"""Terrain sampling and biome queries for the procedural world.
URSINA Y-UP VERSION
"""

import math


def _smoothstep(edge0, edge1, value):
    if edge1 == edge0: return 1.0 if value >= edge1 else 0.0
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

    def _patch_factor(self, patches, x, z):
        best = 0.0
        for cx, cz, radius in patches:
            dist = math.sqrt((x - cx)**2 + (z - cz)**2)
            if dist >= radius: continue
            t = 1.0 - dist / radius
            factor = t * t * (1.35 - 0.35 * t)
            if factor > best: best = factor
        return best

    def set_river_paths(self, river_paths, river_width):
        self.river_paths = [list(path) for path in river_paths]
        self.river_width = float(river_width)

    def set_forest_patches(self, forest_patches): self.forest_patches = list(forest_patches)
    def set_ore_patches(self, ore_patches): self.ore_patches = list(ore_patches)

    def _base_height(self, x, z):
        return (
            4.2 * math.sin(x * 0.0105 + self._phase_a) * math.cos(z * 0.0085 - self._phase_b) +
            2.3 * math.sin((x + z) * 0.012 + self._phase_c) +
            1.1 * math.cos(x * 0.020 - z * 0.016 + self._phase_b)
        )

    def _distance_to_paths(self, x, z):
        best_sq = None
        for path in self.river_paths:
            for px, pz in path:
                dist_sq = (x - px)**2 + (z - pz)**2
                if best_sq is None or dist_sq < best_sq: best_sq = dist_sq
        return math.sqrt(best_sq) if best_sq is not None else None

    def forest_factor_at(self, x, z):
        if self.is_river(x, z, margin=2.0): return 0.0
        return self._patch_factor(self.forest_patches, x, z)

    def ore_factor_at(self, x, z):
        if self.is_river(x, z, margin=1.0): return 0.0
        return self._patch_factor(self.ore_patches, x, z)

    def is_river(self, x, z, margin=0.0):
        if not self.river_paths: return False
        dist = self._distance_to_paths(x, z)
        return dist <= (self.river_width + margin) if dist is not None else False

    def height_at(self, x, z):
        height = self._base_height(x, z)
        origin_dist = math.sqrt(x*x + z*z)
        height *= _smoothstep(self.spawn_flat_radius, self.spawn_blend_radius, origin_dist)

        forest = self.forest_factor_at(x, z)
        ore = self.ore_factor_at(x, z)
        if forest > 0.0:
            f_floor = height * (0.72 - 0.18 * forest) - 0.18 * forest
            height = height * (1.0 - forest * 0.8) + f_floor * (forest * 0.8)
        if ore > 0.0:
            o_floor = height * (0.58 - 0.10 * ore) - 0.22 * ore
            height = height * (1.0 - ore * 0.85) + o_floor * (ore * 0.85)

        river_dist = self._distance_to_paths(x, z)
        if river_dist is not None:
            bank_outer = self.river_width + 18.0
            if river_dist <= bank_outer:
                bed_inner, bed_outer = self.river_width * 0.35, self.river_width * 1.05
                if river_dist <= bed_inner: carve = 5.5
                elif river_dist <= bed_outer:
                    t = _smoothstep(bed_inner, bed_outer, river_dist)
                    carve = 5.5 * (1.0 - t) + 2.0 * t
                else:
                    t = _smoothstep(bed_outer, bank_outer, river_dist)
                    carve = 2.0 * (1.0 - t)
                
                h_damp = 0.12 if river_dist <= bed_outer else (0.12 * (1.0 - _smoothstep(bed_outer, bank_outer, river_dist)) + 1.0 * _smoothstep(bed_outer, bank_outer, river_dist))
                height = height * h_damp - carve
        return max(0.0, height)

    def normal_at(self, x, z, sample=2.0):
        hx0, hx1 = self.height_at(x - sample, z), self.height_at(x + sample, z)
        hz0, hz1 = self.height_at(x, z - sample), self.height_at(x, z + sample)
        nx, nz = hx0 - hx1, hz0 - hz1
        ny = sample * 2.0 # Vertical
        length = math.sqrt(nx*nx + ny*ny + nz*nz) or 1.0
        return (nx / length, ny / length, nz / length)

    def slope_at(self, x, z, sample=2.0):
        nx, ny, nz = self.normal_at(x, z, sample=sample)
        return math.sqrt(nx*nx + nz*nz) / max(0.001, ny)

    def ground_color_at(self, x, z):
        forest, ore, height = self.forest_factor_at(x, z), self.ore_factor_at(x, z), self.height_at(x, z)
        if self.is_river(x, z, margin=-2.0): return (0.30, 0.38, 0.30, 1.0)
        if self.is_river(x, z, margin=10.0): return (0.44, 0.46, 0.30, 1.0)
        low, high = (0.48, 0.60, 0.33, 1.0), (0.58, 0.70, 0.42, 1.0)
        t = max(0.0, min(1.0, height / 8.0))
        base = tuple(low[i] * (1.0 - t) + high[i] * t for i in range(4))
        f_tint, mix = (0.16, 0.24, 0.12, 1.0), min(0.72, forest * 0.68)
        colored = tuple(base[i] * (1.0 - mix) + f_tint[i] * mix for i in range(4))
        if ore > 0.0:
            o_tint, o_mix = (0.70, 0.58, 0.34, 1.0), min(0.82, ore * 0.82)
            colored = tuple(colored[i] * (1.0 - o_mix) + o_tint[i] * o_mix for i in range(4))
        return colored
