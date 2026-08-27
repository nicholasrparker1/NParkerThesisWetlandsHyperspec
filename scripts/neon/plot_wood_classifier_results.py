"""Create publication-ready WOOD bare-soil classifier pilot figures."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
TABLE_DIR = ROOT / "outputs/tables/neon_wood_bare_soil"
FIGURE_DIR = ROOT / "outputs/figures/neon_wood_bare_soil"
SUMMARY = TABLE_DIR / "wood_2025_full_spectra_cross_validation.csv"
PREDICTIONS = TABLE_DIR / "wood_2025_full_spectra_oof_predictions.csv"

TEAL = "#147D82"
GOLD = "#D9A33E"
DARK = "#183247"
GRID = "#D7E0E5"


def main() -> None:
    summary = pd.read_csv(SUMMARY)
    predictions = pd.read_csv(PREDICTIONS)
    spatial = summary[summary["validation"].eq("spatial_block")].copy()
    order = ["NDVI + MNDWI", "Full spectra: tuned PCA + logistic"]
    spatial["model"] = pd.Categorical(spatial["model"], categories=order, ordered=True)
    spatial.sort_values("model", inplace=True)

    detail = predictions[predictions["validation"].eq("spatial_block")].copy()
    detail["error"] = detail["observed_soil"].ne(detail["predicted_soil"])
    error_table = (
        detail.groupby(["model", "observed_class"])["error"]
        .sum()
        .unstack(fill_value=0)
        .reindex(order)
    )
    for column in ["soil", "vegetation", "road_built"]:
        if column not in error_table:
            error_table[column] = 0
    error_table = error_table[["soil", "vegetation", "road_built"]]

    plt.rcParams.update({
        "font.family": "Arial",
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.labelsize": 11,
        "figure.titlesize": 17,
    })
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 5.2), gridspec_kw={"width_ratios": [1.05, 1]})
    fig.suptitle("Full NEON spectra improve exposed-soil screening at WOOD", color=DARK, weight="bold")

    labels = ["NDVI + MNDWI", "426-band spectra\n(tuned PCA + logistic)"]
    x = np.arange(2)
    width = 0.34
    axes[0].bar(
        x - width / 2,
        spatial["balanced_accuracy_mean"],
        width,
        yerr=spatial["balanced_accuracy_sd"],
        color=[GOLD, TEAL],
        capsize=4,
        label="Balanced accuracy",
    )
    axes[0].bar(
        x + width / 2,
        spatial["roc_auc_mean"],
        width,
        color=[GOLD, TEAL],
        alpha=0.48,
        label="ROC AUC",
    )
    axes[0].set_xticks(x, labels)
    axes[0].set_ylim(0, 1.08)
    axes[0].set_ylabel("Spatial-block validation score")
    axes[0].set_title("Performance on held-out 2-km spatial blocks", weight="bold")
    axes[0].grid(axis="y", color=GRID, linewidth=0.8)
    axes[0].set_axisbelow(True)
    axes[0].legend(frameon=False, loc="lower right")
    for index, value in enumerate(spatial["balanced_accuracy_mean"]):
        axes[0].text(index - width / 2, value + 0.055, f"{value:.2f}", ha="center", weight="bold")

    colors = ["#4C78A8", "#72B7B2", "#E45756"]
    bottom = np.zeros(2)
    class_labels = ["True soil missed", "Vegetation false positive", "Road/built false positive"]
    for column, color, label in zip(error_table.columns, colors, class_labels):
        values = error_table[column].to_numpy()
        axes[1].bar(x, values, bottom=bottom, color=color, label=label)
        for index, value in enumerate(values):
            if value:
                axes[1].text(index, bottom[index] + value / 2, str(int(value)), ha="center", va="center", color="white", weight="bold")
        bottom += values
    axes[1].set_xticks(x, labels)
    axes[1].set_ylabel("Misclassified validation points (n)")
    axes[1].set_title("Error composition explains the improvement", weight="bold")
    axes[1].grid(axis="y", color=GRID, linewidth=0.8)
    axes[1].set_axisbelow(True)
    axes[1].legend(frameon=False, loc="upper right")

    fig.text(
        0.5,
        0.015,
        "Pilot data: 82 clear manual labels (26 soil; 56 non-soil). Uncertain labels were excluded. Results are site-specific, not final transfer validation.",
        ha="center",
        color="#526572",
        fontsize=10,
    )
    fig.tight_layout(rect=(0, 0.055, 1, 0.92))
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    output = FIGURE_DIR / "wood_2025_classifier_spatial_validation.png"
    fig.savefig(output, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()

