from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.preprocess import build_bad_band_mask, build_invalid_value_mask


@dataclass(frozen=True)
class SpectralWetnessFeatures:
    r_860: float
    r_1240: float
    r_1640: float
    r_2200: float
    nd_860_1640: float
    nd_1240_1640: float
    swir_darkness: float
    swir_ratio_1640_860: float
    continuum_depth_2200: float


def _as_1d_float(x: np.ndarray, name: str) -> np.ndarray:
    out = np.asarray(x, dtype=float).ravel()
    if out.ndim != 1:
        raise ValueError(f"{name} must be 1D.")
    return out


def _nearest_clean_value(
    wavelengths_nm: np.ndarray,
    reflectance: np.ndarray,
    target_nm: float,
    valid_mask: np.ndarray,
) -> float:
    candidates = np.where(valid_mask & np.isfinite(reflectance))[0]
    if candidates.size == 0:
        return float("nan")
    idx = candidates[int(np.argmin(np.abs(wavelengths_nm[candidates] - target_nm)))]
    return float(reflectance[idx])


def _safe_nd(a: float, b: float) -> float:
    denom = a + b
    if not np.isfinite(denom) or abs(denom) < 1e-12:
        return float("nan")
    return float((a - b) / denom)


def _safe_ratio(num: float, den: float) -> float:
    if not np.isfinite(den) or abs(den) < 1e-12:
        return float("nan")
    return float(num / den)


def _median_window(
    wavelengths_nm: np.ndarray,
    reflectance: np.ndarray,
    lo_nm: float,
    hi_nm: float,
    valid_mask: np.ndarray,
) -> float:
    mask = valid_mask & (wavelengths_nm >= lo_nm) & (wavelengths_nm <= hi_nm)
    vals = reflectance[mask]
    if not np.any(np.isfinite(vals)):
        return float("nan")
    return float(np.nanmedian(vals))


def _continuum_depth(
    wavelengths_nm: np.ndarray,
    reflectance: np.ndarray,
    center_nm: float,
    left_nm: float,
    right_nm: float,
    valid_mask: np.ndarray,
) -> float:
    left = _nearest_clean_value(wavelengths_nm, reflectance, left_nm, valid_mask)
    center = _nearest_clean_value(wavelengths_nm, reflectance, center_nm, valid_mask)
    right = _nearest_clean_value(wavelengths_nm, reflectance, right_nm, valid_mask)

    if not (np.isfinite(left) and np.isfinite(center) and np.isfinite(right)):
        return float("nan")

    frac = (center_nm - left_nm) / (right_nm - left_nm)
    continuum = left + frac * (right - left)
    if not np.isfinite(continuum) or continuum <= 0.0:
        return float("nan")

    return float(1.0 - center / continuum)


def build_clean_valid_mask(
    wavelengths_nm: np.ndarray,
    reflectance: np.ndarray,
    *,
    include_narrow_bad_bands: bool = True,
) -> np.ndarray:
    wl = _as_1d_float(wavelengths_nm, "wavelengths_nm")
    spec = _as_1d_float(reflectance, "reflectance")
    if wl.shape != spec.shape:
        raise ValueError("wavelengths_nm and reflectance must have the same shape.")

    bad = build_bad_band_mask(wl, include_narrow=include_narrow_bad_bands)
    invalid = build_invalid_value_mask(spec, min_reflectance=0.0, max_reflectance=1.2)
    return ~(bad | invalid)


def extract_spectral_wetness_features(
    wavelengths_nm: np.ndarray,
    reflectance: np.ndarray,
    *,
    include_narrow_bad_bands: bool = True,
) -> SpectralWetnessFeatures:
    """
    Extract no-calibration spectral wetness proxies.

    These are relative indicators, not calibrated volumetric soil moisture.
    For bare soil, wetter surfaces generally darken in SWIR and increase
    normalized NIR/SWIR contrast.
    """
    wl = _as_1d_float(wavelengths_nm, "wavelengths_nm")
    spec = _as_1d_float(reflectance, "reflectance")
    valid = build_clean_valid_mask(
        wl,
        spec,
        include_narrow_bad_bands=include_narrow_bad_bands,
    )

    r_860 = _nearest_clean_value(wl, spec, 860.0, valid)
    r_1240 = _nearest_clean_value(wl, spec, 1240.0, valid)
    r_1640 = _nearest_clean_value(wl, spec, 1640.0, valid)
    r_2200 = _nearest_clean_value(wl, spec, 2200.0, valid)

    swir_med = np.nanmedian(
        [
            _median_window(wl, spec, 1550.0, 1750.0, valid),
            _median_window(wl, spec, 2050.0, 2300.0, valid),
        ]
    )

    return SpectralWetnessFeatures(
        r_860=r_860,
        r_1240=r_1240,
        r_1640=r_1640,
        r_2200=r_2200,
        nd_860_1640=_safe_nd(r_860, r_1640),
        nd_1240_1640=_safe_nd(r_1240, r_1640),
        swir_darkness=float(-swir_med) if np.isfinite(swir_med) else float("nan"),
        swir_ratio_1640_860=_safe_ratio(r_1640, r_860),
        continuum_depth_2200=_continuum_depth(
            wl,
            spec,
            center_nm=2200.0,
            left_nm=2050.0,
            right_nm=2350.0,
            valid_mask=valid,
        ),
    )


def features_to_dict(features: SpectralWetnessFeatures) -> dict[str, float]:
    return {
        "r_860": features.r_860,
        "r_1240": features.r_1240,
        "r_1640": features.r_1640,
        "r_2200": features.r_2200,
        "nd_860_1640": features.nd_860_1640,
        "nd_1240_1640": features.nd_1240_1640,
        "swir_darkness": features.swir_darkness,
        "swir_ratio_1640_860": features.swir_ratio_1640_860,
        "continuum_depth_2200": features.continuum_depth_2200,
    }
