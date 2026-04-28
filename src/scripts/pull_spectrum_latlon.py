from __future__ import annotations

import argparse

import h5py
import matplotlib.pyplot as plt
import numpy as np

from src.config import FIGURES
from src.preprocess import clean_spectrum, spectrum_for_plot
from src.workflow import (
    find_h5_files,
    find_h5_for_point,
    normalize_reflectance,
    normalize_wavelengths_nm,
)


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
    Read one band over a small window and return the nearest valid pixel.
    """
    with h5py.File(h5_path, "r") as f:
        cube = f[cube_path]
        rows, cols, _ = cube.shape

        rmin = max(0, r0 - radius)
        rmax = min(rows - 1, r0 + radius)
        cmin = max(0, c0 - radius)
        cmax = min(cols - 1, c0 + radius)

        win = cube[rmin : rmax + 1, cmin : cmax + 1, band]

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
    Return wavelength, ROI median, lower percentile, upper percentile, and bounds.
    """
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

    win[win < 0] = np.nan
    n_pix = win.shape[0] * win.shape[1]
    win2 = win.reshape(n_pix, win.shape[2])

    valid_counts = np.sum(np.isfinite(win2), axis=0)
    min_valid = max(5, int(0.20 * n_pix))

    med = np.nanmedian(win2, axis=0)
    lo = np.nanpercentile(win2, p_lo, axis=0)
    hi = np.nanpercentile(win2, p_hi, axis=0)

    med[valid_counts < min_valid] = np.nan
    lo[valid_counts < min_valid] = np.nan
    hi[valid_counts < min_valid] = np.nan

    return wl, med, lo, hi, (rmin, rmax, cmin, cmax)


def read_roi_median_spectrum(
    h5_path: str,
    cube_path: str,
    wl_path: str,
    r: int,
    c: int,
    roi: int,
) -> tuple[np.ndarray, np.ndarray, tuple[int, int, int, int]]:
    wl, med, _lo, _hi, bounds = read_roi_stats_spectrum(
        h5_path,
        cube_path,
        wl_path,
        r,
        c,
        roi,
        p_lo=25,
        p_hi=75,
    )
    return wl, med, bounds


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--snap", type=int, default=75, help="Snap radius in pixels")
    ap.add_argument("--roi", type=int, default=1, help="Odd integer ROI size; 1 = single pixel")
    args = ap.parse_args()

    h5_files = find_h5_files()
    match = find_h5_for_point(args.lat, args.lon, h5_files)
    if match is None:
        names = ", ".join(h.name for h in h5_files)
        raise RuntimeError(
            f"Point ({args.lat}, {args.lon}) is not inside any H5 tile in data/raw. "
            f"Files checked: {names}"
        )

    print("Matched H5:", match.h5_path)
    if match.site:
        print("Matched site/group:", match.site)
    print(f"lat/lon -> row/col (raw): ({args.lat}, {args.lon}) -> (r={match.row}, c={match.col})")

    row, col = snap_to_valid_pixel(
        str(match.h5_path),
        match.reflectance_path,
        match.row,
        match.col,
        radius=args.snap,
        band=0,
    )
    if row is None or col is None:
        raise RuntimeError(
            f"No valid pixel found within radius={args.snap} of "
            f"(r={match.row}, c={match.col})."
        )

    if (row, col) != (match.row, match.col):
        print(f"Snapped to nearest valid pixel: (r={row}, c={col}) (radius={args.snap})")
    else:
        print("Pixel already valid; no snapping needed.")

    wl, spec, bounds = read_roi_median_spectrum(
        str(match.h5_path),
        match.reflectance_path,
        match.wavelength_path,
        row,
        col,
        roi=args.roi,
    )

    rmin, rmax, cmin, cmax = bounds
    print(f"ROI pixel window: rows {rmin}-{rmax}, cols {cmin}-{cmax}")
    print(f"ROI size: {args.roi} x {args.roi} pixels")

    wl = normalize_wavelengths_nm(wl)
    was_scaled = np.any(np.isfinite(spec)) and float(np.nanmax(spec)) > 2.0
    spec = normalize_reflectance(spec)
    if was_scaled:
        print("Applied scale factor: spec /= 10000.0")

    print(
        "ROI median spectrum stats:",
        "finite=", int(np.isfinite(spec).sum()),
        "min=", float(np.nanmin(spec)),
        "max=", float(np.nanmax(spec)),
    )

    wl_plot, spec_plot, _hidden_mask = spectrum_for_plot(
        wl,
        spec,
        include_narrow_bad_bands=True,
        max_reflectance=1.2,
    )
    wl_clean, spec_clean, _keep_mask = clean_spectrum(
        wl,
        spec,
        include_narrow_bad_bands=True,
        max_reflectance=1.2,
    )
    good_clean = np.isfinite(wl_clean) & np.isfinite(spec_clean)

    print("Original bands:", wl.size)
    print("Bands after atmospheric removal:", wl_clean.size)
    print("Bands valid after cleaning:", int(np.isfinite(spec_clean).sum()))

    if not np.any(good_clean):
        print("WARNING: No valid points after cleaning. Plotting absorption-masked spectrum anyway.")

    plt.figure(figsize=(10, 4.8))
    plt.plot(wl_plot, spec_plot, linewidth=2.2)

    for a, b in [(920, 960), (1110, 1145), (1340, 1450), (1800, 1950)]:
        plt.axvspan(a, b, alpha=0.12)

    plt.xlabel("Wavelength (nm)", fontsize=12)
    plt.ylabel("Reflectance", fontsize=12)
    plt.title(
        f"Median ROI Spectrum @ ({args.lat:.6f}, {args.lon:.6f}) -> r={row}, c={col}\n"
        f"ROI: {args.roi}x{args.roi} pixels (median) | Atmospheric residual bands removed",
        fontsize=13,
    )

    if np.any(good_clean):
        y_top = float(np.nanpercentile(spec_clean[good_clean], 98) * 1.15)
    else:
        good_plot = np.isfinite(wl_plot) & np.isfinite(spec_plot)
        if not np.any(good_plot):
            raise RuntimeError("No valid spectrum to plot. Check scaling or ROI location.")
        y_top = float(np.nanpercentile(spec_plot[good_plot], 98) * 1.15)

    if not np.isfinite(y_top) or y_top <= 0:
        y_top = 0.2
    plt.ylim(0, y_top)

    plt.grid(True, linestyle="--", alpha=0.3)
    plt.minorticks_on()
    plt.tight_layout()

    meta_text = (
        f"H5: {match.h5_path.name}\n"
        f"Snap radius: {args.snap}px\n"
        f"ROI: {args.roi}x{args.roi}px (median)\n"
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
        f"spectrum_roi{args.roi}_lat{args.lat:.5f}_lon{args.lon:.5f}_r{row}_c{col}_snap{args.snap}.png"
    )
    outpath.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(outpath, dpi=300)
    plt.show()
    print("Saved:", outpath)


if __name__ == "__main__":
    main()
