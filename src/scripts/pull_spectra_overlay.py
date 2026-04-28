from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from src.config import FIGURES
from src.preprocess import build_bad_band_mask, build_invalid_value_mask
from src.scripts.pull_spectrum_latlon import read_roi_stats_spectrum, snap_to_valid_pixel
from src.workflow import (
    find_h5_files,
    find_h5_for_point,
    load_point_csv,
    normalize_reflectance,
    normalize_wavelengths_nm,
    rainbow_colors,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--points", required=True, help="CSV with columns: id,lat,lon")
    ap.add_argument("--snap", type=int, default=75, help="Snap radius in pixels")
    ap.add_argument("--roi", type=int, default=9, help="Odd integer ROI size")
    ap.add_argument("--out", default=None, help="Output PNG path")
    ap.add_argument("--p_lo", type=float, default=25.0, help="Lower percentile")
    ap.add_argument("--p_hi", type=float, default=75.0, help="Upper percentile")
    args = ap.parse_args()

    if args.roi < 1 or args.roi % 2 == 0:
        raise ValueError("--roi must be an odd integer >= 1")
    if not (0.0 <= args.p_lo < args.p_hi <= 100.0):
        raise ValueError("--p_lo and --p_hi must satisfy 0 <= p_lo < p_hi <= 100")

    points = load_point_csv(args.points)
    h5_files = find_h5_files()

    print("\nH5 files available:")
    for h5 in h5_files:
        print(" -", h5.name)

    fig, ax = plt.subplots(figsize=(11, 6))
    colors = rainbow_colors(len(points))
    n_plotted = 0
    global_max = 0.0

    for point_index, point in enumerate(points):
        print(f"\n=== Point {point.id}: lat={point.lat}, lon={point.lon} ===")

        match = find_h5_for_point(point.lat, point.lon, h5_files)
        if match is None:
            print(f"SKIP Point {point.id}: not inside any H5 tile in data/raw")
            continue

        print("Matched H5:", match.h5_path.name)
        if match.site:
            print("Matched site/group:", match.site)
        print(
            f"lat/lon -> row/col (raw): ({point.lat}, {point.lon}) "
            f"-> (r={match.row}, c={match.col})"
        )

        row, col = snap_to_valid_pixel(
            str(match.h5_path),
            match.reflectance_path,
            match.row,
            match.col,
            radius=args.snap,
            band=0,
        )
        if row is None or col is None:
            print(f"SKIP Point {point.id}: no valid pixel within radius={args.snap}")
            continue

        if (row, col) != (match.row, match.col):
            print(f"Snapped to nearest valid pixel: (r={row}, c={col})")
        else:
            print("Pixel already valid; no snapping needed.")

        wl, med, lo, hi, bounds = read_roi_stats_spectrum(
            str(match.h5_path),
            match.reflectance_path,
            match.wavelength_path,
            row,
            col,
            roi=args.roi,
            p_lo=args.p_lo,
            p_hi=args.p_hi,
        )
        rmin, rmax, cmin, cmax = bounds
        print(f"ROI pixel window: rows {rmin}-{rmax}, cols {cmin}-{cmax}")

        wl = normalize_wavelengths_nm(wl)
        was_scaled = np.any(np.isfinite(med)) and float(np.nanmax(med)) > 2.0
        med = normalize_reflectance(med)
        lo = normalize_reflectance(lo)
        hi = normalize_reflectance(hi)
        if was_scaled:
            print("Applied scale factor: /10000.0")

        bad_mask = build_bad_band_mask(wl, include_narrow=True)
        med_invalid = build_invalid_value_mask(med, min_reflectance=0.0, max_reflectance=1.2)
        lo_invalid = build_invalid_value_mask(lo, min_reflectance=0.0, max_reflectance=1.2)
        hi_invalid = build_invalid_value_mask(hi, min_reflectance=0.0, max_reflectance=1.2)
        masked = bad_mask | med_invalid | lo_invalid | hi_invalid

        med_plot = med.copy()
        lo_plot = lo.copy()
        hi_plot = hi.copy()
        med_plot[masked] = np.nan
        lo_plot[masked] = np.nan
        hi_plot[masked] = np.nan

        good_plot = np.isfinite(wl) & np.isfinite(med_plot)
        if not np.any(good_plot):
            print(f"WARNING Point {point.id}: no valid points after cleaning; skipping curve.")
            continue

        local_max = float(np.nanpercentile(med_plot[good_plot], 98))
        if np.isfinite(local_max):
            global_max = max(global_max, local_max)

        color = colors[point_index]
        ax.plot(wl, med_plot, linewidth=2.2, label=point.id, color=color)
        n_plotted += 1

        if np.any(np.isfinite(lo_plot)) and np.any(np.isfinite(hi_plot)):
            ax.fill_between(wl, lo_plot, hi_plot, color=color, alpha=0.12)

    if n_plotted == 0:
        raise RuntimeError("No valid spectra plotted. Check points, tiles, snap radius, or ROI location.")

    for a, b in [(920, 960), (1110, 1145), (1340, 1450), (1800, 1950)]:
        ax.axvspan(a, b, alpha=0.12)

    ax.set_xlabel("Wavelength (nm)", fontsize=12, labelpad=12)
    ax.set_ylabel("Reflectance", fontsize=12)
    ax.set_title(
        f"Overlayed ROI Spectra from CSV: {Path(args.points).name}\n"
        f"Auto-matched H5 tile per point | ROI={args.roi} | Snap={args.snap}",
        fontsize=13,
    )
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.minorticks_on()
    ax.legend(loc="upper right")

    y_top = float(global_max * 1.15) if np.isfinite(global_max) and global_max > 0 else 0.2
    ax.set_ylim(0, y_top)

    y_line = -0.19
    y_text = -0.24
    regions = [
        ("VIS\n400-700", 400, 700),
        ("NIR\n700-1300", 700, 1300),
        ("SWIR-I\n1450-1800", 1450, 1800),
        ("SWIR-II\n1950-2400", 1950, 2400),
    ]

    xmin, xmax = ax.get_xlim()
    for label, x0, x1 in regions:
        xa = max(x0, xmin)
        xb = min(x1, xmax)
        if xb <= xa:
            continue

        ax.plot([xa, xb], [y_line, y_line], transform=ax.get_xaxis_transform(), color="black", linewidth=1.0, clip_on=False)
        ax.plot([xa, xa], [y_line - 0.015, y_line + 0.015], transform=ax.get_xaxis_transform(), color="black", linewidth=1.0, clip_on=False)
        ax.plot([xb, xb], [y_line - 0.015, y_line + 0.015], transform=ax.get_xaxis_transform(), color="black", linewidth=1.0, clip_on=False)
        ax.text((xa + xb) / 2, y_text, label, transform=ax.get_xaxis_transform(), ha="center", va="top", fontsize=10, fontweight="bold")

    plt.tight_layout()
    plt.subplots_adjust(bottom=0.31)

    outpath = Path(args.out) if args.out else FIGURES / f"overlay_{Path(args.points).stem}_roi{args.roi}_snap{args.snap}.png"
    outpath.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(outpath, dpi=300)
    plt.show()
    print("\nSaved:", outpath)


if __name__ == "__main__":
    main()
