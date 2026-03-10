# src/h5_report.py
from __future__ import annotations

import json
import math
from typing import Any, Dict, List

import h5py
import numpy as np


# ======================================================================================
# JSON safety helpers
# ======================================================================================

def json_safe(x: Any) -> Any:
    """
    Convert numpy / bytes / nested structures into JSON-safe Python types.
    This lets us json.dump() the full report without "not JSON serializable" errors.
    """
    # bytes -> str
    if isinstance(x, (bytes, bytearray)):
        return x.decode("utf-8", errors="replace")

    # numpy array -> list
    if isinstance(x, np.ndarray):
        return x.tolist()

    # numpy scalar -> python scalar
    if isinstance(x, np.generic):
        return x.item()

    # dict/list recursion
    if isinstance(x, dict):
        return {k: json_safe(v) for k, v in x.items()}

    if isinstance(x, (list, tuple)):
        return [json_safe(v) for v in x]

    return x


def _decode_scalar(x: Any) -> Any:
    """Convert HDF5 scalar/bytes/object to a readable Python type."""
    if isinstance(x, (bytes, bytearray)):
        try:
            return x.decode("utf-8", errors="replace")
        except Exception:
            return repr(x)

    # HDF5 scalar stored as 0-d numpy array
    if isinstance(x, np.ndarray) and x.shape == ():
        return _decode_scalar(x.item())

    # numpy scalar
    if isinstance(x, np.generic):
        return x.item()

    return x


def read_attrs(obj: Any) -> Dict[str, Any]:
    """Read HDF5 attributes into a plain dict of JSON-friendly scalars/strings."""
    out: Dict[str, Any] = {}
    for k, v in obj.attrs.items():
        out[k] = _decode_scalar(v)
    return out


# ======================================================================================
# Stats (safe on huge arrays + safe on non-numeric datasets)
# ======================================================================================

def dataset_stats(dset: h5py.Dataset, sample_max: int = 250_000) -> Dict[str, Any]:
    """
    Compute summary stats without reading huge datasets fully.

    - Scalars: return value
    - Small arrays: read fully
    - Big 2D arrays: stride-sample to ~sample_max elements
    - 3D cubes: read a small window and a few bands
    - Non-numeric (strings/objects): return a preview value
    """
    shape = dset.shape
    ndim = len(shape)

    # Scalars
    if ndim == 0:
        return {"value": _decode_scalar(dset[()])}

    # If it's not numeric, don't try to cast to float64
    # kind: 'i' int, 'u' uint, 'f' float are numeric; 'O','S','U' are not
    if dset.dtype.kind not in ("i", "u", "f"):
        try:
            preview = dset[()]
            return {"value_preview": _decode_scalar(preview), "dtype_kind": dset.dtype.kind}
        except Exception as e:
            return {"error": f"non-numeric dataset; failed to preview: {e}", "dtype_kind": dset.dtype.kind}

    # Decide how to sample
    size = int(np.prod(shape))

    if size <= sample_max:
        arr = np.array(dset[...], dtype=np.float64)
    else:
        if ndim == 2:
            r, c = shape
            target = sample_max  # e.g. 250k ~ 500x500
            step = int(max(1, math.sqrt((r * c) / target)))
            arr = np.array(dset[0:r:step, 0:c:step], dtype=np.float64)

        elif ndim == 3:
            # reflectance cube: sample a small window & a few bands
            r, c, b = shape

            # pick a central-ish spot but bounded
            r0 = min(1000, r // 2)
            c0 = min(1000, c // 2)

            rb = slice(max(0, r0 - 25), min(r, r0 + 25))
            cb = slice(max(0, c0 - 25), min(c, c0 + 25))

            bands = np.linspace(0, b - 1, num=min(20, b), dtype=int)
            # IMPORTANT: h5py supports 1D fancy indexing on the last dimension here
            arr = np.array(dset[rb, cb, bands], dtype=np.float64)

        else:
            # fallback: read a small leading chunk
            sl = tuple(slice(0, min(200, s)) for s in shape)
            arr = np.array(dset[sl], dtype=np.float64)

    # Handle NaNs / infinities
    finite = np.isfinite(arr)
    n_total = int(arr.size)
    n_finite = int(finite.sum())
    n_nan = int((~finite).sum())

    if n_finite == 0:
        return {"n_total_sampled": n_total, "n_finite_sampled": 0, "n_nan_sampled": n_nan}

    vals = arr[finite]
    return {
        "n_total_sampled": n_total,
        "n_finite_sampled": n_finite,
        "n_nan_sampled": n_nan,
        "min": float(vals.min()),
        "max": float(vals.max()),
        "mean": float(vals.mean()),
        "std": float(vals.std()),
        "p01": float(np.quantile(vals, 0.01)),
        "p99": float(np.quantile(vals, 0.99)),
        "example_values": [float(x) for x in vals.flatten()[:10]],
    }


# ======================================================================================
# Map_Info parsing (best-effort)
# ======================================================================================

def parse_map_info(map_info: Any) -> Dict[str, Any]:
    """
    NEON often stores Map_Info as a string. We return:
      - raw string
      - best-effort guess of pixel size (x, y) if we can infer it
    """
    s = _decode_scalar(map_info)
    out: Dict[str, Any] = {"raw": s}
    if not isinstance(s, str):
        return out

    parts = [p.strip() for p in s.replace("{", "").replace("}", "").split(",")]
    floats: List[float] = []
    for p in parts:
        try:
            floats.append(float(p))
        except Exception:
            pass

    # Heuristic: last two floats often are pixel sizes for some encodings
    if len(floats) >= 2:
        out["pixel_size_guess"] = {"x": floats[-2], "y": floats[-1]}
    return out


# ======================================================================================
# Report builder
# ======================================================================================

def build_report(h5_path: str) -> Dict[str, Any]:
    with h5py.File(h5_path, "r") as f:
        report: Dict[str, Any] = {
            "file": h5_path,
            "key_paths_present": {},
            "coordinate_system": {},
            "key_dataset_summaries": {},
        }

        # Key paths (safe if missing)
        key_paths = {
            "reflectance_cube": "ROCX/Reflectance/Reflectance_Data",
            "wavelengths": "ROCX/Reflectance/Metadata/Spectral_Data/Wavelength",
            "fwhm": "ROCX/Reflectance/Metadata/Spectral_Data/FWHM",
            "solar_azimuth": "ROCX/Reflectance/Metadata/Logs/Solar_Azimuth_Angle",
            "solar_zenith": "ROCX/Reflectance/Metadata/Logs/Solar_Zenith_Angle",
            "to_sensor_azimuth": "ROCX/Reflectance/Metadata/to-sensor_Azimuth_Angle",
            "to_sensor_zenith": "ROCX/Reflectance/Metadata/to-sensor_Zenith_Angle",
            "flight_altitude": "ROCX/Reflectance/Metadata/Flight_Trajectory/Flight_Altitude",
            "flight_heading": "ROCX/Reflectance/Metadata/Flight_Trajectory/Flight_Heading",
            "flight_time": "ROCX/Reflectance/Metadata/Flight_Trajectory/Flight_Time",
            "smooth_surface_elev": "ROCX/Reflectance/Metadata/Ancillary_Imagery/Smooth_Surface_Elevation",
            "coord_epsg": "ROCX/Reflectance/Metadata/Coordinate_System/EPSG Code",
            "coord_mapinfo": "ROCX/Reflectance/Metadata/Coordinate_System/Map_Info",
            "coord_proj4": "ROCX/Reflectance/Metadata/Coordinate_System/Proj4",
        }

        present: Dict[str, str] = {}
        for k, p in key_paths.items():
            if p in f:
                present[k] = p
        report["key_paths_present"] = present

        # Coordinate system summary
        coord: Dict[str, Any] = {}
        if "coord_epsg" in present:
            coord["epsg"] = _decode_scalar(f[present["coord_epsg"]][()])
        if "coord_proj4" in present:
            coord["proj4"] = _decode_scalar(f[present["coord_proj4"]][()])
        if "coord_mapinfo" in present:
            coord["map_info"] = parse_map_info(f[present["coord_mapinfo"]][()])
        report["coordinate_system"] = coord

        # Summarize key datasets
        key_summaries: Dict[str, Any] = {}
        for k, p in present.items():
            obj = f[p]
            if isinstance(obj, h5py.Dataset):
                key_summaries[k] = {
                    "path": p,
                    "shape": obj.shape,
                    "dtype": str(obj.dtype),
                    "attrs": read_attrs(obj),
                    "stats": dataset_stats(obj),
                }
        report["key_dataset_summaries"] = key_summaries

        return report


def write_report(h5_path: str, out_json: str, out_txt: str) -> None:
    rep = build_report(h5_path)

    # -------------------------
    # JSON (machine-readable)
    # -------------------------
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(json_safe(rep), f, indent=2)

    # -------------------------
    # TXT (human-readable)
    # -------------------------
    lines: List[str] = []
    lines.append("OFFICEROS/THESIS H5 SUMMARY REPORT")
    lines.append("=" * 80)
    lines.append(f"File: {rep['file']}")
    lines.append("")

    cs = rep.get("coordinate_system", {})
    if cs:
        lines.append("COORDINATE SYSTEM")
        lines.append("-" * 80)
        for k, v in cs.items():
            lines.append(f"{k}: {v}")
        lines.append("")

    lines.append("KEY DATASETS (SHAPES / UNITS / STATS)")
    lines.append("-" * 80)

    for name, info in rep["key_dataset_summaries"].items():
        lines.append(f"\n{name}")
        lines.append(f"  path: {info['path']}")
        lines.append(f"  shape: {info['shape']}")
        lines.append(f"  dtype: {info['dtype']}")

        attrs = info.get("attrs", {}) or {}
        if attrs:
            for a in ["units", "unit", "scale_factor", "add_offset", "FillValue", "_FillValue", "missing_value"]:
                if a in attrs:
                    lines.append(f"  attr {a}: {attrs[a]}")

        stats = info.get("stats", {}) or {}
        if "value" in stats:
            lines.append(f"  value: {stats['value']}")
        elif "value_preview" in stats:
            lines.append(f"  value_preview: {stats['value_preview']}")
        else:
            for k in ["min", "max", "mean", "std", "p01", "p99", "n_total_sampled", "n_nan_sampled"]:
                if k in stats:
                    lines.append(f"  {k}: {stats[k]}")
            if "example_values" in stats:
                lines.append(f"  example_values: {stats['example_values']}")

    with open(out_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
