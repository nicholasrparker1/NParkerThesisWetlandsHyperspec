"""Evaluate the manually labeled WOOD 2025 bare-soil screening pilot.

The validation sample was balanced by the version-0 prediction (75 predicted
negative and 75 predicted positive). Consequently, the reported metrics test
screening discrimination but must not be interpreted as landscape prevalence.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import pyogrio
import seaborn as sns
from sklearn.metrics import confusion_matrix


DEFAULT_GDB = Path(
    r"C:\Users\NI34189\OneDrive - MIT Lincoln Laboratory\Documents\MIT MS Stuff"
    r"\KSSL\KSSLHydricEvidence\KSSLHydricEvidence\KSSLHydricEvidence.gdb"
)
DEFAULT_LAYER = "WOOD_2025_balanced_bare_soil_validation_label_template_XYTableToPoint"
TABLE_DIR = Path("outputs/tables/neon_wood_bare_soil")
FIGURE_DIR = Path("outputs/figures/neon_wood_bare_soil")

LABEL_MAP = {
    "soil": "soil",
    "vegetation": "vegetation",
    "road_built": "road or built surface",
    "uncertain": "uncertain",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gdb", type=Path, default=DEFAULT_GDB)
    parser.add_argument("--layer", default=DEFAULT_LAYER)
    return parser.parse_args()


def safe_divide(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else float("nan")


def main() -> None:
    args = parse_args()
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)

    frame = pyogrio.read_dataframe(args.gdb, layer=args.layer)
    required = {
        "point_id", "longitude", "latitude", "predicted_bare_soil",
        "ndvi", "mndwi", "observed_class", "confidence", "notes",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing required fields: {sorted(missing)}")

    data = frame[list(required)].copy()
    data["observed_class"] = (
        data["observed_class"].astype("string").str.strip().str.lower()
    )
    data["confidence"] = data["confidence"].astype("string").str.strip().str.lower()
    invalid = sorted(set(data["observed_class"].dropna()) - set(LABEL_MAP))
    if invalid:
        raise ValueError(f"Unexpected observed labels: {invalid}")
    if data["observed_class"].isna().any():
        raise ValueError("The validation table still contains unlabeled records.")

    data["observed_label"] = data["observed_class"].map(LABEL_MAP)
    data = data.sort_values("point_id")
    data.to_csv(TABLE_DIR / "wood_2025_bare_soil_validation_labels.csv", index=False)

    label_counts = (
        data.groupby(["observed_label", "confidence"], dropna=False)
        .size().rename("count").reset_index()
    )
    label_counts.to_csv(TABLE_DIR / "wood_2025_label_summary.csv", index=False)

    clear = data[data["observed_class"] != "uncertain"].copy()
    clear["observed_bare_soil"] = (clear["observed_class"] == "soil").astype(int)
    tn, fp, fn, tp = confusion_matrix(
        clear["observed_bare_soil"], clear["predicted_bare_soil"], labels=[0, 1]
    ).ravel()

    metrics = pd.DataFrame(
        [
            ("Total labeled points", len(data)),
            ("Clear-label evaluation points", len(clear)),
            ("Uncertain points", (data["observed_class"] == "uncertain").sum()),
            ("Uncertain fraction", (data["observed_class"] == "uncertain").mean()),
            ("True positives", tp), ("False positives", fp),
            ("True negatives", tn), ("False negatives", fn),
            ("Accuracy", safe_divide(tp + tn, len(clear))),
            ("Bare-soil precision", safe_divide(tp, tp + fp)),
            ("Bare-soil recall", safe_divide(tp, tp + fn)),
            ("Non-soil specificity", safe_divide(tn, tn + fp)),
            ("Balanced accuracy", (
                safe_divide(tp, tp + fn) + safe_divide(tn, tn + fp)
            ) / 2),
        ],
        columns=["metric", "value"],
    )
    metrics.to_csv(TABLE_DIR / "wood_2025_baseline_metrics.csv", index=False)

    counts = pd.crosstab(
        data["observed_label"], data["predicted_bare_soil"],
    ).reindex(index=list(LABEL_MAP.values()), columns=[0, 1], fill_value=0)
    counts.columns = ["predicted_non_soil", "predicted_bare_soil"]
    counts.to_csv(TABLE_DIR / "wood_2025_prediction_by_observed_class.csv")

    sns.set_theme(style="white", context="talk", font="Arial")
    matrix = pd.DataFrame(
        [[tn, fp], [fn, tp]],
        index=["Observed non-soil", "Observed bare soil"],
        columns=["Predicted non-soil", "Predicted bare soil"],
    )
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.8), gridspec_kw={"width_ratios": [1, 1.18]})
    sns.heatmap(matrix, annot=True, fmt="d", cmap="Blues", cbar=False,
                linewidths=1.5, linecolor="white", ax=axes[0], annot_kws={"size": 20})
    axes[0].set_title("Clear-label confusion matrix", weight="bold", pad=14)
    axes[0].set_xlabel("")
    axes[0].set_ylabel("")

    class_colors = ["#2A9D8F", "#6A994E", "#8D6E63", "#A7A9AC"]
    ordered = ["soil", "vegetation", "road or built surface", "uncertain"]
    totals = data["observed_label"].value_counts().reindex(ordered)
    axes[1].barh(ordered[::-1], totals[::-1], color=class_colors[::-1])
    for i, value in enumerate(totals[::-1]):
        axes[1].text(value + 1, i, str(value), va="center", fontsize=14)
    axes[1].set_xlim(0, max(totals) * 1.18)
    axes[1].set_title("Manual interpretation outcomes", weight="bold", pad=14)
    axes[1].set_xlabel("Number of validation points")
    axes[1].spines[["top", "right", "left"]].set_visible(False)
    axes[1].grid(axis="x", alpha=0.25)
    axes[1].grid(axis="y", visible=False)

    fig.suptitle("WOOD 2025 exposed-soil screen: version-0 pilot validation",
                 fontsize=20, weight="bold", y=1.02)
    fig.text(
        0.5, -0.035,
        "Balanced sample: 75 predicted bare-soil and 75 predicted non-soil points. "
        "Uncertain labels are excluded from the confusion matrix.",
        ha="center", fontsize=11, color="#4D5D6C",
    )
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / "wood_2025_bare_soil_validation.png",
                dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    print(metrics.to_string(index=False))
    print(f"\nWrote tables to {TABLE_DIR} and figure to {FIGURE_DIR}.")


if __name__ == "__main__":
    main()
