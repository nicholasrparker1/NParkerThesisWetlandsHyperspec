from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from src.config import FIGURES
from src.io_hyperspectral import read_roi_median_spectrum, snap_to_valid_pixel
from src.preprocess import clean_spectrum, spectrum_for_plot
from src.spectral_plotting import ReflectancePlotSeries, plot_reflectance_spectra
from src.workflow import (
    find_h5_files,
    find_h5_for_point,
    normalize_reflectance,
    normalize_wavelengths_nm,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--snap", type=int, default=5, help="Snap radius in pixels")
    ap.add_argument("--roi", type=int, default=1, help="Odd integer ROI size; 1 = single pixel")
    ap.add_argument("--out", default=None, help="Output PNG path")
    ap.add_argument("--show", action="store_true", help="Open the Matplotlib window after saving")
    args = ap.parse_args()

    if args.roi < 1 or args.roi % 2 == 0:
        raise ValueError("--roi must be an odd integer >= 1")

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

    default_outpath = FIGURES / (
        f"spectrum_roi{args.roi}_lat{args.lat:.5f}_lon{args.lon:.5f}_r{row}_c{col}_snap{args.snap}.png"
    )
    outpath = Path(args.out) if args.out else default_outpath
    site = match.site or "ROCX"
    plot_reflectance_spectra(
        [
            ReflectancePlotSeries(
                label=f"lat {args.lat:.6f}, lon {args.lon:.6f}",
                wavelengths_nm=wl_plot,
                reflectance=spec_plot,
            )
        ],
        outpath=outpath,
        footer=(
            f"Data source: NEON {site} airborne hyperspectral reflectance; "
            f"single point; ROI size: {args.roi} m x {args.roi} m; snap={args.snap}."
        ),
        show=args.show,
    )
    print("Saved:", outpath)


if __name__ == "__main__":
    main()
