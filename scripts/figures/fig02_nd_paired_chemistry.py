from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]

INPUT = (
    ROOT
    / "outputs"
    / "tables"
    / "kssl_neon_linkage"
    / "north_dakota_pilot"
    / "nd_best3_texture_matched_chemistry.csv"
)

OUTDIR = (
    ROOT
    / "outputs"
    / "figures"
    / "hydric_soil_bridge"
)

OUTDIR.mkdir(parents=True, exist_ok=True)

PNG = OUTDIR / "fig02_nd_paired_chemistry.png"
PDF = OUTDIR / "fig02_nd_paired_chemistry.pdf"


# ---------------------------------------------------------------------
# Properties to display
# ---------------------------------------------------------------------

PROPERTIES = [
    "estimated_organic_carbon_pct",
    "total_nitrogen_pct",
    "total_sulfur_pct",
    "fe_dithionite_pct",
    "al_dithionite_pct",
]

LABELS = {
    "estimated_organic_carbon_pct": "Organic C",
    "total_nitrogen_pct": "Total N",
    "total_sulfur_pct": "Total S",
    "fe_dithionite_pct": "Dithionite Fe",
    "al_dithionite_pct": "Dithionite Al",
}


def main():

    df = pd.read_csv(INPUT)

    df = df[df["property"].isin(PROPERTIES)].copy()

    print("North Dakota paired chemistry figure")
    print("=" * 72)

    # Confirm directional consistency before plotting.
    for prop in PROPERTIES:

        d = df[df["property"].eq(prop)]

        n = len(d)
        higher = (d["delta_hydric_minus_nonhydric"] > 0).sum()
        lower = (d["delta_hydric_minus_nonhydric"] < 0).sum()

        print(
            f"{LABELS[prop]}: "
            f"hydric higher {higher}/{n}, "
            f"hydric lower {lower}/{n}"
        )

    # -----------------------------------------------------------------
    # Figure
    # -----------------------------------------------------------------

    fig, axes = plt.subplots(
        1,
        len(PROPERTIES),
        figsize=(13.5, 5.6),
        constrained_layout=True,
    )

    for ax, prop in zip(axes, PROPERTIES):

        d = (
            df[df["property"].eq(prop)]
            .sort_values("hydric_pedon")
            .reset_index(drop=True)
        )

        # Each line is one texture-matched pedon pair.
        for _, row in d.iterrows():

            ax.plot(
                [0, 1],
                [
                    row["nonhydric_value"],
                    row["hydric_value"],
                ],
                marker="o",
                markersize=7,
                linewidth=1.6,
                alpha=0.85,
            )

        ax.set_xticks([0, 1])
        ax.set_xticklabels(
            ["Nonhydric", "Hydric"],
            rotation=0,
        )

        ax.set_title(
            LABELS[prop],
            fontsize=12,
            fontweight="bold",
        )

        ax.set_ylabel("Concentration (%)")

        ax.grid(
            axis="y",
            alpha=0.20,
        )

        # Keep a little visual breathing room around the data.
        values = pd.concat(
            [
                d["nonhydric_value"],
                d["hydric_value"],
            ]
        )

        ymin = values.min()
        ymax = values.max()

        span = ymax - ymin

        if span == 0:
            span = max(abs(ymax), 1) * 0.1

        ax.set_ylim(
            max(0, ymin - 0.12 * span),
            ymax + 0.12 * span,
        )

    # -----------------------------------------------------------------
    # Overall title and explanatory text
    # -----------------------------------------------------------------

    fig.suptitle(
        "Paired soil chemistry differences in "
        "texture-matched North Dakota pedons",
        fontsize=16,
        fontweight="bold",
    )

    fig.text(
        0.5,
        -0.035,
        "Each line represents one hydric pedon and its "
        "texture-matched nonhydric comparison (n = 3 pairs).",
        ha="center",
        fontsize=10,
    )

    # -----------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------

    fig.savefig(
        PNG,
        dpi=300,
        bbox_inches="tight",
    )

    fig.savefig(
        PDF,
        bbox_inches="tight",
    )

    print("\nWrote:")
    print(PNG)
    print(PDF)


if __name__ == "__main__":
    main()