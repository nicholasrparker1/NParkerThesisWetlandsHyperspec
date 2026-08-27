from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.preprocess import build_bad_band_mask, build_invalid_value_mask


@dataclass(frozen=True)
class CoverFeatures:
    green: float
    red: float
    nir: float
    swir1: float
    swir2: float
    visible_mean: float
    nir_swir_mean: float
    ndvi: float
    ndwi: float
    mndwi: float
    ndmi: float
    nbr2: float
    soil_likelihood: float
    vegetation_likelihood: float
    water_likelihood: float
    cover_class: str
    usable_for_soil_retrieval: bool
    quality_flag: str


def _as_1d_float(x: np.ndarray, name: str) -> np.ndarray:
    out = np.asarray(x, dtype=float).ravel()
    if out.ndim != 1:
        raise ValueError(f"{name} must be 1D.")
    return out


def _safe_normalized_difference(a: float, b: float) -> float:
    denom = a + b
    if not np.isfinite(denom) or abs(denom) < 1e-12:
        return float("nan")
    return float((a - b) / denom)


def _clamp01(x: float) -> float:
    if not np.isfinite(x):
        return float("nan")
    return float(np.clip(x, 0.0, 1.0))


def _nearest_value(
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


def _median_range(
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


def build_cover_valid_mask(
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


def compute_cover_features(
    wavelengths_nm: np.ndarray,
    reflectance: np.ndarray,
    *,
    include_narrow_bad_bands: bool = True,
) -> CoverFeatures:
    """
    Compute simple cover diagnostics for screening bare-soil retrieval points.

    The thresholds are intentionally conservative and meant for point/ROI review,
    not final land-cover mapping.
    """
    wl = _as_1d_float(wavelengths_nm, "wavelengths_nm")
    spec = _as_1d_float(reflectance, "reflectance")
    valid = build_cover_valid_mask(
        wl,
        spec,
        include_narrow_bad_bands=include_narrow_bad_bands,
    )

    green = _nearest_value(wl, spec, 560.0, valid)
    red = _nearest_value(wl, spec, 665.0, valid)
    nir = _nearest_value(wl, spec, 860.0, valid)
    swir1 = _nearest_value(wl, spec, 1640.0, valid)
    swir2 = _nearest_value(wl, spec, 2200.0, valid)
    visible_mean = _median_range(wl, spec, 450.0, 700.0, valid)
    nir_swir_mean = _median_range(wl, spec, 800.0, 2300.0, valid)

    ndvi = _safe_normalized_difference(nir, red)
    ndwi = _safe_normalized_difference(green, nir)
    mndwi = _safe_normalized_difference(green, swir1)
    ndmi = _safe_normalized_difference(nir, swir1)
    nbr2 = _safe_normalized_difference(swir1, swir2)

    cover_class, usable, quality = classify_cover(
        ndvi=ndvi,
        ndwi=ndwi,
        mndwi=mndwi,
        ndmi=ndmi,
        red=red,
        nir=nir,
        swir1=swir1,
        visible_mean=visible_mean,
        nir_swir_mean=nir_swir_mean,
    )

    vegetation_likelihood = _vegetation_likelihood(ndvi)
    water_likelihood = _water_likelihood(ndwi, mndwi, nir, swir1)
    soil_likelihood = _soil_likelihood(
        vegetation_likelihood=vegetation_likelihood,
        water_likelihood=water_likelihood,
        ndvi=ndvi,
        nir_swir_mean=nir_swir_mean,
    )

    return CoverFeatures(
        green=green,
        red=red,
        nir=nir,
        swir1=swir1,
        swir2=swir2,
        visible_mean=visible_mean,
        nir_swir_mean=nir_swir_mean,
        ndvi=ndvi,
        ndwi=ndwi,
        mndwi=mndwi,
        ndmi=ndmi,
        nbr2=nbr2,
        soil_likelihood=soil_likelihood,
        vegetation_likelihood=vegetation_likelihood,
        water_likelihood=water_likelihood,
        cover_class=cover_class,
        usable_for_soil_retrieval=usable,
        quality_flag=quality,
    )


def classify_cover(
    *,
    ndvi: float,
    ndwi: float,
    mndwi: float,
    ndmi: float,
    red: float,
    nir: float,
    swir1: float,
    visible_mean: float,
    nir_swir_mean: float,
) -> tuple[str, bool, str]:
    if not np.isfinite(nir_swir_mean) or not np.isfinite(visible_mean):
        return "unknown", False, "insufficient_valid_reflectance"

    if nir_swir_mean < 0.015 and visible_mean < 0.025:
        return "shadow_or_low_signal", False, "very_low_reflectance"

    likely_water = (
        (np.isfinite(mndwi) and mndwi > 0.25 and np.isfinite(nir) and nir < 0.06)
        or (np.isfinite(ndwi) and ndwi > 0.20 and np.isfinite(swir1) and swir1 < 0.04)
    )
    if likely_water:
        return "water", False, "water_like_indices"

    if np.isfinite(ndvi) and ndvi > 0.35:
        return "vegetation", False, "high_ndvi"

    if np.isfinite(ndvi) and 0.18 < ndvi <= 0.35:
        return "mixed_vegetation", False, "moderate_ndvi"

    soil_like = (
        np.isfinite(ndvi)
        and ndvi <= 0.18
        and np.isfinite(swir1)
        and swir1 >= 0.015
        and not likely_water
    )
    if soil_like:
        if np.isfinite(ndvi) and ndvi < -0.05:
            return "mixed_or_uncertain", False, "negative_ndvi_not_water"
        return "bare_soil_candidate", True, "soil_like_indices"

    return "mixed_or_uncertain", False, "thresholds_inconclusive"


def _vegetation_likelihood(ndvi: float) -> float:
    if not np.isfinite(ndvi):
        return float("nan")
    return _clamp01((ndvi - 0.10) / 0.35)


def _water_likelihood(ndwi: float, mndwi: float, nir: float, swir1: float) -> float:
    vals = []
    if np.isfinite(ndwi):
        vals.append(_clamp01((ndwi + 0.05) / 0.45))
    if np.isfinite(mndwi):
        vals.append(_clamp01((mndwi + 0.05) / 0.45))
    if np.isfinite(nir):
        vals.append(_clamp01((0.08 - nir) / 0.08))
    if np.isfinite(swir1):
        vals.append(_clamp01((0.05 - swir1) / 0.05))
    if not vals:
        return float("nan")
    return float(np.nanmean(vals))


def _soil_likelihood(
    *,
    vegetation_likelihood: float,
    water_likelihood: float,
    ndvi: float,
    nir_swir_mean: float,
) -> float:
    if not np.isfinite(nir_swir_mean):
        return float("nan")
    base = 1.0
    if np.isfinite(vegetation_likelihood):
        base -= 0.65 * vegetation_likelihood
    if np.isfinite(water_likelihood):
        base -= 0.65 * water_likelihood
    if np.isfinite(ndvi):
        base -= 0.25 * _clamp01(abs(ndvi - 0.08) / 0.35)
    if nir_swir_mean < 0.015:
        base -= 0.35
    return _clamp01(base)


def cover_features_to_dict(features: CoverFeatures) -> dict[str, object]:
    return {
        "green": features.green,
        "red": features.red,
        "nir": features.nir,
        "swir1": features.swir1,
        "swir2": features.swir2,
        "visible_mean": features.visible_mean,
        "nir_swir_mean": features.nir_swir_mean,
        "ndvi": features.ndvi,
        "ndwi": features.ndwi,
        "mndwi": features.mndwi,
        "ndmi": features.ndmi,
        "nbr2": features.nbr2,
        "soil_likelihood": features.soil_likelihood,
        "vegetation_likelihood": features.vegetation_likelihood,
        "water_likelihood": features.water_likelihood,
        "cover_class": features.cover_class,
        "usable_for_soil_retrieval": features.usable_for_soil_retrieval,
        "quality_flag": features.quality_flag,
    }
