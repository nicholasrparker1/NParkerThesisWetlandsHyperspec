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

def discover_neon_h5_paths(h5_path: str) -> dict:
    """
    Auto-discover the main NEON-style paths inside an HDF5 hyperspectral file.

    Returns a dictionary with:
        site
        reflectance_path
        wavelength_path
        map_info_path
        epsg_path
    """
    result = {
        "site": None,
        "reflectance_path": None,
        "wavelength_path": None,
        "map_info_path": None,
        "epsg_path": None,
    }

    with h5py.File(h5_path, "r") as f:
        dataset_names = []

        def visitor(name, obj):
            if isinstance(obj, h5py.Dataset):
                dataset_names.append(name)

        f.visititems(visitor)

    for name in dataset_names:
        if name.endswith("/Reflectance/Reflectance_Data"):
            result["reflectance_path"] = name
            result["site"] = name.split("/")[0]

        elif name.endswith("/Reflectance/Metadata/Spectral_Data/Wavelength"):
            result["wavelength_path"] = name

        elif name.endswith("/Reflectance/Metadata/Coordinate_System/Map_Info"):
            result["map_info_path"] = name

        elif name.endswith("/Reflectance/Metadata/Coordinate_System/EPSG Code"):
            result["epsg_path"] = name

    missing = [k for k, v in result.items() if k != "epsg_path" and v is None]
    if missing:
        raise ValueError(
            f"Could not auto-discover required paths in {h5_path}. Missing: {missing}"
        )

    return result

def get_wavelengths_from_file(h5_path: str):
    """
    Open a NEON-style HDF5 file, auto-discover the wavelength path,
    and return the wavelength array.
    """
    paths = discover_neon_h5_paths(h5_path)
    return read_1d_array(h5_path, paths["wavelength_path"])


def get_map_info_and_epsg_from_file(h5_path: str):
    """
    Open a NEON-style HDF5 file, auto-discover the coordinate metadata paths,
    and return (map_info, epsg_code).
    """
    paths = discover_neon_h5_paths(h5_path)
    map_info = read_map_info(h5_path, paths["map_info_path"])
    epsg_code = None

    if paths["epsg_path"] is not None:
        with h5py.File(h5_path, "r") as f:
            epsg_raw = f[paths["epsg_path"]][()]
            if isinstance(epsg_raw, bytes):
                epsg_code = epsg_raw.decode("utf-8")
            else:
                epsg_code = str(epsg_raw)

    return map_info, epsg_code



def latlon_to_rowcol_from_file(h5_path: str, lat: float, lon: float):
    """
    Convert lat/lon to row/col using coordinate metadata auto-discovered
    from the HDF5 file.
    """
    map_info, _ = get_map_info_and_epsg_from_file(h5_path)
    return latlon_to_rowcol(lat, lon, map_info)


def point_in_file_bounds(h5_path: str, lat: float, lon: float):
    """
    Return row, col, and whether the point falls inside the reflectance cube bounds.
    """
    paths = discover_neon_h5_paths(h5_path)
    row, col = latlon_to_rowcol_from_file(h5_path, lat, lon)

    with h5py.File(h5_path, "r") as f:
        cube = f[paths["reflectance_path"]]
        rows, cols, _ = cube.shape

    inside = (0 <= row < rows) and (0 <= col < cols)

    return {
        "row": row,
        "col": col,
        "rows": rows,
        "cols": cols,
        "inside": inside,
    }

def read_pixel_spectrum_from_file(h5_path: str, row: int, col: int):
    """
    Read a single pixel spectrum using auto-discovered reflectance and wavelength paths.
    Returns (wavelengths, spectrum).
    """
    paths = discover_neon_h5_paths(h5_path)
    return read_pixel_spectrum(
        h5_path,
        paths["reflectance_path"],
        paths["wavelength_path"],
        row,
        col,
    )

def read_pixel_spectrum_from_file_with_snap(
    h5_path: str,
    row: int,
    col: int,
    search_radius: int = 20,
    band: int = 0,
):
    """
    Read a single pixel spectrum, snapping to the nearest valid pixel if needed.
    Returns (wavelengths, spectrum, used_row, used_col).
    """
    paths = discover_neon_h5_paths(h5_path)

    used_row, used_col = find_nearest_valid_pixel(
        h5_path,
        paths["reflectance_path"],
        row,
        col,
        search_radius=search_radius,
        band=band,
    )

    wavelengths, spectrum = read_pixel_spectrum(
        h5_path,
        paths["reflectance_path"],
        paths["wavelength_path"],
        used_row,
        used_col,
    )

    return wavelengths, spectrum, used_row, used_col

def read_roi_stats_spectrum(
    h5_path: str,
    cube_path: str,
    wl_path: str,
    row: int,
    col: int,
    roi: int,
    p_lo: float = 25,
    p_hi: float = 75,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, tuple[int, int, int, int]]:
    """Return wavelength, ROI median, lower percentile, upper percentile, and bounds."""
    if roi < 1 or roi % 2 == 0:
        raise ValueError("roi must be an odd integer >= 1")

    with h5py.File(h5_path, "r") as f:
        cube = f[cube_path]
        wl = f[wl_path][:]

        rows, cols, _ = cube.shape
        half = roi // 2

        rmin = max(0, row - half)
        rmax = min(rows - 1, row + half)
        cmin = max(0, col - half)
        cmax = min(cols - 1, col + half)

        win = cube[rmin:rmax + 1, cmin:cmax + 1, :].astype(np.float32)

    win = _scale_and_mask_cube_window(win)

    n_pix = win.shape[0] * win.shape[1]
    win2 = win.reshape(n_pix, win.shape[2])

    valid_counts = np.sum(np.isfinite(win2), axis=0)
    min_valid = max(1, int(0.20 * n_pix))

    med = np.nanmedian(win2, axis=0)
    lo = np.nanpercentile(win2, p_lo, axis=0)
    hi = np.nanpercentile(win2, p_hi, axis=0)

    med[valid_counts < min_valid] = np.nan
    lo[valid_counts < min_valid] = np.nan
    hi[valid_counts < min_valid] = np.nan

    return wl, med, lo, hi, (rmin, rmax, cmin, cmax)


def read_roi_median_spectrum(
    h5_path: str,
    cube_path: str,
    wl_path: str,
    row: int,
    col: int,
    roi: int,
) -> tuple[np.ndarray, np.ndarray, tuple[int, int, int, int]]:
    wl, med, _lo, _hi, bounds = read_roi_stats_spectrum(
        h5_path,
        cube_path,
        wl_path,
        row,
        col,
        roi,
    )
    return wl, med, bounds


def read_roi_median_spectrum_from_file(
    h5_path: str,
    row: int,
    col: int,
    roi: int,
):
    """
    Read an ROI median spectrum using auto-discovered reflectance and wavelength paths.
    Returns (wavelengths, median_spectrum, bounds).
    """
    paths = discover_neon_h5_paths(h5_path)
    return read_roi_median_spectrum(
        h5_path,
        paths["reflectance_path"],
        paths["wavelength_path"],
        row,
        col,
        roi,
    )

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

def extract_spectrum_from_latlon(
    h5_path: str,
    lat: float,
    lon: float,
    roi_size: int = 1,
    snap_radius: int = 20,
):
    """
    End-to-end extraction from lat/lon.

    Returns a dictionary with:
        row, col, inside, wavelengths, spectrum, bounds
    """
    info = point_in_file_bounds(h5_path, lat, lon)

    result = {
        "row": info["row"],
        "col": info["col"],
        "inside": info["inside"],
        "wavelengths": None,
        "spectrum": None,
        "bounds": None,
        "used_row": None,
        "used_col": None,
    }

    if not info["inside"]:
        return result

    if roi_size == 1:
        w, s, used_row, used_col = read_pixel_spectrum_from_file_with_snap(
            h5_path,
            info["row"],
            info["col"],
            search_radius=snap_radius,
        )
        result["wavelengths"] = w
        result["spectrum"] = s
        result["used_row"] = used_row
        result["used_col"] = used_col
    else:
        w, s, bounds = read_roi_median_spectrum_from_file(
            h5_path,
            info["row"],
            info["col"],
            roi_size,
        )
        result["wavelengths"] = w
        result["spectrum"] = s
        result["bounds"] = bounds
        result["used_row"] = info["row"]
        result["used_col"] = info["col"]

    return result

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

        valid_mask = (band_slice != SCALING.fill_raw) & ((band_slice.astype(np.float32) / SCALING.scale) > SCALING.min_valid)

        if not np.any(valid_mask):
            raise RuntimeError("No valid pixels found within search radius.")

        rr, cc = np.where(valid_mask)

        dist2 = (rr + rmin - r0) ** 2 + (cc + cmin - c0) ** 2
        idx = np.argmin(dist2)

        return int(rr[idx] + rmin), int(cc[idx] + cmin)


def snap_to_valid_pixel(
    h5_path: str,
    cube_path: str,
    row: int,
    col: int,
    *,
    radius: int = 50,
    band: int = 0,
) -> tuple[int | None, int | None]:
    """
    Return the nearest valid pixel inside a true Euclidean radius.

    Unlike find_nearest_valid_pixel, this returns (None, None) when no valid
    pixel is available so CLI scripts can print clearer location-specific errors.
    """
    try:
        used_row, used_col = find_nearest_valid_pixel(
            h5_path,
            cube_path,
            row,
            col,
            search_radius=radius,
            band=band,
        )
    except RuntimeError:
        return None, None

    if (used_row - row) ** 2 + (used_col - col) ** 2 > radius ** 2:
        return None, None
    return used_row, used_col


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

def rowcol_to_latlon(row, col, map_info):
    x = map_info["x0"] + col * map_info["dx"]
    y = map_info["y0"] - row * map_info["dy"]

    from pyproj import CRS, Transformer
    transformer = Transformer.from_crs(
        CRS.from_epsg(map_info["epsg"]),
        CRS.from_epsg(4326),
        always_xy=True,
    )
    lon, lat = transformer.transform(x, y)
    return lat, lon
