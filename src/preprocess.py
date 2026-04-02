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


def _as_1d_float(arr: np.ndarray, name: str) -> np.ndarray:
    """
    Convert input to a 1D float numpy array.
    """
    out = np.asarray(arr, dtype=float).reshape(-1)
    if out.ndim != 1:
        raise ValueError(f"{name} must be 1D.")
    return out


def _check_same_shape(a: np.ndarray, b: np.ndarray, a_name: str, b_name: str) -> None:
    """
    Raise an error if two arrays do not have the same shape.
    """
    if a.shape != b.shape:
        raise ValueError(
            f"{a_name} and {b_name} must have the same shape. "
            f"Got {a.shape} and {b.shape}."
        )


def build_bad_band_mask(
    wl_nm: np.ndarray,
    broad_windows=DEFAULT_BROAD_BAD_WINDOWS_NM,
    narrow_windows=DEFAULT_NARROW_BAD_WINDOWS_NM,
    include_narrow: bool = True,
) -> np.ndarray:
    """
    Return boolean mask where True means 'bad band / exclude based on wavelength'.

    Parameters
    ----------
    wl_nm : np.ndarray
        Wavelengths in nm.
    broad_windows : sequence of (float, float)
        Broad atmospheric absorption windows to exclude.
    narrow_windows : sequence of (float, float)
        Narrow suspicious windows to optionally exclude.
    include_narrow : bool
        If True, include the narrow bad-band windows.

    Returns
    -------
    np.ndarray
        Boolean array of same shape as wl_nm, where True means band is masked.
    """
    wl_nm = _as_1d_float(wl_nm, "wl_nm")
    bad = np.zeros(wl_nm.shape, dtype=bool)

    for lo, hi in broad_windows:
        bad |= (wl_nm >= lo) & (wl_nm <= hi)

    if include_narrow:
        for lo, hi in narrow_windows:
            bad |= (wl_nm >= lo) & (wl_nm <= hi)

    return bad


def build_invalid_value_mask(
    spec: np.ndarray,
    *,
    min_reflectance: float = 0.0,
    max_reflectance: float = 1.2,
) -> np.ndarray:
    """
    Return boolean mask where True means 'invalid value'.

    Parameters
    ----------
    spec : np.ndarray
        Reflectance spectrum.
    min_reflectance : float
        Minimum allowed reflectance. Values <= this are masked.
    max_reflectance : float
        Maximum allowed reflectance. Values > this are masked.

    Returns
    -------
    np.ndarray
        Boolean array where True means invalid.
    """
    spec = _as_1d_float(spec, "spec")
    invalid = ~np.isfinite(spec) | (spec <= min_reflectance) | (spec > max_reflectance)
    return invalid


def clean_spectrum(
    wl_nm: np.ndarray,
    spec: np.ndarray,
    *,
    include_narrow_bad_bands: bool = True,
    min_reflectance: float = 0.0,
    max_reflectance: float = 1.2,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Clean one spectrum by removing masked wavelength regions and invalid values.

    Returns
    -------
    wl_nm_clean : np.ndarray
        Wavelengths after removing bad/invalid bands.
    spec_clean : np.ndarray
        Cleaned spectrum after removing bad/invalid bands.
    keep_mask : np.ndarray
        Boolean mask over original arrays where True means kept.
    """
    wl_nm = _as_1d_float(wl_nm, "wl_nm")
    spec = _as_1d_float(spec, "spec")
    _check_same_shape(wl_nm, spec, "wl_nm", "spec")

    bad_band_mask = build_bad_band_mask(
        wl_nm,
        include_narrow=include_narrow_bad_bands,
    )
    invalid_value_mask = build_invalid_value_mask(
        spec,
        min_reflectance=min_reflectance,
        max_reflectance=max_reflectance,
    )

    masked = bad_band_mask | invalid_value_mask
    keep = ~masked

    return wl_nm[keep], spec[keep], keep


def spectrum_for_plot(
    wl_nm: np.ndarray,
    spec: np.ndarray,
    *,
    include_narrow_bad_bands: bool = True,
    min_reflectance: float = 0.0,
    max_reflectance: float = 1.2,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Return plotting arrays with bad/invalid bands set to NaN so they appear as gaps.

    Returns
    -------
    wl_nm : np.ndarray
        Original wavelengths.
    spec_plot : np.ndarray
        Spectrum with bad/invalid bands replaced by NaN.
    masked : np.ndarray
        Boolean mask where True means hidden in the plot.
    """
    wl_nm = _as_1d_float(wl_nm, "wl_nm")
    spec = _as_1d_float(spec, "spec")
    _check_same_shape(wl_nm, spec, "wl_nm", "spec")

    bad_band_mask = build_bad_band_mask(
        wl_nm,
        include_narrow=include_narrow_bad_bands,
    )
    invalid_value_mask = build_invalid_value_mask(
        spec,
        min_reflectance=min_reflectance,
        max_reflectance=max_reflectance,
    )

    masked = bad_band_mask | invalid_value_mask

    spec_plot = spec.copy()
    spec_plot[masked] = np.nan

    return wl_nm, spec_plot, masked


def iqr_summary(values_lo: np.ndarray, values_hi: np.ndarray) -> float:
    """
    Return median interquartile-range width across wavelengths.
    """
    values_lo = _as_1d_float(values_lo, "values_lo")
    values_hi = _as_1d_float(values_hi, "values_hi")
    _check_same_shape(values_lo, values_hi, "values_lo", "values_hi")

    width = values_hi - values_lo
    return float(np.nanmedian(width))