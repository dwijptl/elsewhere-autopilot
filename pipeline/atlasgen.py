"""The atlas — a map of a planet that does not exist.

Channel 1 downloaded Earth's coastlines. We cannot: there is no GeoJSON for
Kelvara. So the atlas is GENERATED — deterministically, from a seed stored in
canon — and it is generated the SAME WAY every single time. That determinism is
the entire point: the map a viewer sees in episode 1 must be the map they see in
episode 30, or the world stops being a world and becomes a mood board.

Drop-in compatible with the map-zoom renderer channel 1 already uses:
render_scene_maps() returns {world, region, markerWorld, markerRegion}.

Regions come from canon/canon.json and are placed at fixed coordinates. A region
that canon has not REVEALED is drawn as blank ocean — the map itself keeps the
secret, and a later episode fills it in. That reveal is the returning-viewer
mechanic, so it is enforced in code rather than left to good intentions.

FAIL-OPEN: any problem returns None and the scene falls back to a still.
"""
from __future__ import annotations

import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter

import canon as canon_mod

# The dossier palette (canon/art_bible.md). Nothing here is navy — that is
# channel 1's colour and the two channels must never be confused.
PAPER = (28, 24, 20)        # deep warm black, not blue-black
SEA = (34, 46, 47)          # the Slow Sea — desaturated teal
LAND = (58, 46, 34)         # basalt / ochre landmass
LAND_EDGE = (150, 106, 58)  # amber coastline — the engineered accent
GRID = (72, 58, 42)         # survey graticule
UNREVEALED = (36, 34, 31)   # terra incognita: drawn, but empty

WORLD_SEED = 91177          # the shape of the planet. NEVER change this.


def _cache_dir() -> str:
    d = os.path.join(os.path.expanduser("~"), ".cache", "elsewhere_atlas")
    os.makedirs(d, exist_ok=True)
    return d


def _continents(seed: int = WORLD_SEED) -> list[list[tuple[float, float]]]:
    """Deterministic landmasses in lon/lat space.

    Blobs of radial noise, not real tectonics — but consistent, and consistent
    is what a persistent world needs. The water/land split is deliberately
    lopsided (one wet hemisphere, one dry) because canon says the scarcity line
    is the planet's central political fact, and the map has to show that.
    """
    rng = random.Random(seed)
    shapes = []
    # (centre_lon, centre_lat, radius_deg, roughness) — the dry hemisphere is
    # one big continent; the wet hemisphere is broken into shelves.
    blobs = [
        (-70, 12, 58, 0.30),   # the great dry continent (Cinder Shelf lives here)
        (-40, -48, 30, 0.34),  # southern spur
        (95, 5, 26, 0.40),     # wet-hemisphere shelf
        (140, 38, 22, 0.42),
        (120, -40, 25, 0.38),
        (170, -8, 14, 0.45),
    ]
    for lon_c, lat_c, radius, rough in blobs:
        pts, steps = [], 260
        # Summed harmonics with falling amplitude — coastlines are rough at
        # every scale, and a single sine wave reads instantly as a blob. Eight
        # octaves is enough to look surveyed rather than generated.
        octaves = [(k + 2, rng.uniform(-rough, rough) / (k + 1) ** 0.75,
                    rng.uniform(0, 2 * math.pi)) for k in range(8)]
        for i in range(steps):
            th = 2 * math.pi * i / steps
            wobble = 1.0 + sum(a * math.sin(f * th + ph) for f, a, ph in octaves)
            r = radius * max(0.40, wobble)
            lon = lon_c + r * math.cos(th) * 1.35
            lat = lat_c + r * math.sin(th) * 0.72
            pts.append((lon, max(-88, min(88, lat))))
        shapes.append(pts)
    return shapes


def _project(lon: float, lat: float, bbox: tuple, size: tuple) -> tuple:
    x = (lon - bbox[0]) / (bbox[2] - bbox[0]) * size[0]
    y = (bbox[3] - lat) / (bbox[3] - bbox[1]) * size[1]
    return x, y


def _render(shapes: list, bbox: tuple, size: tuple, grid_step: int,
            regions: list) -> Image.Image:
    img = Image.new("RGB", size, SEA)
    d = ImageDraw.Draw(img)

    lon0 = math.floor(bbox[0] / grid_step) * grid_step
    lat0 = math.floor(bbox[1] / grid_step) * grid_step
    for lon in range(int(lon0), int(bbox[2]) + grid_step, grid_step):
        x, _ = _project(lon, 0, bbox, size)
        d.line([(x, 0), (x, size[1])], fill=GRID, width=2)
    for lat in range(int(lat0), int(bbox[3]) + grid_step, grid_step):
        _, y = _project(0, lat, bbox, size)
        d.line([(0, y), (size[0], y)], fill=GRID, width=2)

    for pts in shapes:
        poly = [_project(lon, lat, bbox, size) for lon, lat in pts]
        d.polygon(poly, fill=LAND, outline=LAND_EDGE)
        d.line(poly + [poly[0]], fill=LAND_EDGE, width=4)

    # Revealed regions get an amber survey ring. Everything else stays dark —
    # the map does not spoil an episode that has not aired.
    for r in regions:
        if r.get("status") != "revealed":
            continue
        lon, lat = r["_coords"]
        x, y = _project(lon, lat, bbox, size)
        rad = max(size) * 0.012
        d.ellipse([x - rad, y - rad, x + rad, y + rad],
                  outline=LAND_EDGE, width=3)
        d.ellipse([x - rad / 3, y - rad / 3, x + rad / 3, y + rad / 3],
                  fill=LAND_EDGE)

    vignette = Image.new("L", size, 0)
    ImageDraw.Draw(vignette).ellipse(
        [-size[0] * 0.15, -size[1] * 0.15, size[0] * 1.15, size[1] * 1.15],
        fill=190)
    vignette = vignette.filter(ImageFilter.GaussianBlur(size[0] // 22))
    img = Image.composite(img, Image.new("RGB", size, PAPER), vignette)
    return img


# Fixed coordinates for canon regions. A region's position on the planet is
# canon: once an episode has shown it, it can never move.
REGION_COORDS = {
    "REG-01": (-78.0, 14.0),    # The Cinder Shelf — dry hemisphere, near equator
    "REG-02": (104.0, -6.0),    # The Slow Sea — wet hemisphere shelf
}


def render_scene_maps(region_id: str, workdir: str, scene_n: int,
                      portrait: bool = False, repo_root: str = ".") -> dict | None:
    """Render world + region atlas plates for one locator scene."""
    try:
        world_canon = canon_mod.load(repo_root)
        regions = []
        for r in world_canon["atlas"]["regions"]:
            coords = REGION_COORDS.get(r["id"])
            if coords:
                regions.append({**r, "_coords": coords})

        target = next((r for r in regions if r["id"] == region_id), None)
        if target is None:
            print(f"[atlas] region '{region_id}' has no coordinates — "
                  f"add it to REGION_COORDS before an episode uses it")
            return None
        if target.get("status") != "revealed":
            print(f"[atlas] region '{region_id}' is not revealed yet — "
                  f"an episode cannot be located on it")
            return None

        lon, lat = target["_coords"]
        size = (2160, 3840) if portrait else (3840, 2160)
        aspect = size[0] / size[1]
        shapes = _continents()

        lat_span_w = 360 / aspect
        bbox_w = ((-180, -90, 180, 90) if lat_span_w >= 180
                  else (-180, -lat_span_w / 2, 180, lat_span_w / 2))
        world = _render(shapes, bbox_w, size, 30, regions)

        lon_span = 24.0 if portrait else 40.0
        lat_span = lon_span / aspect
        r_lat = max(min(lat, 90 - lat_span / 2), lat_span / 2 - 90)
        bbox_r = (lon - lon_span / 2, r_lat - lat_span / 2,
                  lon + lon_span / 2, r_lat + lat_span / 2)
        region = _render(shapes, bbox_r, size, 5, regions)

        def frac(bbox: tuple) -> list:
            fx = (lon - bbox[0]) / (bbox[2] - bbox[0])
            fy = (bbox[3] - lat) / (bbox[3] - bbox[1])
            return [round(min(max(fx, 0.02), 0.98), 4),
                    round(min(max(fy, 0.02), 0.98), 4)]

        wname = f"atlas_s{scene_n:02d}_world.png"
        rname = f"atlas_s{scene_n:02d}_region.png"
        world.save(os.path.join(workdir, wname))
        region.save(os.path.join(workdir, rname))
        print(f"[atlas] scene {scene_n}: {target['name']} located "
              f"({lat:.1f}, {lon:.1f})")
        return {"world": wname, "region": rname,
                "markerWorld": frac(bbox_w), "markerRegion": frac(bbox_r),
                "label": target["name"]}
    except Exception as e:
        print(f"[atlas] render failed ({e}) — scene falls back to a still")
        return None
