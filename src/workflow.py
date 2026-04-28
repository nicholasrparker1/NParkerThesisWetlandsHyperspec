from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import h5py
import matplotlib.pyplot as plt
import numpy as np

from src.config import DATA_RAW
from src.io_hyperspectral import discover_neon_h5_paths, latlon_to_rowcol, read_map_info


@dataclass(frozen=True)
class PointRecord:
    id: str
    lat: float
    lon: float
    fields: dict[str, str]


@dataclass(frozen=True)
class H5PointMatch:
    h5_path: Path
    reflectance_path: str
    wavelength_path: str
    map_info_path: str
    row: int
    col: int
    site: str | None = None


def find_h5_files(raw_dir: Path = DATA_RAW) -> list[Path]:
    h5_files = sorted(raw_dir.glob("*.h5"))
    if not h5_files:
        raise FileNotFoundError(f"No .h5 files found in {raw_dir}")
    return h5_files


def load_point_csv(csv_path: str | Path) -> list[PointRecord]:
    path = Path(csv_path)
    points: list[PointRecord] = []

    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required = {"id", "lat", "lon"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path} must contain columns: id, lat, lon")

        for row in reader:
            points.append(
                PointRecord(
                    id=str(row["id"]).strip(),
                    lat=float(row["lat"]),
                    lon=float(row["lon"]),
                    fields={k: v for k, v in row.items() if k not in required},
                )
            )

    if not points:
        raise RuntimeError(f"No points found in {path}")

    return points


def rainbow_colors(n: int):
    if n <= 0:
        return []
    return plt.cm.rainbow(np.linspace(0, 1, n))[::-1]


def normalize_wavelengths_nm(wavelengths: np.ndarray) -> np.ndarray:
    wl = np.asarray(wavelengths, dtype=float)
    if wl.size and float(np.nanmax(wl)) < 50.0:
        wl = wl * 1000.0
    return wl


def normalize_reflectance(reflectance: np.ndarray) -> np.ndarray:
    spec = np.asarray(reflectance, dtype=float)
    if np.any(np.isfinite(spec)) and float(np.nanmax(spec)) > 2.0:
        spec = spec / 10000.0
    return spec


def find_h5_for_point(
    lat: float,
    lon: float,
    h5_files: Iterable[Path] | None = None,
) -> H5PointMatch | None:
    files = list(h5_files) if h5_files is not None else find_h5_files()

    for h5_path in files:
        try:
            paths = discover_neon_h5_paths(str(h5_path))
            map_info = read_map_info(str(h5_path), paths["map_info_path"])
            row, col = latlon_to_rowcol(lat, lon, map_info)

            with h5py.File(h5_path, "r") as f:
                cube = f[paths["reflectance_path"]]
                rows, cols, _ = cube.shape

            if 0 <= row < rows and 0 <= col < cols:
                return H5PointMatch(
                    h5_path=h5_path,
                    reflectance_path=paths["reflectance_path"],
                    wavelength_path=paths["wavelength_path"],
                    map_info_path=paths["map_info_path"],
                    row=row,
                    col=col,
                    site=paths.get("site"),
                )
        except Exception:
            continue

    return None
