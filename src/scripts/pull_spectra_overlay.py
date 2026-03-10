"""
pull_spectra_overlay.py

Read a CSV of transect points (id,lat,lon), extract a median ROI spectrum for each,
remove atmospheric absorption bands, and OVERLAY all spectra on a single plot.

Adds ROI variability shading (default: interquartile range, p25–p75) so you can
see per-band variance within the ROI.

Uses same logic as pull_spectrum_latlon.py (snap + ROI stats + band masking).
"""

from __future__ import annotations

import argparse
import csv

import matplotlib.pyplot as plt
import numpy as np

from src.config import DATA_RAW, FIGURES, REFLECTANCE_PATH, WAVELENGTH_PATH
from src.io_hyperspectral import latlon_to_rowcol, read_map_info

# Reuse helpers from your working single-point script
from src.scripts.pull_spectrum_latlon import (
    MAPINFO_PATH,
    snap_to_valid_pixel,
    read_roi_stats_spectrum,  # returns wl, median, p_lo, p_hi, bounds
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--points", required=True, help="CSV with columns: id,lat,lon")
    ap.add_argument("--snap", type=int, default=75, help="Snap radius (pixels)")
    ap.add_argument("--roi", type=int, default=9, help="Odd integer ROI size (default 9)")
    ap.add_argument("--out", default=None, help="Output PNG path (optional)")
    ap.add_argument(
        "--p_lo",
        type=float,
        default=25.0,
        help="Lower percentile for ROI shading (default 25)",
    )
    ap.add_argument(
        "--p_hi",
        type=float,
        default=75.0,
        help="Upper percentile for ROI shading (default 75)",
    )
    args = ap.parse_args()

    if args.roi < 1 or args.roi % 2 == 0:
        raise ValueError("--roi must be an odd integer >= 1 (1,3,5,7,9,...)")
    if not (0.0 <= args.p_lo < args.p_hi <= 100.0):
        raise ValueError("--p_lo and --p_hi must satisfy 0 <= p_lo < p_hi <= 100")

    # ---- read points ----
    pts: list[tuple[str, float, float]] = []
    with open(args.points, "r", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            pts.append((str(r["id"]), float(r["lat"]), float(r["lon"])))

    if not pts:
        raise RuntimeError(f"No points found in {args.points}. Expect columns: id,lat,lon")

    # ---- find H5 ----
    h5_files = list(DATA_RAW.glob("*.h5"))
    if not h5_files:
        raise FileNotFoundError(f"No .h5 files found in {DATA_RAW}")
    h5 = h5_files[0]
    print("Using H5:", h5)

    # ---- map info once ----
    mi = read_map_info(str(h5), MAPINFO_PATH)
    print("Using EPSG:", mi.get("epsg"))

    # ---- plotting ----
    fig, ax = plt.subplots(figsize=(11, 6))

    any_good = False
    global_max = 0.0

    # keep simple numeric summary of "variance" (IQR width) per point
    variance_summary: list[tuple[str, float]] = []

    for pid, lat, lon in pts:
        print(f"\n=== Point {pid}: lat={lat}, lon={lon} ===")

        # lat/lon -> raw row/col
        r0, c0 = latlon_to_rowcol(lat, lon, mi)
        print(f"lat/lon -> row/col (raw): ({lat}, {lon}) -> (r={r0}, c={c0})")

        # snap
        r, c = snap_to_valid_pixel(
            str(h5),
            REFLECTANCE_PATH,
            r0,
            c0,
            radius=args.snap,
            band=0,
        )
        if r is None or c is None:
            print(f"SKIP Point {pid}: no valid pixel within radius={args.snap}")
            continue

        if (r, c) != (r0, c0):
            print(f"Snapped to nearest valid pixel: (r={r}, c={c})  (radius={args.snap})")
        else:
            print("Pixel already valid — no snapping needed.")

        # ROI stats (median + percentile band)
        wl, med, lo, hi, bounds = read_roi_stats_spectrum(
            str(h5),
            REFLECTANCE_PATH,
            WAVELENGTH_PATH,
            r,
            c,
            roi=args.roi,
            p_lo=args.p_lo,
            p_hi=args.p_hi,
        )
        rmin, rmax, cmin, cmax = bounds
        print(f"ROI pixel window: rows {rmin}-{rmax}, cols {cmin}-{cmax}")

        # warn if ROI is clipped (near edges)
        # (this can reduce effective ROI size and inflate variability)
        # We can't easily get rows/cols without opening H5 again; bounds check still helps.
        if (rmin == r - (args.roi // 2)) is False or (cmin == c - (args.roi // 2)) is False:
            # not perfect, but gives a hint; the printed bounds are the truth
            pass

        # µm -> nm if needed
        wl = wl.astype(float)
        if float(np.nanmax(wl)) < 50.0:
            wl *= 1000.0

        med = med.astype(float)
        lo = lo.astype(float)
        hi = hi.astype(float)

        # scaling (same rule as your single-point script)
        # Use median to decide scaling, then apply to all stats
        if np.nanmax(med) > 2.0:
            med = med / 10000.0
            lo = lo / 10000.0
            hi = hi / 10000.0
            print("Applied scale factor: spec /= 10000.0 (scaled-int reflectance -> 0–1)")

        # atmospheric absorption mask (same as single-point)
        bad = (
            ((wl > 1340) & (wl < 1450))
            | ((wl > 1800) & (wl < 1950))
            | (wl > 2400)
        )

        # plotting arrays with NaN gaps
        med_plot = med.copy()
        lo_plot = lo.copy()
        hi_plot = hi.copy()

        med_plot[bad] = np.nan
        lo_plot[bad] = np.nan
        hi_plot[bad] = np.nan

        # keep consistent with your cleaning cap
        med_plot[med_plot > 1.2] = np.nan
        lo_plot[lo_plot > 1.2] = np.nan
        hi_plot[hi_plot > 1.2] = np.nan

        good_plot = np.isfinite(wl) & np.isfinite(med_plot)
        if not np.any(good_plot):
            print(f"WARNING Point {pid}: no valid points after cleaning (skipping curve).")
            continue

        any_good = True

        # numeric "variance" summary: median IQR width across wavelengths (excluding masked NaNs)
        iqr = hi_plot - lo_plot
        good_iqr = np.isfinite(iqr) & np.isfinite(wl)
        if np.any(good_iqr):
            iqr_med = float(np.nanmedian(iqr[good_iqr]))
            variance_summary.append((pid, iqr_med))
            print(f"ROI variability summary (median p{args.p_hi:.0f}-p{args.p_lo:.0f} width): {iqr_med:.5f}")

        # global y-limit tracking
        global_max = max(global_max, float(np.nanpercentile(med_plot[good_plot], 98)))

        # plot median line + shaded percentile band
        ax.plot(wl, med_plot, linewidth=2.0, label=f"Point {pid}")
        ax.fill_between(wl, lo_plot, hi_plot, alpha=0.15)

    if not any_good:
        raise RuntimeError("No valid spectra plotted. Check points, snap radius, or ROI location.")

    # shade absorption regions on the combined plot
    for a, b in [(1340, 1450), (1800, 1950)]:
        ax.axvspan(a, b, alpha=0.12)

    ax.set_xlabel("Wavelength (nm)", fontsize=12)
    ax.set_ylabel("Reflectance", fontsize=12)
    ax.set_title(
        f"Median ROI spectra along transect (ROI={args.roi}×{args.roi}, snap={args.snap}px)\n"
        f"Shaded band: p{args.p_lo:.0f}–p{args.p_hi:.0f} across ROI pixels | Atmospheric absorption bands masked",
        fontsize=13,
    )
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.minorticks_on()
    ax.legend(title="Transect points", loc="upper right")

    # y-limit (consistent across curves)
    y_top = float(global_max * 1.15) if np.isfinite(global_max) and global_max > 0 else 0.2
    ax.set_ylim(0, y_top)

    # Add a small text box summarizing variability (optional but useful)
    if variance_summary:
        # show up to first 8 points to keep box compact
        lines = [f"{pid}: {v:.4f}" for pid, v in variance_summary[:8]]
        extra = "" if len(variance_summary) <= 8 else f"\n(+{len(variance_summary)-8} more)"
        var_text = (
            f"ROI variability (median p{args.p_hi:.0f}-p{args.p_lo:.0f} width)\n"
            + "\n".join(lines)
            + extra
        )
        ax.text(
            0.01,
            0.99,
            var_text,
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=9,
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.85),
        )

    plt.tight_layout()

    outpath = args.out
    if outpath is None:
        outpath = FIGURES / f"spectra_overlay_roi{args.roi}_snap{args.snap}_p{int(args.p_lo)}-{int(args.p_hi)}.png"
    else:
        outpath = str(outpath)

    plt.savefig(outpath, dpi=300)
    plt.show()
    print("Saved:", outpath)


if __name__ == "__main__":
    main()