"""
io_hyperspectral.py

I/O utilities for NEON ROCX H5 hyperspectral reflectance products.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np
import h5py


# -----------------------------
# Basic H5 inspection utilities
# -----------------------------

def list_h5_datasets(h5_path: str) -> None:
    with h5py.File(h5_path, "r") as f:
        def visitor(name, obj):
            if isinstance(obj, h5py.Dataset):
                print(f"{name} | shape={obj.shape} | dtype={obj.dtype}")
        f.visititems(visitor)


def get_dataset_shape(h5_path: str, dset_path: str) -> Tuple[int, ...]:
    with h5py.File(h5_path, "r") as f:
        return tuple(f[dset_path].shape)


def read_1d_array(h5_path: str, dset_path: str) -> np.ndarray:
    with h5py.File(h5_path, "r") as f:
        return f[dset_path][:]


# -----------------------------
# Reflectance conventions
# -----------------------------

@dataclass(frozen=True)
class ReflectanceScaling:
    scale: float = 10000.0
    fill_raw: int = -10000
    min_valid: float = 0.0


SCALING = ReflectanceScaling()


def _scale_and_mask_spectrum(spec_raw: np.ndarray) -> np.ndarray:
    spec = spec_raw.astype(np.float32) / SCALING.scale
    spec[(spec_raw == SCALING.fill_raw) | (spec <= SCALING.min_valid)] = np.nan
    return spec


def _scale_and_mask_cube_window(win_raw: np.ndarray) -> np.ndarray:
    win = win_raw.astype(np.float32) / SCALING.scale
    win[(win_raw == SCALING.fill_raw) | (win <= SCALING.min_valid)] = np.nan
    return win


# -----------------------------
# Memory-safe reading
# -----------------------------

def read_pixel_spectrum(h5_path, cube_path, wave_path, r, c):
    with h5py.File(h5_path, "r") as f:
        wavelengths = f[wave_path][:]
        cube = f[cube_path]
        spec_raw = cube[r, c, :]
    return wavelengths, _scale_and_mask_spectrum(spec_raw)


def read_window(h5_path, cube_path, r0, r1, c0, c1):
    with h5py.File(h5_path, "r") as f:
        cube = f[cube_path]
        win_raw = cube[r0:r1, c0:c1, :]
    return _scale_and_mask_cube_window(win_raw)


def read_roi_mean_spectrum(h5_path, cube_path, wave_path, r0, r1, c0, c1):
    wavelengths = read_1d_array(h5_path, wave_path)
    win = read_window(h5_path, cube_path, r0, r1, c0, c1)
    return wavelengths, np.nanmean(win, axis=(0, 1))


# -----------------------------
# FAST nearest valid pixel search
# -----------------------------

def find_nearest_valid_pixel(
    h5_path: str,
    cube_path: str,
    r0: int,
    c0: int,
    search_radius: int = 200,
    band: int = 0,
) -> Tuple[int, int]:
    """
    Fast nearest-valid pixel search.

    Reads only ONE band and finds nearest valid pixel using numpy math.
    """

    with h5py.File(h5_path, "r") as f:
        cube = f[cube_path]
        rows, cols, _ = cube.shape

        if not (0 <= r0 < rows and 0 <= c0 < cols):
            raise ValueError(f"Requested pixel outside raster: r={r0}, c={c0}")

        rmin = max(0, r0 - search_radius)
        rmax = min(rows, r0 + search_radius + 1)
        cmin = max(0, c0 - search_radius)
        cmax = min(cols, c0 + search_radius + 1)

        band_slice = cube[rmin:rmax, cmin:cmax, band]

        valid_mask = band_slice != SCALING.fill_raw

        if not np.any(valid_mask):
            raise RuntimeError("No valid pixels found within search radius.")

        rr, cc = np.where(valid_mask)

        dist2 = (rr + rmin - r0) ** 2 + (cc + cmin - c0) ** 2
        idx = np.argmin(dist2)

        return int(rr[idx] + rmin), int(cc[idx] + cmin)


# -----------------------------
# Coordinate helpers
# -----------------------------

def read_map_info(h5_path: str, mapinfo_path: str) -> dict:
    epsg_path = mapinfo_path.replace("Map_Info", "EPSG Code")

    with h5py.File(h5_path, "r") as f:
        raw = f[mapinfo_path][()]
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")
        else:
            raw = str(raw)

        epsg = None
        if epsg_path in f:
            epsg_raw = f[epsg_path][()]
            if isinstance(epsg_raw, bytes):
                epsg_raw = epsg_raw.decode("utf-8", errors="ignore")
            epsg = int(str(epsg_raw).strip())

    parsed = parse_map_info(raw)
    parsed["raw"] = raw
    if epsg is not None:
        parsed["epsg"] = epsg
    return parsed


def parse_map_info(map_info_raw: str) -> dict:
    parts = [p.strip() for p in map_info_raw.split(",")]

    x0 = float(parts[3])
    y0 = float(parts[4])
    dx = float(parts[5])
    dy = float(parts[6])

    # UTM zone and hemisphere are commonly stored here (e.g., "... , 18, North, ...")
    try:
        zone = int(parts[7])
    except Exception as e:
        raise ValueError(f"Could not parse UTM zone from Map_Info: {map_info_raw}") from e

    hemi = parts[8].lower() if len(parts) > 8 else "north"
    if hemi.startswith("s"):
        epsg = 32700 + zone  # UTM South
    else:
        epsg = 32600 + zone  # UTM North

    return {
        "x0": x0,
        "y0": y0,
        "dx": dx,
        "dy": dy,
        "zone": zone,
        "epsg": epsg,
        "hemi": hemi,
    }


def latlon_to_rowcol(lat, lon, map_info):
    from pyproj import Transformer

    epsg = map_info["epsg"]

    transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    x, y = transformer.transform(lon, lat)

    col = int(round((x - map_info["x0"]) / map_info["dx"]))
    row = int(round((map_info["y0"] - y) / map_info["dy"]))

    return row, col
