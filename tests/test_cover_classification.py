import numpy as np

from src.models.cover_classification import compute_cover_features


WAVELENGTHS_NM = np.array([560.0, 665.0, 860.0, 1640.0, 2200.0])


def test_bare_soil_candidate():
    result = compute_cover_features(
        WAVELENGTHS_NM,
        np.array([0.16, 0.18, 0.20, 0.25, 0.22]),
        include_narrow_bad_bands=False,
    )
    assert result.cover_class == "bare_soil_candidate"
    assert result.usable_for_soil_retrieval is True


def test_green_vegetation_is_rejected():
    result = compute_cover_features(
        WAVELENGTHS_NM,
        np.array([0.12, 0.05, 0.50, 0.22, 0.14]),
        include_narrow_bad_bands=False,
    )
    assert result.cover_class == "vegetation"
    assert result.usable_for_soil_retrieval is False


def test_open_water_is_rejected():
    result = compute_cover_features(
        WAVELENGTHS_NM,
        np.array([0.08, 0.04, 0.02, 0.01, 0.005]),
        include_narrow_bad_bands=False,
    )
    assert result.cover_class == "water"
    assert result.usable_for_soil_retrieval is False


def test_shadow_is_rejected():
    result = compute_cover_features(
        WAVELENGTHS_NM,
        np.full(5, 0.01),
        include_narrow_bad_bands=False,
    )
    assert result.cover_class == "shadow_or_low_signal"
    assert result.usable_for_soil_retrieval is False
