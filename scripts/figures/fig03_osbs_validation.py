from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]

INPUT_DIR = (
    ROOT
    / "outputs"
    / "tables"
    / "kssl_neon_linkage"
    / "osbs_validation"
)

SUMMARY_FILE = INPUT_DIR / "osbs_nd_band_validation_summary.csv"
SPECTRA_FILE = INPUT_DIR / "osbs_nd_band_validation_spectra.csv"

OUTPUT_DIR = ROOT / "outputs" / "figures" / "hydric_soil_bridge"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PNG_OUT = OUTPUT_DIR / "fig03_osbs_validation.png"
PDF_OUT = OUTPUT_DIR / "fig03_osbs_validation.pdf"


# ---------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------

summary = pd.read_csv(SUMMARY_FILE).iloc[0]
spectra = pd.read_csv(SPECTRA_FILE)

BAND_MIN = 1248
BAND_MAX = 1298

comparison_cols = [
    c for c in spectra.columns
    if c.startswith("comparison_")
]

band = spectra[
    spectra["wavenumber_cm1"].between(BAND_MIN, BAND_MAX)
].copy()

w = band["wavenumber_cm1"].to_numpy()
mean_spectrum = band["mean_difference"].to_numpy()

supporting_channels = int(summary["channels_hydric_lower_3plus"])
n_channels = int(summary["channels_in_candidate_band"])
supporting_pairs = int(summary["pairs_supporting_nd_direction"])


# ---------------------------------------------------------------------
# Figure styling
# ---------------------------------------------------------------------

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.size": 12,
        "axes.labelsize": 14,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 1.0,
    }
)


# ---------------------------------------------------------------------
# Build figure
# ---------------------------------------------------------------------

fig, ax = plt.subplots(figsize=(10.8, 5.9))

# Four independent Florida hydric–nonhydric comparisons
for col in comparison_cols:
    ax.plot(
        band["wavenumber_cm1"],
        band[col],
        color="0.72",
        linewidth=1.6,
        alpha=0.9,
        zorder=1,
    )

# Zero line = no difference between hydric and matched nonhydric sample
ax.axhline(
    0,
    color="0.30",
    linewidth=1.1,
    zorder=0,
)

# Mean response across the four Florida comparisons
ax.plot(
    w,
    mean_spectrum,
    color="black",
    linewidth=3.6,
    zorder=3,
)


# ---------------------------------------------------------------------
# Axes
# ---------------------------------------------------------------------

# MIR spectra are conventionally displayed with decreasing wavenumber
ax.set_xlim(BAND_MAX, BAND_MIN)

all_values = band[comparison_cols].to_numpy().flatten()

ax.set_ylim(
    np.nanmin(all_values) - 0.03,
    np.nanmax(all_values) + 0.05,
)

ax.set_xlabel(r"Wavenumber (cm$^{-1}$)")

ax.set_ylabel(
    "Difference in SNV-normalized\nMIR absorbance (a.u.)"
)

ax.grid(
    axis="y",
    color="0.92",
    linewidth=0.8,
)


# ---------------------------------------------------------------------
# Title and subtitle
# ---------------------------------------------------------------------

fig.suptitle(
    "Independent Florida validation of the North Dakota MIR candidate region",
    x=0.14,
    y=0.965,
    ha="left",
    fontsize=20,
    fontweight="bold",
)

fig.text(
    0.14,
    0.885,
    "1248–1298 cm⁻¹ · 4 texture-matched hydric–nonhydric comparisons",
    ha="left",
    fontsize=12.5,
    color="0.38",
)



# ---------------------------------------------------------------------
# Final formatting
# ---------------------------------------------------------------------

ax.tick_params(direction="out")

fig.subplots_adjust(
    left=0.13,
    right=0.98,
    top=0.79,
    bottom=0.14,
)


# ---------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------

fig.savefig(
    PNG_OUT,
    dpi=300,
    bbox_inches="tight",
    facecolor="white",
)

fig.savefig(
    PDF_OUT,
    bbox_inches="tight",
    facecolor="white",
)

plt.close(fig)


# ---------------------------------------------------------------------
# Console summary
# ---------------------------------------------------------------------

print("Florida validation figure")
print("=" * 70)
print(f"Florida comparisons: {len(comparison_cols)}")
print(
    f"Channels supporting ND direction in >=3/4 comparisons: "
    f"{supporting_channels}/{n_channels}"
)
print(
    f"Comparisons with negative band-average: "
    f"{supporting_pairs}/{len(comparison_cols)}"
)
print()
print("Wrote:")
print(PNG_OUT)
print(PDF_OUT)