"""
marmit.py

Simplified MARMIT-style bare-soil wetness fitting.

This implementation treats wet-soil reflectance as a dry-soil reference spectrum
attenuated by a thin effective surface water layer using a Beer-Lambert-style model:

    R_wet(lambda) = R_dry(lambda) * exp[-2 * alpha(lambda) * L]

where:
    R_dry(lambda)   = dry reference reflectance
    alpha(lambda)   = water absorption coefficient
    L               = effective optical water-thickness parameter

Important:
- This is a first-pass simplified MARMIT-style inversion, not the full published
  MARMIT retrieval chain.
- The fitted parameter L is interpreted here as an effective optical wetness
  parameter, not yet a fully calibrated soil-moisture-content estimate.

Key assumptions:
- input spectra are already cleaned and masked
- target pixels are bare-soil / soil-dominated
- open water pixels should NOT be fit with this model
- dry reference and wet target are broadly comparable substrate types
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class MarmitFitResult:
    thickness_um: float
    rmse: float
    r2: float
    wavelengths_nm: np.ndarray
    observed_reflectance: np.ndarray
    modeled_reflectance: np.ndarray
    dry_reflectance: np.ndarray
    valid_mask: np.ndarray
    residuals_full: np.ndarray
    thickness_grid_um: np.ndarray
    sse_grid: np.ndarray


@dataclass
class MarmitMixedFitResult:
    thickness_um: float
    wet_fraction: float
    equivalent_water_thickness_um: float
    rmse: float
    r2: float
    wavelengths_nm: np.ndarray
    observed_reflectance: np.ndarray
    modeled_reflectance: np.ndarray
    dry_reflectance: np.ndarray
    valid_mask: np.ndarray
    residuals_full: np.ndarray
    thickness_grid_um: np.ndarray
    wet_fraction_grid: np.ndarray
    sse_grid: np.ndarray


def _as_float_1d(x: np.ndarray, name: str) -> np.ndarray:
    x = np.asarray(x, dtype=float).ravel()
    if x.ndim != 1:
        raise ValueError(f"{name} must be 1D after flattening.")
    return x


def build_valid_mask(
    wavelengths_nm: np.ndarray,
    observed_reflectance: np.ndarray,
    dry_reflectance: np.ndarray,
    alpha_water: np.ndarray,
    *,
    extra_mask: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Build a valid mask for model fitting.
    True = use this wavelength in the fit.
    """
    wl = _as_float_1d(wavelengths_nm, "wavelengths_nm")
    obs = _as_float_1d(observed_reflectance, "observed_reflectance")
    dry = _as_float_1d(dry_reflectance, "dry_reflectance")
    alpha = _as_float_1d(alpha_water, "alpha_water")

    if not (len(wl) == len(obs) == len(dry) == len(alpha)):
        raise ValueError("All input vectors must have the same length.")

    valid = (
        np.isfinite(wl)
        & np.isfinite(obs)
        & np.isfinite(dry)
        & np.isfinite(alpha)
        & (obs > 0.0)
        & (dry > 0.0)
        & (obs < 1.2)
        & (dry < 1.2)
        & (alpha >= 0.0)
    )

    if extra_mask is not None:
        extra_mask = np.asarray(extra_mask, dtype=bool).ravel()
        if len(extra_mask) != len(wl):
            raise ValueError("extra_mask must have same length as wavelengths.")
        valid &= extra_mask

    return valid


def build_fit_window_mask(
    wavelengths_nm: np.ndarray,
    *,
    use_default_windows: bool = True,
) -> np.ndarray:
    """
    Build a wavelength mask for trusted fit windows.

    Default windows are chosen to avoid the strongest atmospheric absorption
    regions while retaining cleaner spectral regions often used for soil analysis.
    """
    wl = _as_float_1d(wavelengths_nm, "wavelengths_nm")
    mask = np.zeros_like(wl, dtype=bool)

    if use_default_windows:
        windows = [
            (1000.0, 1300.0),
            (1550.0, 1750.0),
            (2000.0, 2300.0),
        ]
        for lo, hi in windows:
            mask |= (wl >= lo) & (wl <= hi)
    else:
        mask[:] = True

    return mask


def model_wet_reflectance_simple(
    dry_reflectance: np.ndarray,
    alpha_water: np.ndarray,
    thickness_um: float,
) -> np.ndarray:
    """
    Simple first-pass MARMIT-style model:
        R_wet(lambda) = R_dry(lambda) * exp(-2 * alpha(lambda) * L)

    Parameters
    ----------
    dry_reflectance : 1D ndarray
        Dry reference reflectance.
    alpha_water : 1D ndarray
        Water absorption coefficient at each wavelength.
        Units must be reciprocal to thickness_um.
    thickness_um : float
        Effective optical water thickness parameter.

    Returns
    -------
    modeled_reflectance : 1D ndarray
    """
    dry = _as_float_1d(dry_reflectance, "dry_reflectance")
    alpha = _as_float_1d(alpha_water, "alpha_water")

    if len(dry) != len(alpha):
        raise ValueError("dry_reflectance and alpha_water must have same length.")

    tw = np.exp(-alpha * thickness_um)
    return dry * (tw ** 2)


def model_wet_reflectance_mixed(
    dry_reflectance: np.ndarray,
    alpha_water: np.ndarray,
    thickness_um: float,
    wet_fraction: float,
) -> np.ndarray:
    """
    MARMIT-adjacent mixed wet/dry model:
        R_model = (1 - epsilon) * R_dry + epsilon * R_dry * exp(-2 alpha L)

    epsilon is constrained conceptually to [0, 1] and represents the fraction
    of the observed surface behaving like water-film-covered soil.
    """
    dry = _as_float_1d(dry_reflectance, "dry_reflectance")
    attenuated = model_wet_reflectance_simple(dry, alpha_water, thickness_um)
    eps = float(wet_fraction)
    return (1.0 - eps) * dry + eps * attenuated


def fit_marmit_simple(
    wavelengths_nm: np.ndarray,
    observed_reflectance: np.ndarray,
    dry_reflectance: np.ndarray,
    alpha_water: np.ndarray,
    *,
    thickness_min_um: float = 0.0,
    thickness_max_um: float = 2000.0,
    n_grid: int = 2001,
    extra_mask: Optional[np.ndarray] = None,
) -> MarmitFitResult:
    """
    Fit an effective surface-water thickness by least squares.

    The fit minimizes:
        sum( R_obs(lambda) - R_model(lambda; L) )^2

    Returns
    -------
    MarmitFitResult
    """
    wl = _as_float_1d(wavelengths_nm, "wavelengths_nm")
    obs = _as_float_1d(observed_reflectance, "observed_reflectance")
    dry = _as_float_1d(dry_reflectance, "dry_reflectance")
    alpha = _as_float_1d(alpha_water, "alpha_water")

    if not (len(wl) == len(obs) == len(dry) == len(alpha)):
        raise ValueError("All input vectors must have the same length.")

    valid = build_valid_mask(
        wl,
        obs,
        dry,
        alpha,
        extra_mask=extra_mask,
    )

    if valid.sum() < 10:
        raise ValueError("Not enough valid wavelengths to fit the model.")

    wl_v = wl[valid]
    obs_v = obs[valid]
    dry_v = dry[valid]
    alpha_v = alpha[valid]

    # Simple sanity check: wet target should generally be darker than dry reference
    median_darkening = float(np.nanmedian(dry_v - obs_v))
    if median_darkening <= 0:
        print(
            "WARNING: target is not generally darker than dry reference "
            "over the fit window. The pair may be physically questionable."
        )

    grid = np.linspace(thickness_min_um, thickness_max_um, n_grid)
    sse = np.empty_like(grid)

    for i, L in enumerate(grid):
        mod = model_wet_reflectance_simple(dry_v, alpha_v, L)
        sse[i] = np.nansum((obs_v - mod) ** 2)

    best_idx = int(np.argmin(sse))
    best_L = float(grid[best_idx])

    modeled_full = np.full_like(obs, np.nan, dtype=float)
    modeled_full[valid] = model_wet_reflectance_simple(dry_v, alpha_v, best_L)

    residuals_full = np.full_like(obs, np.nan, dtype=float)
    residuals_full[valid] = obs_v - modeled_full[valid]

    resid = residuals_full[valid]
    rmse = float(np.sqrt(np.mean(resid ** 2)))

    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((obs_v - np.mean(obs_v)) ** 2))
    r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else np.nan

    return MarmitFitResult(
        thickness_um=best_L,
        rmse=rmse,
        r2=r2,
        wavelengths_nm=wl,
        observed_reflectance=obs,
        modeled_reflectance=modeled_full,
        dry_reflectance=dry,
        valid_mask=valid,
        residuals_full=residuals_full,
        thickness_grid_um=grid,
        sse_grid=sse,
    )


def fit_marmit_mixed(
    wavelengths_nm: np.ndarray,
    observed_reflectance: np.ndarray,
    dry_reflectance: np.ndarray,
    alpha_water: np.ndarray,
    *,
    thickness_min_um: float = 0.0,
    thickness_max_um: float = 2000.0,
    n_grid: int = 2001,
    extra_mask: Optional[np.ndarray] = None,
) -> MarmitMixedFitResult:
    """
    Fit effective water-film thickness and wet surface fraction.

    For each candidate L, epsilon is solved by constrained least squares:
        obs ~= dry + epsilon * (dry * exp(-2 alpha L) - dry)

    This keeps the search one-dimensional while adding the key partial-wetness
    term used by MARMIT-style models.
    """
    wl = _as_float_1d(wavelengths_nm, "wavelengths_nm")
    obs = _as_float_1d(observed_reflectance, "observed_reflectance")
    dry = _as_float_1d(dry_reflectance, "dry_reflectance")
    alpha = _as_float_1d(alpha_water, "alpha_water")

    if not (len(wl) == len(obs) == len(dry) == len(alpha)):
        raise ValueError("All input vectors must have the same length.")

    valid = build_valid_mask(
        wl,
        obs,
        dry,
        alpha,
        extra_mask=extra_mask,
    )

    if valid.sum() < 10:
        raise ValueError("Not enough valid wavelengths to fit the model.")

    obs_v = obs[valid]
    dry_v = dry[valid]
    alpha_v = alpha[valid]

    median_darkening = float(np.nanmedian(dry_v - obs_v))
    if median_darkening <= 0:
        print(
            "WARNING: target is not generally darker than dry reference "
            "over the fit window. The pair may be physically questionable."
        )

    grid = np.linspace(thickness_min_um, thickness_max_um, n_grid)
    eps_grid = np.empty_like(grid)
    sse = np.empty_like(grid)

    y = obs_v - dry_v
    for i, L in enumerate(grid):
        attenuated = model_wet_reflectance_simple(dry_v, alpha_v, float(L))
        x = attenuated - dry_v
        denom = float(np.nansum(x ** 2))
        if denom <= 0.0:
            eps = 0.0
        else:
            eps = float(np.nansum(x * y) / denom)
        eps = float(np.clip(eps, 0.0, 1.0))
        eps_grid[i] = eps
        mod = dry_v + eps * x
        sse[i] = np.nansum((obs_v - mod) ** 2)

    best_idx = int(np.argmin(sse))
    best_L = float(grid[best_idx])
    best_eps = float(eps_grid[best_idx])

    modeled_full = np.full_like(obs, np.nan, dtype=float)
    modeled_full[valid] = model_wet_reflectance_mixed(
        dry_v,
        alpha_v,
        best_L,
        best_eps,
    )

    residuals_full = np.full_like(obs, np.nan, dtype=float)
    residuals_full[valid] = obs_v - modeled_full[valid]

    resid = residuals_full[valid]
    rmse = float(np.sqrt(np.mean(resid ** 2)))

    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((obs_v - np.mean(obs_v)) ** 2))
    r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else np.nan

    return MarmitMixedFitResult(
        thickness_um=best_L,
        wet_fraction=best_eps,
        equivalent_water_thickness_um=best_L * best_eps,
        rmse=rmse,
        r2=r2,
        wavelengths_nm=wl,
        observed_reflectance=obs,
        modeled_reflectance=modeled_full,
        dry_reflectance=dry,
        valid_mask=valid,
        residuals_full=residuals_full,
        thickness_grid_um=grid,
        wet_fraction_grid=eps_grid,
        sse_grid=sse,
    )


def interpolate_alpha_to_wavelengths(
    wavelengths_nm: np.ndarray,
    alpha_wavelengths_nm: np.ndarray,
    alpha_values: np.ndarray,
) -> np.ndarray:
    """
    Interpolate tabulated water absorption coefficients onto target wavelengths.

    Outside the tabulated range, returns NaN.
    """
    wl = _as_float_1d(wavelengths_nm, "wavelengths_nm")
    awl = _as_float_1d(alpha_wavelengths_nm, "alpha_wavelengths_nm")
    aval = _as_float_1d(alpha_values, "alpha_values")

    if len(awl) != len(aval):
        raise ValueError("alpha_wavelengths_nm and alpha_values must have same length.")

    order = np.argsort(awl)
    awl = awl[order]
    aval = aval[order]

    out = np.interp(wl, awl, aval, left=np.nan, right=np.nan)
    return out
