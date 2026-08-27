"""Evaluate whether full NEON spectra improve the WOOD bare-soil screen.

This is an exploratory pilot. Only manually assigned clear labels (soil versus
vegetation/road_built) are used; uncertain observations are excluded. Model
selection is nested inside repeated stratified cross-validation so test folds
do not influence PCA dimension or logistic-regression regularization. A
spatial-block test is also reported to reduce optimism from nearby pixels.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import (
    GridSearchCV,
    RepeatedStratifiedKFold,
    StratifiedGroupKFold,
    StratifiedKFold,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data/raw/NEON/WOOD_2025/WOOD_2025_labeled_full_hyperspectral_spectra.csv"
OUTPUT_DIR = ROOT / "outputs/tables/neon_wood_bare_soil"
SUMMARY_OUTPUT = OUTPUT_DIR / "wood_2025_full_spectra_cross_validation.csv"
FOLD_OUTPUT = OUTPUT_DIR / "wood_2025_full_spectra_cv_folds.csv"
PREDICTION_OUTPUT = OUTPUT_DIR / "wood_2025_full_spectra_oof_predictions.csv"


def metrics(y_true: np.ndarray, y_pred: np.ndarray, y_prob: np.ndarray) -> dict[str, float]:
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "balanced_accuracy": balanced_accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "roc_auc": roc_auc_score(y_true, y_prob),
    }


def main() -> None:
    data = pd.read_csv(INPUT)
    band_columns = [column for column in data.columns if re.fullmatch(r"B\d{3}", column)]
    if len(data) != 150 or len(band_columns) != 426:
        raise ValueError(
            f"Expected 150 rows and 426 bands; found {len(data)} and {len(band_columns)}"
        )

    clear = data[data["observed_class"].isin(["soil", "vegetation", "road_built"])].copy()
    clear.reset_index(drop=True, inplace=True)
    y = (clear["observed_class"] == "soil").astype(int).to_numpy()
    x_index = clear[["ndvi", "mndwi"]].to_numpy(dtype=float)
    x_spectra = clear[band_columns].to_numpy(dtype=float)

    coordinates = clear[".geo"].map(lambda value: json.loads(value)["coordinates"])
    longitude = np.array([value[0] for value in coordinates], dtype=float)
    latitude = np.array([value[1] for value in coordinates], dtype=float)

    # Approximate 2-km cells. They are used only to keep nearby pixels in the
    # same validation fold, not for distance calculations or reported geometry.
    x_m = longitude * 111_320.0 * np.cos(np.deg2rad(latitude.mean()))
    y_m = latitude * 110_540.0
    x_block = np.floor((x_m - x_m.min()) / 2_000).astype(int)
    y_block = np.floor((y_m - y_m.min()) / 2_000).astype(int)
    spatial_groups = np.array([f"{x}_{y}" for x, y in zip(x_block, y_block)])

    random_cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=5, random_state=2025)
    spatial_cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=2025)
    split_sets = [
        ("repeated_random", random_cv.split(x_spectra, y)),
        ("spatial_block", spatial_cv.split(x_spectra, y, groups=spatial_groups)),
    ]

    rows: list[dict[str, float | int | str]] = []
    prediction_rows: list[dict[str, float | int | str]] = []

    for validation, splits in split_sets:
        for fold, (train, test) in enumerate(splits, start=1):
            inner = StratifiedKFold(n_splits=4, shuffle=True, random_state=10_000 + fold)

            index_search = GridSearchCV(
                Pipeline([
                    ("scale", StandardScaler()),
                    ("logistic", LogisticRegression(max_iter=5000, class_weight="balanced")),
                ]),
                {"logistic__C": [0.01, 0.1, 1.0, 10.0, 100.0]},
                scoring="balanced_accuracy",
                cv=inner,
            )
            index_search.fit(x_index[train], y[train])

            spectral_search = GridSearchCV(
                Pipeline([
                    ("scale", StandardScaler()),
                    ("pca", PCA()),
                    ("logistic", LogisticRegression(max_iter=5000, class_weight="balanced")),
                ]),
                {
                    "pca__n_components": [3, 5, 10, 15, 20],
                    "logistic__C": [0.01, 0.1, 1.0, 10.0],
                },
                scoring="balanced_accuracy",
                cv=inner,
            )
            spectral_search.fit(x_spectra[train], y[train])

            candidates = [
                ("NDVI + MNDWI", index_search, x_index),
                ("Full spectra: tuned PCA + logistic", spectral_search, x_spectra),
            ]
            for name, search, features in candidates:
                probability = search.predict_proba(features[test])[:, 1]
                prediction = (probability >= 0.5).astype(int)
                row: dict[str, float | int | str] = {
                    "validation": validation,
                    "model": name,
                    "fold": fold,
                    "n_train": len(train),
                    "n_test": len(test),
                    **metrics(y[test], prediction, probability),
                }
                row["selected_components"] = (
                    search.best_params_["pca__n_components"]
                    if name.startswith("Full spectra")
                    else np.nan
                )
                rows.append(row)

                for position, probability_value, prediction_value in zip(
                    test, probability, prediction
                ):
                    prediction_rows.append({
                        "validation": validation,
                        "model": name,
                        "fold": fold,
                        "point_id": clear.iloc[position]["point_id"],
                        "observed_class": clear.iloc[position]["observed_class"],
                        "observed_soil": int(y[position]),
                        "predicted_soil": int(prediction_value),
                        "soil_probability": float(probability_value),
                        "longitude": longitude[position],
                        "latitude": latitude[position],
                        "spatial_group": spatial_groups[position],
                    })

    fold_results = pd.DataFrame(rows)
    summary = (
        fold_results.groupby(["validation", "model"], as_index=False)
        .agg(
            folds=("fold", "count"),
            accuracy_mean=("accuracy", "mean"),
            accuracy_sd=("accuracy", "std"),
            balanced_accuracy_mean=("balanced_accuracy", "mean"),
            balanced_accuracy_sd=("balanced_accuracy", "std"),
            precision_mean=("precision", "mean"),
            recall_mean=("recall", "mean"),
            roc_auc_mean=("roc_auc", "mean"),
        )
    )
    summary.insert(2, "clear_labeled_points", len(clear))
    summary.insert(3, "soil_points", int(y.sum()))
    summary.insert(4, "nonsoil_points", int((1 - y).sum()))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_OUTPUT, index=False)
    fold_results.to_csv(FOLD_OUTPUT, index=False)
    pd.DataFrame(prediction_rows).to_csv(PREDICTION_OUTPUT, index=False)

    print(summary.to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    print(f"\nWrote {SUMMARY_OUTPUT}")
    print(f"Wrote {FOLD_OUTPUT}")
    print(f"Wrote {PREDICTION_OUTPUT}")


if __name__ == "__main__":
    main()

