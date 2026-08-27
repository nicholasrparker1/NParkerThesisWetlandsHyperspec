"""Evaluate a compact classifier that can be reproduced in Earth Engine.

The existing full-spectrum PCA model is the strongest pilot model, but its PCA
transformation is awkward to deploy in Earth Engine. This script tests a
compact, evenly sampled subset of the native NEON bands with Random Forest.
Feature selection is fixed before validation, and nearby observations remain
in the same spatial fold.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import balanced_accuracy_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data/raw/NEON/WOOD_2025/WOOD_2025_labeled_full_hyperspectral_spectra.csv"
OUTPUT_DIR = ROOT / "outputs/tables/neon_wood_bare_soil"


def main() -> None:
    data = pd.read_csv(INPUT)
    bands = [column for column in data.columns if re.fullmatch(r"B\d{3}", column)]
    if len(bands) != 426:
        raise ValueError(f"Expected 426 NEON bands; found {len(bands)}")

    clear = data[data["observed_class"].isin(["soil", "vegetation", "road_built"])].copy()
    clear.reset_index(drop=True, inplace=True)
    y = (clear["observed_class"] == "soil").astype(int).to_numpy()

    # Forty-three bands retain the full spectral domain while reducing adjacent
    # redundancy and Earth Engine memory demand. Exact wavelengths remain tied
    # to the source image metadata; this file intentionally reports band IDs.
    compact_bands = bands[::10]
    if compact_bands[-1] != bands[-1]:
        compact_bands.append(bands[-1])
    x = clear[compact_bands].to_numpy(dtype=float)

    coordinates = clear[".geo"].map(lambda value: json.loads(value)["coordinates"])
    longitude = np.array([value[0] for value in coordinates], dtype=float)
    latitude = np.array([value[1] for value in coordinates], dtype=float)
    x_m = longitude * 111_320.0 * np.cos(np.deg2rad(latitude.mean()))
    y_m = latitude * 110_540.0
    groups = np.array([
        f"{x_cell}_{y_cell}"
        for x_cell, y_cell in zip(
            np.floor((x_m - x_m.min()) / 2_000).astype(int),
            np.floor((y_m - y_m.min()) / 2_000).astype(int),
        )
    ])

    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=2025)
    rows = []
    predictions = []
    for fold, (train, test) in enumerate(cv.split(x, y, groups), start=1):
        model = RandomForestClassifier(
            n_estimators=500,
            min_samples_leaf=2,
            class_weight="balanced_subsample",
            max_features="sqrt",
            random_state=2025 + fold,
            n_jobs=-1,
        )
        model.fit(x[train], y[train])
        probability = model.predict_proba(x[test])[:, 1]
        prediction = (probability >= 0.5).astype(int)
        rows.append({
            "fold": fold,
            "n_train": len(train),
            "n_test": len(test),
            "balanced_accuracy": balanced_accuracy_score(y[test], prediction),
            "precision": precision_score(y[test], prediction, zero_division=0),
            "recall": recall_score(y[test], prediction, zero_division=0),
            "roc_auc": roc_auc_score(y[test], probability),
        })
        for position, pred, prob in zip(test, prediction, probability):
            predictions.append({
                "fold": fold,
                "point_id": clear.iloc[position]["point_id"],
                "observed_class": clear.iloc[position]["observed_class"],
                "observed_soil": int(y[position]),
                "predicted_soil": int(pred),
                "soil_probability": float(prob),
                "spatial_group": groups[position],
            })

    results = pd.DataFrame(rows)
    summary = pd.DataFrame([{
        "model": "44-band Random Forest",
        "clear_labeled_points": len(clear),
        "soil_points": int(y.sum()),
        "nonsoil_points": int((1 - y).sum()),
        "spatial_folds": len(results),
        "balanced_accuracy_mean": results["balanced_accuracy"].mean(),
        "balanced_accuracy_sd": results["balanced_accuracy"].std(),
        "precision_mean": results["precision"].mean(),
        "recall_mean": results["recall"].mean(),
        "roc_auc_mean": results["roc_auc"].mean(),
        "band_count": len(compact_bands),
        "band_ids": ";".join(compact_bands),
    }])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUTPUT_DIR / "wood_2025_gee_ready_classifier_summary.csv", index=False)
    results.to_csv(OUTPUT_DIR / "wood_2025_gee_ready_classifier_folds.csv", index=False)
    pd.DataFrame(predictions).to_csv(
        OUTPUT_DIR / "wood_2025_gee_ready_classifier_predictions.csv", index=False
    )
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
