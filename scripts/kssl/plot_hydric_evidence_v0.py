"""Create publication-ready diagnostics for the provisional mapped-evidence tool."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "outputs/tables/kssl_tool/kssl_mt_nd_hydric_evidence_v0.csv"
OUT_DIR = ROOT / "outputs/figures/kssl_tool"

NAVY = "#17324D"
TEAL = "#0F7C80"
GOLD = "#D9A441"
PURPLE = "#7A3E9D"
GRAY = "#9AA5AC"
PALE = "#EAF2F3"


def main() -> None:
    data = pd.read_csv(INPUT, low_memory=False)
    score = pd.to_numeric(data["hydric_evidence_score"], errors="coerce")
    ssurgo = pd.to_numeric(data["ssurgo_evidence_component"], errors="coerce") * 100
    nwi = pd.to_numeric(data["nwi_evidence_component"], errors="coerce").eq(1)

    plt.rcParams.update(
        {
            "font.family": "Arial",
            "font.size": 10,
            "axes.titlesize": 13,
            "axes.labelsize": 11,
            "axes.edgecolor": NAVY,
            "axes.labelcolor": NAVY,
            "xtick.color": NAVY,
            "ytick.color": NAVY,
            "text.color": NAVY,
        }
    )

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(12.5, 5.8), gridspec_kw={"width_ratios": [1.05, 1.45]}
    )
    fig.patch.set_facecolor("white")

    order = ["low", "moderate", "high", "very high"]
    counts = data["evidence_category"].value_counts().reindex(order, fill_value=0)
    colors = [GRAY, GOLD, TEAL, NAVY]
    bars = ax1.barh(order, counts, color=colors, edgecolor="white", height=0.7)
    ax1.invert_yaxis()
    ax1.set_title("A. Provisional evidence categories", loc="left", fontweight="bold")
    ax1.set_xlabel("Number of surface-soil samples")
    ax1.grid(axis="x", alpha=0.18)
    ax1.set_axisbelow(True)
    for bar, value in zip(bars, counts):
        ax1.text(
            bar.get_width() + 4,
            bar.get_y() + bar.get_height() / 2,
            f"{value} ({value / len(data):.1%})",
            va="center",
            fontsize=10,
        )
    ax1.set_xlim(0, max(counts) * 1.22)

    rng = np.random.default_rng(42)
    jitter = rng.normal(0, 0.012, len(data))
    ax2.scatter(
        ssurgo[~nwi],
        score[~nwi] + jitter[~nwi],
        s=30,
        color=GRAY,
        alpha=0.62,
        edgecolor="white",
        linewidth=0.35,
        label=f"No NWI intersection (n={(~nwi).sum()})",
    )
    ax2.scatter(
        ssurgo[nwi],
        score[nwi] + jitter[nwi],
        s=48,
        color=PURPLE,
        alpha=0.9,
        edgecolor=NAVY,
        linewidth=0.55,
        label=f"NWI intersection (n={nwi.sum()})",
        zorder=3,
    )
    for boundary in (0.25, 0.50, 0.75):
        ax2.axhline(boundary, color=NAVY, linewidth=0.8, alpha=0.24, linestyle="--")
    ax2.set_title("B. How the mapped score is constructed", loc="left", fontweight="bold")
    ax2.set_xlabel("SSURGO hydric component (%)")
    ax2.set_ylabel("Hydric evidence score (0–1)")
    ax2.set_xlim(-3, 103)
    ax2.set_ylim(-0.04, 1.04)
    ax2.grid(alpha=0.16)
    ax2.set_axisbelow(True)
    ax2.legend(frameon=False, loc="upper left")

    fig.suptitle(
        "Version-0 mapped hydric-soil evidence diagnostic",
        fontsize=18,
        fontweight="bold",
        color=NAVY,
        y=0.98,
    )
    fig.text(
        0.5,
        0.015,
        "SSURGO and NWI are weak reference evidence—not field-confirmed hydric determinations. "
        "Confidence records input completeness separately from evidence strength.",
        ha="center",
        color=NAVY,
        fontsize=10.5,
    )
    fig.tight_layout(rect=(0.02, 0.065, 0.99, 0.93), w_pad=3.0)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    png = OUT_DIR / "kssl_mt_nd_hydric_evidence_v0_diagnostic.png"
    pdf = OUT_DIR / "kssl_mt_nd_hydric_evidence_v0_diagnostic.pdf"
    fig.savefig(png, dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(png)
    print(pdf)


if __name__ == "__main__":
    main()
