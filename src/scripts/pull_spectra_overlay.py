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

from src.preprocess import (
    build_bad_band_mask,
    build_invalid_value_mask,
    iqr_summary,
)

from src.config import DATA_RAW, FIGURES, REFLECTANCE_PATH, WAVELENGTH_PATH
from src.io_hyperspectral import latlon_to_rowcol, read_map_info
from src.scripts.pull_spectrum_latlon import (
    MAPINFO_PATH,
    snap_to_valid_pixel,
    read_roi_stats_spectrum,
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

    # keep simple numeric summary of ROI spread (median IQR width) per point
    iqr_summary_vals: list[tuple[str, float]] = []

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
        if (rmin != r - (args.roi // 2)) or (cmin != c - (args.roi // 2)):
            print("NOTE: ROI may be clipped near raster edge; check printed bounds.")
            # not perfect, but gives a hint; the printed bounds are the truth
           

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
        
        bad_band_mask = build_bad_band_mask(
            wl,
            include_narrow=True,
        )

        invalid_med = build_invalid_value_mask(
            med,
            min_reflectance=0.0,
            max_reflectance=1.2,
        )
        invalid_lo = build_invalid_value_mask(
            lo,
            min_reflectance=0.0,
            max_reflectance=1.2,
        )
        invalid_hi = build_invalid_value_mask(
            hi,
            min_reflectance=0.0,
            max_reflectance=1.2,
        )

        masked = bad_band_mask | invalid_med | invalid_lo | invalid_hi

        med_plot = med.copy()
        lo_plot = lo.copy()
        hi_plot = hi.copy()

        med_plot[masked] = np.nan
        lo_plot[masked] = np.nan
        hi_plot[masked] = np.nan

        good_plot = np.isfinite(wl) & np.isfinite(med_plot)
        if not np.any(good_plot):
            print(f"WARNING Point {pid}: no valid points after cleaning (skipping curve).")
            continue

        any_good = True

        # numeric "variance" summary: median IQR width across wavelengths (excluding masked NaNs)
        if np.any(np.isfinite(lo_plot)) and np.any(np.isfinite(hi_plot)):
            iqr_med = iqr_summary(lo_plot, hi_plot)
            iqr_summary_vals.append((pid, iqr_med))
            print(
                f"ROI spread summary (median IQR width = "
                f"p{args.p_hi:.0f}-p{args.p_lo:.0f}): {iqr_med:.5f}"
            )
            

        # global y-limit tracking
        global_max = max(global_max, float(np.nanpercentile(med_plot[good_plot], 98)))

        # plot median line + shaded percentile band
        ax.plot(wl, med_plot, linewidth=2.0, label=f"Point {pid}")
        ax.fill_between(wl, lo_plot, hi_plot, alpha=0.15)

    if not any_good:
        raise RuntimeError("No valid spectra plotted. Check points, snap radius, or ROI location.")

    # shade absorption regions on the combined plot
    for a, b in [(920, 960), (1110, 1145), (1340, 1450), (1800, 1950)]:
        ax.axvspan(a, b, alpha=0.12)

    ax.set_xlabel("Wavelength (nm)", fontsize=12, labelpad=12)
    ax.set_ylabel("Reflectance", fontsize=12)
    ax.set_title(
        f"Median ROI spectra along transect (ROI={args.roi}×{args.roi}, snap={args.snap}px)\n"
        f"Shaded band: IQR envelope (p{args.p_lo:.0f}–p{args.p_hi:.0f}) across ROI pixels | Broad + narrow atmospheric residual bands masked",
        fontsize=13,
    )
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.minorticks_on()
    ax.legend(title="Transect points", loc="upper right")

    # y-limit (consistent across curves)
    y_top = float(global_max * 1.15) if np.isfinite(global_max) and global_max > 0 else 0.2
    ax.set_ylim(0, y_top)

    # --------------------------------------------------------
    # Spectral-region labels under x-axis
    # --------------------------------------------------------
    xmin, xmax = ax.get_xlim()

    y_line = -0.19
    y_text = -0.24

    regions = [
        ("VIS\n400–700", 400, 700),
        ("NIR\n700–1300", 700, 1300),
        ("SWIR-I\n1450–1800", 1450, 1800),
        ("SWIR-II\n1950–2400", 1950, 2400),
    ]

    for label, x0, x1 in regions:
        xa = max(x0, xmin)
        xb = min(x1, xmax)
        if xb <= xa:
            continue

        ax.plot(
            [xa, xb],
            [y_line, y_line],
            transform=ax.get_xaxis_transform(),
            color="black",
            linewidth=1.0,
            clip_on=False,
        )

        ax.plot(
            [xa, xa],
            [y_line - 0.015, y_line + 0.015],
            transform=ax.get_xaxis_transform(),
            color="black",
            linewidth=1.0,
            clip_on=False,
        )
        ax.plot(
            [xb, xb],
            [y_line - 0.015, y_line + 0.015],
            transform=ax.get_xaxis_transform(),
            color="black",
            linewidth=1.0,
            clip_on=False,
        )

        ax.text(
            (xa + xb) / 2,
            y_text,
            label,
            transform=ax.get_xaxis_transform(),
            ha="center",
            va="top",
            fontsize=10,
            fontweight="bold",
        )

    plt.tight_layout()
    plt.subplots_adjust(bottom=0.31)
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