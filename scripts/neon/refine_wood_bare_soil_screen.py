"""Assess whether NDVI and MNDWI can improve the WOOD bare-soil screen.

The manually interpreted ``uncertain`` points are excluded. Performance is
estimated with repeated, stratified cross-validation so that fitted models are
not evaluated on the same points used to fit them. The original GEE rule is
retained as the version-0 baseline.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


INPUT = Path(
    "outputs/tables/neon_wood_bare_soil/"
    "wood_2025_bare_soil_validation_labels.csv"
)
OUTPUT = Path(
    "outputs/tables/neon_wood_bare_soil/"
    "wood_2025_index_model_cross_validation.csv"
)


def metrics(y_true: np.ndarray, y_pred: np.ndarray, probability=None) -> dict:
    result = {
        "accuracy": accuracy_score(y_true, y_pred),
        "balanced_accuracy": balanced_accuracy_score(y_true, y_pred),
        "bare_soil_precision": precision_score(y_true, y_pred, zero_division=0),
        "bare_soil_recall": recall_score(y_true, y_pred, zero_division=0),
    }
    if probability is not None:
        result["roc_auc"] = roc_auc_score(y_true, probability)
    return result


def main() -> None:
    data = pd.read_csv(INPUT)
    clear = data.loc[data["observed_label"] != "uncertain"].copy()
    clear["target"] = (clear["observed_label"] == "soil").astype(int)

    x = clear[["ndvi", "mndwi"]].to_numpy()
    y = clear["target"].to_numpy()

    rows = [{"model": "GEE version-0 rule", **metrics(
        y, clear["predicted_bare_soil"].astype(int).to_numpy()
    )}]

    splitter = RepeatedStratifiedKFold(
        n_splits=5, n_repeats=20, random_state=2025
    )
    fold_rows = []
    for repeat_fold, (train, test) in enumerate(splitter.split(x, y)):
        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(class_weight="balanced", random_state=2025),
        )
        model.fit(x[train], y[train])
        probability = model.predict_proba(x[test])[:, 1]
        prediction = (probability >= 0.5).astype(int)
        fold_rows.append({
            "model": "NDVI + MNDWI logistic model",
            "fold": repeat_fold,
            **metrics(y[test], prediction, probability),
        })

    folds = pd.DataFrame(fold_rows)
    summary = folds.drop(columns="fold").groupby("model").agg(["mean", "std"])
    summary.columns = [f"{metric}_{stat}" for metric, stat in summary.columns]
    summary = summary.reset_index()

    baseline = pd.DataFrame(rows)
    for column in ["accuracy", "balanced_accuracy", "bare_soil_precision",
                   "bare_soil_recall"]:
        baseline[f"{column}_mean"] = baseline.pop(column)
        baseline[f"{column}_std"] = np.nan
    baseline["roc_auc_mean"] = np.nan
    baseline["roc_auc_std"] = np.nan

    result = pd.concat([baseline, summary], ignore_index=True, sort=False)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUTPUT, index=False)
    print(result.to_string(index=False))
    print(f"\nWrote {OUTPUT}")


if __name__ == "__main__":
    main()
