from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from src.io_hyperspectral import read_roi_median_spectrum, snap_to_valid_pixel
from src.workflow import (
    find_h5_files,
    find_h5_for_point,
    normalize_reflectance,
    normalize_wavelengths_nm,
)


def lookup_point_in_csv(csv_path: str | Path, point_id: int) -> tuple[float, float]:
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        required = {"id", "lat", "lon"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"{csv_path} must contain columns: id, lat, lon")

        for row in reader:
            if int(row["id"]) == int(point_id):
                return float(row["lat"]), float(row["lon"])

    raise ValueError(f"Point id {point_id} not found in {csv_path}")


def load_alpha_csv(csv_path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    wl = []
    alpha = []
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        required = {"wavelength_nm", "alpha_water"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"{csv_path} must contain columns: wavelength_nm, alpha_water")
        for row in reader:
            wl.append(float(row["wavelength_nm"]))
            alpha.append(float(row["alpha_water"]))
    return np.asarray(wl, dtype=float), np.asarray(alpha, dtype=float)


def extract_clean_roi_spectrum(
    h5_path: str | Path | None,
    lat: float,
    lon: float,
    *,
    snap: int,
    roi: int,
) -> tuple[np.ndarray, np.ndarray, tuple[int, int]]:
    """
    Extract a normalized ROI median spectrum and mask invalid reflectance values.

    Bad atmospheric wavelength bands are kept on the wavelength axis so plotting
    and fitting helpers can choose their own masks later.
    """
    h5_files = [Path(h5_path)] if h5_path is not None else find_h5_files()
    match = find_h5_for_point(lat, lon, h5_files)
    if match is None:
        raise RuntimeError(f"Point ({lat}, {lon}) is not inside any H5 tile.")

    row, col = snap_to_valid_pixel(
        str(match.h5_path),
        match.reflectance_path,
        match.row,
        match.col,
        radius=snap,
        band=0,
    )
    if row is None or col is None:
        raise RuntimeError(
            f"No valid pixel found within radius={snap} for lat/lon=({lat}, {lon})"
        )

    wavelengths, spectrum, _bounds = read_roi_median_spectrum(
        str(match.h5_path),
        match.reflectance_path,
        match.wavelength_path,
        row,
        col,
        roi=roi,
    )

    wavelengths = normalize_wavelengths_nm(wavelengths)
    spectrum = normalize_reflectance(spectrum)
    spectrum[(spectrum <= 0.0) | (spectrum >= 1.2)] = np.nan

    return wavelengths, spectrum, (row, col)


def intersect_clean_spectra(
    wl1: np.ndarray,
    s1: np.ndarray,
    wl2: np.ndarray,
    s2: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    common = np.intersect1d(wl1, wl2)
    if common.size < 10:
        raise RuntimeError("Too few common wavelengths between spectra.")

    idx1 = np.nonzero(np.isin(wl1, common))[0]
    idx2 = np.nonzero(np.isin(wl2, common))[0]
    return common, s1[idx1], s2[idx2]


def intersect_three_clean_spectra(
    wl1: np.ndarray,
    s1: np.ndarray,
    wl2: np.ndarray,
    s2: np.ndarray,
    wl3: np.ndarray,
    s3: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    common = np.intersect1d(np.intersect1d(wl1, wl2), wl3)
    if common.size < 10:
        raise RuntimeError("Too few common wavelengths between the three spectra.")

    i1 = np.nonzero(np.isin(wl1, common))[0]
    i2 = np.nonzero(np.isin(wl2, common))[0]
    i3 = np.nonzero(np.isin(wl3, common))[0]
    return common, s1[i1], s2[i2], s3[i3]
