from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


# ============================================================================
# Paths
# ============================================================================

ROOT = Path(__file__).resolve().parents[2]

INPUT = (
    ROOT
    / "outputs"
    / "tables"
    / "kssl_neon_linkage"
    / "north_dakota_pilot"
    / "nd_sample_texture_matched_mir.csv"
)

OUTDIR = ROOT / "outputs" / "figures" / "hydric_soil_bridge"
OUTDIR.mkdir(parents=True, exist_ok=True)

PNG = OUTDIR / "fig03_nd_mir_candidate_region.png"
PDF = OUTDIR / "fig03_nd_mir_candidate_region.pdf"


PAIR_COLUMNS = [
    "269180_minus_269142",
    "242130_minus_247323",
    "242114_minus_269150",
    "242107_minus_247270",
    "242125_minus_247310",
]


# ============================================================================
# Style
# ============================================================================

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.size": 11,
        "axes.titlesize": 16,
        "axes.labelsize": 12,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "axes.linewidth": 0.8,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    }
)


def main():

    df = pd.read_csv(INPUT)

    plot_df = df[
        df["wavenumber_cm1"].between(1200, 1400)
    ].copy()

    candidate = df[
        df["wavenumber_cm1"].between(1248, 1298)
    ].copy()

    print("North Dakota MIR candidate-region figure")
    print("=" * 70)
    print("Matched comparisons:", len(PAIR_COLUMNS))
    print(
        "Candidate channels hydric-lower in >=4/5 comparisons:",
        f"{(candidate['hydric_lower_count'] >= 4).sum()}/{len(candidate)}",
    )
    print(
        "Candidate channels hydric-lower in all 5:",
        f"{(candidate['hydric_lower_count'] == 5).sum()}/{len(candidate)}",
    )
    print(
        "Median mean difference in candidate region:",
        f"{candidate['mean_delta'].median():.4f}",
    )

    # ========================================================================
    # Figure
    # ========================================================================

    fig, ax = plt.subplots(figsize=(10.5, 5.8))

    # ------------------------------------------------------------------------
    # Candidate region
    # ------------------------------------------------------------------------

    ax.axvspan(
        1248,
        1298,
        color="0.92",
        zorder=0,
    )

    # ------------------------------------------------------------------------
    # Five individual texture-matched comparisons
    # ------------------------------------------------------------------------

    for col in PAIR_COLUMNS:
        ax.plot(
            plot_df["wavenumber_cm1"],
            plot_df[col],
            color="0.68",
            linewidth=1.1,
            alpha=0.72,
            zorder=2,
        )

    # ------------------------------------------------------------------------
    # Mean across all five comparisons
    # ------------------------------------------------------------------------

    ax.plot(
        plot_df["wavenumber_cm1"],
        plot_df["mean_delta"],
        color="black",
        linewidth=3.0,
        zorder=5,
    )

    # ------------------------------------------------------------------------
    # Zero reference
    # ------------------------------------------------------------------------

    ax.axhline(
        0,
        color="0.25",
        linewidth=1.0,
        zorder=1,
    )

    # MIR convention
    ax.set_xlim(1400, 1200)

    ymin = plot_df[PAIR_COLUMNS].min().min()
    ymax = plot_df[PAIR_COLUMNS].max().max()

    ax.set_ylim(
        ymin - 0.05,
        ymax + 0.08,
    )

    # ------------------------------------------------------------------------
    # Axis labels
    # ------------------------------------------------------------------------

    ax.set_xlabel(
        r"Wavenumber (cm$^{-1}$)"
    )

    ax.set_ylabel(
        "Normalized MIR difference (dimensionless)\n"
        "Hydric − matched nonhydric"
    )

    # ------------------------------------------------------------------------
    # Title + subtitle
    # ------------------------------------------------------------------------

    ax.set_title(
        "Hydric soils show a consistent MIR difference near 1250–1300 cm⁻¹",
        loc="left",
        fontweight="semibold",
        pad=18,
    )

    ax.text(
        0.0,
        1.015,
        "North Dakota · 5 hydric soils compared with texture-matched nonhydric soils",
        transform=ax.transAxes,
        fontsize=10,
        color="0.38",
        ha="left",
        va="bottom",
    )

    # ------------------------------------------------------------------------
    # Candidate region label
    # ------------------------------------------------------------------------

    ax.text(
        1273,
        ymax + 0.045,
        "Candidate region\n1248–1298 cm⁻¹",
        ha="center",
        va="top",
        fontsize=9.5,
        fontweight="semibold",
        color="0.30",
    )

    # ------------------------------------------------------------------------
    # Mean line label
    # ------------------------------------------------------------------------

    label_x = 1340

    idx = (
        plot_df["wavenumber_cm1"] - label_x
    ).abs().idxmin()

    label_y = plot_df.loc[idx, "mean_delta"]

    ax.annotate(
        "Mean of 5 comparisons",
        xy=(label_x, label_y),
        xytext=(1370, -0.30),
        fontsize=9.5,
        fontweight="semibold",
        color="black",
        ha="left",
        va="center",
        arrowprops={
            "arrowstyle": "-",
            "linewidth": 0.8,
            "color": "0.30",
        },
    )

    # ------------------------------------------------------------------------
    # Zero-line label
    # ------------------------------------------------------------------------

    ax.text(
        1203,
        0.012,
        "No difference",
        fontsize=8.5,
        color="0.35",
        ha="right",
        va="bottom",
    )

    # ------------------------------------------------------------------------
    # Clean appearance
    # ------------------------------------------------------------------------

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    ax.tick_params(
        direction="out",
        length=4,
        width=0.8,
    )

    ax.grid(False)

    # Give title/subtitle and axes comfortable spacing.
    fig.subplots_adjust(
        left=0.13,
        right=0.98,
        bottom=0.15,
        top=0.86,
    )

    # ------------------------------------------------------------------------
    # Small explanatory note OUTSIDE plotting area
    # ------------------------------------------------------------------------

    fig.text(
        0.13,
        0.055,
        "Negative values indicate lower normalized MIR absorbance in the hydric soil.",
        fontsize=9,
        color="0.38",
        ha="left",
    )

    # ------------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------------

    fig.savefig(
        PNG,
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
    )

    fig.savefig(
        PDF,
        bbox_inches="tight",
        facecolor="white",
    )

    plt.close(fig)

    print("\nWrote:")
    print(PNG)
    print(PDF)


if __name__ == "__main__":
    main()