"""
preprocess.py

Spectral preprocessing utilities for hyperspectral soil / bare-ground analysis.
"""

from __future__ import annotations

import numpy as np


# Broad atmospheric absorption regions
DEFAULT_BROAD_BAD_WINDOWS_NM = [
    (1340.0, 1450.0),
    (1800.0, 1950.0),
    (2400.0, np.inf),
]

# Narrow likely atmospheric-residual / unstable regions
# Start conservative and adjust later if needed.
DEFAULT_NARROW_BAD_WINDOWS_NM = [
    (920.0, 960.0),
    (1110.0, 1145.0),
]


def build_bad_band_mask(
    wl_nm: np.ndarray,
    broad_windows=DEFAULT_BROAD_BAD_WINDOWS_NM,
    narrow_windows=DEFAULT_NARROW_BAD_WINDOWS_NM,
    include_narrow: bool = True,
) -> np.ndarray:
    """
    Returns boolean mask where True means 'bad band / exclude'.
    """
    wl_nm = np.asarray(wl_nm, dtype=float)
    bad = np.zeros(wl_nm.shape, dtype=bool)

    for lo, hi in broad_windows:
        bad |= (wl_nm > lo) & (wl_nm < hi)

    if include_narrow:
        for lo, hi in narrow_windows:
            bad |= (wl_nm > lo) & (wl_nm < hi)

    return bad


def clean_spectrum(
    wl_nm: np.ndarray,
    spec: np.ndarray,
    *,
    include_narrow_bad_bands: bool = True,
    max_reflectance: float = 1.2,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Clean one spectrum.

    Returns
    -------
    wl_nm_clean : wavelengths after removing bad bands
    spec_clean  : cleaned spectrum after removing bad bands
    keep_mask   : boolean mask over original wl/spec where True means kept
    """
    wl_nm = np.asarray(wl_nm, dtype=float)
    spec = np.asarray(spec, dtype=float)

    bad = build_bad_band_mask(
        wl_nm,
        include_narrow=include_narrow_bad_bands,
    )

    invalid = ~np.isfinite(spec) | (spec <= 0) | (spec > max_reflectance)
    keep = ~(bad | invalid)

    return wl_nm[keep], spec[keep], keep


def spectrum_for_plot(
    wl_nm: np.ndarray,
    spec: np.ndarray,
    *,
    include_narrow_bad_bands: bool = True,
    max_reflectance: float = 1.2,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Returns plotting arrays with bad bands set to NaN so they appear as gaps.

    Returns
    -------
    wl_nm       : original wavelengths
    spec_plot   : original spectrum with bad/invalid bands replaced by NaN
    bad_mask    : boolean mask where True means hidden
    """
    wl_nm = np.asarray(wl_nm, dtype=float)
    spec = np.asarray(spec, dtype=float)

    bad = build_bad_band_mask(
        wl_nm,
        include_narrow=include_narrow_bad_bands,
    )

    invalid = ~np.isfinite(spec) | (spec <= 0) | (spec > max_reflectance)

    spec_plot = spec.copy()
    spec_plot[bad | invalid] = np.nan

    return wl_nm, spec_plot, (bad | invalid)


def iqr_summary(values_lo: np.ndarray, values_hi: np.ndarray) -> float:
    """
    Returns median IQR width across wavelengths.
    """
    width = np.asarray(values_hi, dtype=float) - np.asarray(values_lo, dtype=float)
    return float(np.nanmedian(width))