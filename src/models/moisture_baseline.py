from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


@dataclass
class BaselineFitResult:
    feature_names: list[str]
    coefficients: np.ndarray
    intercept: float
    fitted_model: Pipeline


def _as_1d(x: np.ndarray, name: str) -> np.ndarray:
    x = np.asarray(x, dtype=float).ravel()
    if x.ndim != 1:
        raise ValueError(f"{name} must be 1D.")
    return x


def _as_2d(x: np.ndarray, name: str) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    if x.ndim != 2:
        raise ValueError(f"{name} must be 2D.")
    return x


def nearest_band_index(wavelengths_nm: np.ndarray, target_nm: float) -> int:
    wl = _as_1d(wavelengths_nm, "wavelengths_nm")
    return int(np.argmin(np.abs(wl - target_nm)))


def build_band_mask(wavelengths_nm: np.ndarray) -> np.ndarray:
    wl = _as_1d(wavelengths_nm, "wavelengths_nm")
    mask = np.isfinite(wl)

    # remove strongest atmospheric regions
    bad_ranges = [
        (920.0, 960.0),
        (1110.0, 1145.0),
        (1340.0, 1450.0),
        (1800.0, 1950.0),
    ]
    for lo, hi in bad_ranges:
        mask &= ~((wl >= lo) & (wl <= hi))

    return mask


def extract_simple_features(
    wavelengths_nm: np.ndarray,
    X_spectra: np.ndarray,
) -> tuple[np.ndarray, list[str]]:
    """
    Very simple first-pass features that avoid the strongest masked atmospheric regions.
    This is only for a prototype with very few points.
    """
    wl = _as_1d(wavelengths_nm, "wavelengths_nm")
    X = _as_2d(X_spectra, "X_spectra")

    if X.shape[1] != len(wl):
        raise ValueError("X_spectra second dimension must match wavelengths_nm length.")

    mask = build_band_mask(wl)
    wl_use = wl[mask]
    X_use = X[:, mask]

    target_bands = [1650.0, 1730.0, 2200.0]
    feat_cols = []
    feat_names = []

    for target in target_bands:
        idx = nearest_band_index(wl_use, target)
        feat_cols.append(X_use[:, idx])
        feat_names.append(f"R_{int(round(wl_use[idx]))}")

    features = np.column_stack(feat_cols)
    return features, feat_names


def fit_baseline_model(
    X_features: np.ndarray,
    y_moisture: np.ndarray,
    feature_names: list[str],
) -> BaselineFitResult:
    X = _as_2d(X_features, "X_features")
    y = _as_1d(y_moisture, "y_moisture")

    if X.shape[0] != len(y):
        raise ValueError("X_features rows must match y_moisture length.")

    model = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("regressor", LinearRegression()),
    ])

    model.fit(X, y)

    reg = model.named_steps["regressor"]

    return BaselineFitResult(
        feature_names=feature_names,
        coefficients=np.asarray(reg.coef_, dtype=float),
        intercept=float(reg.intercept_),
        fitted_model=model,
    )