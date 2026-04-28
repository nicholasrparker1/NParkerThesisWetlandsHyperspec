from __future__ import annotations

import argparse

import matplotlib.pyplot as plt
import numpy as np

from src.config import FIGURES
from src.io_hyperspectral import find_nearest_valid_pixel, read_pixel_spectrum
from src.preprocess import spectrum_for_plot
from src.workflow import find_h5_files, normalize_reflectance, normalize_wavelengths_nm
from src.io_hyperspectral import discover_neon_h5_paths


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--row", type=int, default=20)
    ap.add_argument("--col", type=int, default=2400)
    ap.add_argument("--snap", type=int, default=200)
    args = ap.parse_args()

    h5_file = find_h5_files()[0]
    paths = discover_neon_h5_paths(str(h5_file))
    print("Using H5:", h5_file)
    print("Reflectance path:", paths["reflectance_path"])

    row, col = args.row, args.col
    try:
        wavelengths, spectrum = read_pixel_spectrum(
            str(h5_file),
            paths["reflectance_path"],
            paths["wavelength_path"],
            row,
            col,
        )
    except Exception:
        row, col = find_nearest_valid_pixel(
            str(h5_file),
            paths["reflectance_path"],
            row,
            col,
            search_radius=args.snap,
            band=0,
        )
        wavelengths, spectrum = read_pixel_spectrum(
            str(h5_file),
            paths["reflectance_path"],
            paths["wavelength_path"],
            row,
            col,
        )

    if int(np.isfinite(spectrum).sum()) == 0:
        row, col = find_nearest_valid_pixel(
            str(h5_file),
            paths["reflectance_path"],
            row,
            col,
            search_radius=args.snap,
            band=0,
        )
        wavelengths, spectrum = read_pixel_spectrum(
            str(h5_file),
            paths["reflectance_path"],
            paths["wavelength_path"],
            row,
            col,
        )

    wl = normalize_wavelengths_nm(wavelengths)
    spec = normalize_reflectance(spectrum)
    wl_plot, spec_plot, _ = spectrum_for_plot(wl, spec, include_narrow_bad_bands=True, max_reflectance=1.2)

    print("wavelengths:", wl.shape, "min/max:", float(np.nanmin(wl)), float(np.nanmax(wl)))
    print(
        "spectrum stats:",
        "finite=", int(np.isfinite(spec).sum()),
        "min=", float(np.nanmin(spec)),
        "max=", float(np.nanmax(spec)),
    )

    plt.figure(figsize=(9, 4))
    plt.plot(wl_plot, spec_plot, linewidth=2.0)
    for a, b in [(920, 960), (1110, 1145), (1340, 1450), (1800, 1950)]:
        plt.axvspan(a, b, alpha=0.12)
    plt.xlabel("Wavelength (nm)")
    plt.ylabel("Reflectance")
    plt.title(f"Reflectance Spectrum (r={row}, c={col})")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    outpath = FIGURES / f"sample_spectrum_r{row}_c{col}_clean.png"
    outpath.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(outpath, dpi=250)
    plt.show()
    print("Saved:", outpath)


if __name__ == "__main__":
    main()
