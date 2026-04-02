"""
pull_spectrum_latlon.py

Pull a hyperspectral reflectance spectrum from a NEON ROCX H5 file using a
lat/lon coordinate. Converts lat/lon -> row/col using Map_Info (UTM), optionally
snaps to a nearby valid pixel, then extracts either:
  - a single pixel spectrum (roi=1), or
  - a median spectrum over an NxN ROI window (roi>1)

Atmospheric absorption bands are shown as gaps in the plot and are removed
from the analysis vector.
"""

from __future__ import annotations

import argparse

import matplotlib.pyplot as plt
import numpy as np
import h5py
from src.preprocess import clean_spectrum, spectrum_for_plot


from src.config import DATA_RAW, FIGURES
from src.io_hyperspectral import (
    latlon_to_rowcol,
    read_map_info,
    discover_neon_h5_paths,
)

#This also needs to be changed based on the hyperspectral file of interest

MAPINFO_PATH = "ROCX/Reflectance/Metadata/Coordinate_System/Map_Info"
EPSG_PATH    = "ROCX/Reflectance/Metadata/Coordinate_System/EPSG Code"

# ============================================================
# FAST SNAP FUNCTION (single disk read of a small window)
# ============================================================
def snap_to_valid_pixel(
    h5_path: str,
    cube_path: str,
    r0: int,
    c0: int,
    *,
    radius: int = 50,
    band: int = 0,
) -> tuple[int | None, int | None]:
    """
    Fast snap-to-valid pixel:
    - Reads ONE band over a (2*radius+1) x (2*radius+1) window in ONE HDF5 call.
    - Finds nearest pixel where value > 0 (valid convention for raw int16 band).
    """
    with h5py.File(h5_path, "r") as f:
        cube = f[cube_path]
        rows, cols, _ = cube.shape

        rmin = max(0, r0 - radius)
        rmax = min(rows - 1, r0 + radius)
        cmin = max(0, c0 - radius)
        cmax = min(cols - 1, c0 + radius)

        win = cube[rmin : rmax + 1, cmin : cmax + 1, band]  # (H, W)

    valid = win > 0
    if not np.any(valid):
        return None, None

    rr, cc = np.where(valid)
    rr_full = rr + rmin
    cc_full = cc + cmin

    d2 = (rr_full - r0) ** 2 + (cc_full - c0) ** 2
    k = int(np.argmin(d2))
    return int(rr_full[k]), int(cc_full[k])


def read_roi_stats_spectrum(
    h5_path: str,
    cube_path: str,
    wl_path: str,
    r: int,
    c: int,
    roi: int,
    p_lo: float = 25,
    p_hi: float = 75,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, tuple[int, int, int, int]]:
    """
    Returns:
      wl (B,)
      med (B,)  median across ROI pixels for each band
      lo  (B,)  lower percentile (default p25)
      hi  (B,)  upper percentile (default p75)
      bounds (rmin,rmax,cmin,cmax) inclusive
    """
    import h5py
    import numpy as np

    if roi < 1 or roi % 2 == 0:
        raise ValueError("--roi must be an odd integer >= 1")

    half = roi // 2

    with h5py.File(h5_path, "r") as f:
        cube = f[cube_path]
        wl = f[wl_path][:]

        rows, cols, _ = cube.shape
        rmin = max(0, r - half)
        rmax = min(rows - 1, r + half)
        cmin = max(0, c - half)
        cmax = min(cols - 1, c + half)

        win = cube[rmin : rmax + 1, cmin : cmax + 1, :].astype(float)

    # invalid handling consistent with your median code
    win[win < 0] = np.nan

    n_pix = win.shape[0] * win.shape[1]
    win2 = win.reshape(n_pix, win.shape[2])  # (Npix, B)

    valid_counts = np.sum(np.isfinite(win2), axis=0)
    min_valid = max(5, int(0.20 * n_pix))

    med = np.nanmedian(win2, axis=0)
    lo = np.nanpercentile(win2, p_lo, axis=0)
    hi = np.nanpercentile(win2, p_hi, axis=0)

    # Require enough valid pixels per band.
    med[valid_counts < min_valid] = np.nan
    lo[valid_counts < min_valid] = np.nan
    hi[valid_counts < min_valid] = np.nan

    return wl, med, lo, hi, (rmin, rmax, cmin, cmax)

# ============================================================
# ROI MEDIAN SPECTRUM (single HDF5 read of a small window)
# ============================================================
def read_roi_median_spectrum(
    h5_path: str,
    cube_path: str,
    wl_path: str,
    r: int,
    c: int,
    roi: int,
) -> tuple[np.ndarray, np.ndarray, tuple[int, int, int, int]]:
    """
    Reads an NxN ROI window around (r,c) from the reflectance cube and returns:

      wavelengths (B,)
      median_spectrum (B,)   median across pixels for each band
      roi_bounds (rmin, rmax, cmin, cmax) inclusive

    Robustness:
      - Treats negatives as invalid
      - Does NOT automatically kill near-zero reflectance
      - Requires a minimum number of valid pixels per band before accepting the median
    """
    if roi < 1:
        raise ValueError("--roi must be >= 1")
    if roi % 2 == 0:
        raise ValueError("--roi must be odd (1,3,5,7,9,...)")

    half = roi // 2

    with h5py.File(h5_path, "r") as f:
        cube = f[cube_path]
        wl = f[wl_path][:]

        rows, cols, _ = cube.shape
        rmin = max(0, r - half)
        rmax = min(rows - 1, r + half)
        cmin = max(0, c - half)
        cmax = min(cols - 1, c + half)

        win = cube[rmin : rmax + 1, cmin : cmax + 1, :]  # (H, W, B)

    win = win.astype(float)

    # Invalid handling: negative values are never valid reflectance
    win[win < 0] = np.nan

    # reshape to (Npix, B)
    n_pix = win.shape[0] * win.shape[1]
    win2 = win.reshape(n_pix, win.shape[2])

    # valid pixel counts per band
    valid_counts = np.sum(np.isfinite(win2), axis=0)

    # median per band
    spec_med = np.nanmedian(win2, axis=0)

    # Require enough valid pixels per band.
    min_valid = max(5, int(0.20 * n_pix))
    spec_med[valid_counts < min_valid] = np.nan

    return wl, spec_med, (rmin, rmax, cmin, cmax)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--snap", type=int, default=75, help="Snap radius (pixels)")
    ap.add_argument(
        "--roi",
        type=int,
        default=1,
        help="Odd integer ROI size in pixels. 1 = single pixel; 9 = 9x9 median spectrum",
    )
    args = ap.parse_args()

    # --------------------------------------------------------
    # Find H5
    # --------------------------------------------------------
    h5_files = list(DATA_RAW.glob("*.h5"))
    if not h5_files:
        raise FileNotFoundError(f"No .h5 files found in {DATA_RAW}")
    h5 = h5_files[0]
    print("Using H5:", h5)

    paths = discover_neon_h5_paths(str(h5))
    cube_path = paths["reflectance_path"]
    wl_path = paths["wavelength_path"]
    mapinfo_path = paths["map_info_path"]

    # --------------------------------------------------------
    # Convert lat/lon -> pixel (row/col)
    # --------------------------------------------------------
    mi = read_map_info(str(h5), mapinfo_path)    
    print("Program is using EPSG:", mi.get("epsg"))
    r0, c0 = latlon_to_rowcol(args.lat, args.lon, mi)
    print(f"lat/lon -> row/col (raw): ({args.lat}, {args.lon}) -> (r={r0}, c={c0})")

    # --------------------------------------------------------
    # Snap to valid pixel
    # --------------------------------------------------------
    r, c = snap_to_valid_pixel(
        str(h5),
        cube_path,
        r0,
        c0,
        radius=args.snap,
        band=0,
    )
    if r is None or c is None:
        raise RuntimeError(
            f"No valid pixel found within radius={args.snap} of (r={r0}, c={c0})."
        )

    if (r, c) != (r0, c0):
        print(f"Snapped to nearest valid pixel: (r={r}, c={c})  (radius={args.snap})")
    else:
        print("Pixel already valid — no snapping needed.")

    # --------------------------------------------------------
    # Read ROI median spectrum
    # --------------------------------------------------------
    wl, spec, bounds = read_roi_median_spectrum(
        str(h5),
        cube_path,
        wl_path,
        r,
        c,
        roi=args.roi,
    )

    rmin, rmax, cmin, cmax = bounds
    print(f"ROI pixel window: rows {rmin}-{rmax}, cols {cmin}-{cmax}")
    print(f"ROI size: {args.roi} x {args.roi} pixels (~{args.roi}m x ~{args.roi}m if ~1m NEON pixels)")

    # Convert µm -> nm if needed
    wl = wl.astype(float)
    if float(np.nanmax(wl)) < 50.0:
        wl *= 1000.0
    spec = spec.astype(float)


    # --------------------------------------------------------
    # Scale reflectance if stored as scaled integers (common in NEON products)
    # If values look like 0–10000+, convert to ~0–1 reflectance.
    # --------------------------------------------------------
    # Scale reflectance if stored as scaled integers (common)
    if np.nanmax(spec) > 2.0:
        spec = spec / 10000.0
        print("Applied scale factor: spec /= 10000.0 (scaled-int reflectance -> 0–1)")


    # Debug stats
    print(
        "ROI median spectrum stats:",
        "finite=", int(np.isfinite(spec).sum()),
        "min=", float(np.nanmin(spec)),
        "max=", float(np.nanmax(spec)),
    )

        # --------------------------------------------------------
    # Spectral cleaning / bad-band masking
    # --------------------------------------------------------
    wl_plot, spec_plot, hidden_mask = spectrum_for_plot(
        wl,
        spec,
        include_narrow_bad_bands=True,
        max_reflectance=1.2,
    )

    wl_clean, spec_clean, keep_mask = clean_spectrum(
        wl,
        spec,
        include_narrow_bad_bands=True,
        max_reflectance=1.2,
    )

    good_clean = np.isfinite(wl_clean) & np.isfinite(spec_clean)

    print("Original bands:", wl.size)
    print("Bands after atmospheric removal:", wl_clean.size)
    print("Bands valid after cleaning:", int(np.isfinite(spec_clean).sum()))

    # If cleaning killed everything, still allow plotting of what we have
    if not np.any(good_clean):
        print("WARNING: No valid points after cleaning. Plotting absorption-masked spectrum anyway.")

    # --------------------------------------------------------
    # Plot
    # --------------------------------------------------------
    plt.figure(figsize=(10, 4.8))
    plt.plot(wl, spec_plot, linewidth=2.2)

    for a, b in [(920, 960), (1110, 1145), (1340, 1450), (1800, 1950)]:
        plt.axvspan(a, b, alpha=0.12)
        plt.axvspan(a, b, alpha=0.15)

    plt.xlabel("Wavelength (nm)", fontsize=12)
    plt.ylabel("Reflectance", fontsize=12)
    plt.title(
        f"Median ROI Spectrum @ ({args.lat:.6f}, {args.lon:.6f}) → r={r}, c={c}\n"
        f"ROI: {args.roi}×{args.roi} pixels (median) | Broad + narrow atmospheric residual bands removed",
        fontsize=13,
    )

    # y-limits: use cleaned data if available, else fall back to plot data
    if np.any(good_clean):
        y_top = float(np.nanpercentile(spec_clean[good_clean], 98) * 1.15)
    else:
        good_plot = np.isfinite(wl) & np.isfinite(spec_plot)
        if not np.any(good_plot):
            raise RuntimeError("No valid spectrum to plot (all NaN after masking). Check scaling / ROI location.")
        y_top = float(np.nanpercentile(spec_plot[good_plot], 98) * 1.15)

    if not np.isfinite(y_top) or y_top <= 0:
        y_top = 0.2
    plt.ylim(0, y_top)


    plt.grid(True, linestyle="--", alpha=0.3)
    plt.minorticks_on()
    plt.tight_layout()

    meta_text = (
        "Sensor: NEON Airborne Hyperspectral\n"
        "CRS: UTM Zone 18N (EPSG:32618)\n"
        f"Snap radius: {args.snap}px\n"
        f"ROI: {args.roi}×{args.roi}px (median)\n"
        f"Bands (raw): {wl.size}\n"
        f"Bands (used): {wl_clean.size}"
    )
    plt.text(
        0.99,
        0.98,
        meta_text,
        transform=plt.gca().transAxes,
        ha="right",
        va="top",
        fontsize=9,
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.85),
    )

    outpath = FIGURES / (
        f"spectrum_roi{args.roi}_lat{args.lat:.5f}_lon{args.lon:.5f}_r{r}_c{c}_snap{args.snap}.png"
    )
    plt.savefig(outpath, dpi=300)
    plt.show()

    print("Saved:", outpath)


if __name__ == "__main__":
    main()
