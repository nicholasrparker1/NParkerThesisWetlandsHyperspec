from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from src.config import DATA_RAW, FIGURES
from src.io_hyperspectral import (
    discover_neon_h5_paths,
    latlon_to_rowcol,
    read_map_info,
)
from src.preprocess import build_bad_band_mask, build_invalid_value_mask
from src.scripts.pull_spectrum_latlon import (
    read_roi_stats_spectrum,
    snap_to_valid_pixel,
)


def find_h5_for_point(lat: float, lon: float, h5_files: list[Path]):
    """
    Find the H5 tile that contains this lat/lon.
    Returns:
        h5, cube_path, wl_path, mapinfo_path, row, col
    """
    for h5 in h5_files:
        try:
            paths = discover_neon_h5_paths(str(h5))
            cube_path = paths["reflectance_path"]
            wl_path = paths["wavelength_path"]
            mapinfo_path = paths["map_info_path"]

            mi = read_map_info(str(h5), mapinfo_path)
            r, c = latlon_to_rowcol(lat, lon, mi)

            import h5py
            with h5py.File(h5, "r") as f:
                cube = f[cube_path]
                rows, cols, _ = cube.shape

            inside = (0 <= r < rows) and (0 <= c < cols)
            if inside:
                return h5, cube_path, wl_path, mapinfo_path, r, c
        except Exception:
            continue

    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--points", required=True, help="CSV with columns: id,lat,lon")
    ap.add_argument("--snap", type=int, default=75, help="Snap radius (pixels)")
    ap.add_argument("--roi", type=int, default=9, help="Odd integer ROI size")
    ap.add_argument("--out", default=None, help="Output PNG path (optional)")
    ap.add_argument("--p_lo", type=float, default=25.0, help="Lower percentile")
    ap.add_argument("--p_hi", type=float, default=75.0, help="Upper percentile")
    args = ap.parse_args()

    if args.roi < 1 or args.roi % 2 == 0:
        raise ValueError("--roi must be an odd integer >= 1")
    if not (0.0 <= args.p_lo < args.p_hi <= 100.0):
        raise ValueError("--p_lo and --p_hi must satisfy 0 <= p_lo < p_hi <= 100")

    # Read point CSV
    pts: list[tuple[str, float, float]] = []
    with open(args.points, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pts.append((str(row["id"]), float(row["lat"]), float(row["lon"])))

    if not pts:
        raise RuntimeError(f"No points found in {args.points}")

    # Gather all H5 files
    h5_files = sorted(DATA_RAW.glob("*.h5"))
    if not h5_files:
        raise FileNotFoundError(f"No .h5 files found in {DATA_RAW}")

    print("\nH5 files available:")
    for h5 in h5_files:
        print(" -", h5.name)

    fig, ax = plt.subplots(figsize=(11, 6))
    n_plotted = 0
    global_max = 0.0

    colors = plt.cm.rainbow(np.linspace(0, 1, len(pts)))

    for pid, lat, lon in pts:
        print(f"\n=== Point {pid}: lat={lat}, lon={lon} ===")

        match = find_h5_for_point(lat, lon, h5_files)
        if match is None:
            print(f"SKIP Point {pid}: not inside any H5 tile in data/raw")
            continue

        h5, cube_path, wl_path, mapinfo_path, r0, c0 = match
        print("Matched H5:", h5.name)
        print(f"lat/lon -> row/col (raw): ({lat}, {lon}) -> (r={r0}, c={c0})")

        # Snap to nearest valid pixel
        r, c = snap_to_valid_pixel(
            str(h5),
            cube_path,
            r0,
            c0,
            radius=args.snap,
            band=0,
        )
        if r is None or c is None:
            print(f"SKIP Point {pid}: no valid pixel within radius={args.snap}")
            continue

        if (r, c) != (r0, c0):
            print(f"Snapped to nearest valid pixel: (r={r}, c={c})")
        else:
            print("Pixel already valid — no snapping needed.")

        # Read ROI stats
        wl, med, lo, hi, bounds = read_roi_stats_spectrum(
            str(h5),
            cube_path,
            wl_path,
            r,
            c,
            roi=args.roi,
            p_lo=args.p_lo,
            p_hi=args.p_hi,
        )
        rmin, rmax, cmin, cmax = bounds
        print(f"ROI pixel window: rows {rmin}-{rmax}, cols {cmin}-{cmax}")

        wl = wl.astype(float)
        med = med.astype(float)
        lo = lo.astype(float)
        hi = hi.astype(float)

        # Convert µm -> nm if needed
        if np.nanmax(wl) < 50.0:
            wl *= 1000.0

        # Scale reflectance if stored as scaled integers
        if np.any(np.isfinite(med)):
            if np.nanmax(med) > 2.0:
                med = med / 10000.0
                lo = lo / 10000.0
                hi = hi / 10000.0
                print("Applied scale factor: /10000.0")

        # Build masks
        bad_mask = build_bad_band_mask(wl, include_narrow=True)
        med_invalid = build_invalid_value_mask(
            med, min_reflectance=0.0, max_reflectance=1.2
        )
        lo_invalid = build_invalid_value_mask(
            lo, min_reflectance=0.0, max_reflectance=1.2
        )
        hi_invalid = build_invalid_value_mask(
            hi, min_reflectance=0.0, max_reflectance=1.2
        )

        masked = bad_mask | med_invalid | lo_invalid | hi_invalid

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

        color_idx = n_plotted

        # Track y-limit
        try:
            local_max = float(np.nanpercentile(med_plot[good_plot], 98))
            if np.isfinite(local_max):
                global_max = max(global_max, local_max)
        except Exception:
            pass

        # Plot
        ax.plot(
            wl,
            med_plot,
            linewidth=2.2,
            label=pid,
            color=colors[color_idx],
        )

        n_plotted += 1

        if np.any(np.isfinite(lo_plot)) and np.any(np.isfinite(hi_plot)):
            ax.fill_between(wl, lo_plot, hi_plot, alpha=0.12)

    if n_plotted == 0:
        raise RuntimeError("No valid spectra plotted. Check points, tiles, snap radius, or ROI location.")

    # Atmospheric windows
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

    if args.out:
        outpath = Path(args.out)
    else:
        outpath = FIGURES / f"overlay_{Path(args.points).stem}_roi{args.roi}_snap{args.snap}.png"

    plt.savefig(outpath, dpi=300)
    plt.show()
    print("\nSaved:", outpath)


if __name__ == "__main__":
    main()