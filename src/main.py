import sys
from pathlib import Path

# When this file is executed directly (python src/main.py) the interpreter
# does not automatically add the project root to sys.path which makes
# imports like `from src.config import ...` fail with ModuleNotFoundError.
# Ensure the project root (parent of `src`) is on sys.path so the module
# imports work both when run as a module and as a script.
if __package__ is None:
    proj_root = Path(__file__).resolve().parents[1]
    proj_root_str = str(proj_root)
    if proj_root_str not in sys.path:
        sys.path.insert(0, proj_root_str)

import numpy as np
import matplotlib.pyplot as plt

from src.config import DATA_RAW, FIGURES, REFLECTANCE_PATH, WAVELENGTH_PATH
from src.io_hyperspectral import read_pixel_spectrum, find_valid_pixel


def main():
    h5_files = list(DATA_RAW.glob("*.h5"))
    if not h5_files:
        raise FileNotFoundError(f"No .h5 files found in {DATA_RAW}")

    h5_file = h5_files[0]
    print("Using H5:", h5_file)

    # Start with a known-good pixel (you can change these)
    r = 20
    c = 2400

    wavelengths, spectrum = read_pixel_spectrum(
        str(h5_file), REFLECTANCE_PATH, WAVELENGTH_PATH, r, c
    )

    # If the pixel is invalid, automatically find a valid one
    n_valid = int(np.isfinite(spectrum).sum())
    if n_valid == 0:
        print(f"Pixel (r={r}, c={c}) has no valid bands. Finding a valid pixel...")
        r, c = find_valid_pixel(
            str(h5_file), REFLECTANCE_PATH, step=200, band_for_check=0
        )
        print(f"Found valid pixel (approx): r={r}, c={c}")

        wavelengths, spectrum = read_pixel_spectrum(
            str(h5_file), REFLECTANCE_PATH, WAVELENGTH_PATH, r, c
        )
        n_valid = int(np.isfinite(spectrum).sum())

    # --- Wavelength units (um vs nm) ---
    wl = wavelengths.astype(float)
    if float(np.nanmax(wl)) < 50.0:
        wl *= 1000.0  # um -> nm

    spec = spectrum.astype(float)

    print(
        "wavelengths:", wl.shape, "min/max:", float(np.nanmin(wl)), float(np.nanmax(wl))
    )
    print(
        "spectrum stats: finite:",
        n_valid,
        "/",
        spec.size,
        "min/max:",
        float(np.nanmin(spec)),
        float(np.nanmax(spec)),
    )

    # ==============================
    # Remove atmospheric absorption bands (for analysis + plotting)
    # ==============================

    # Standard atmospheric H2O absorption + low-SNR tail (nm)
    bad = (
        ((wl > 1340) & (wl < 1450))
        | ((wl > 1800) & (wl < 1950))
        | (wl > 2400)
    )

    wl_clean = wl[~bad]
    spec_clean = spec[~bad]

    # Optional: mask extreme outliers (instrument artifacts / bad bands)
    spec_clean = spec_clean.copy()
    spec_clean[spec_clean > 1.2] = np.nan

    good = np.isfinite(wl_clean) & np.isfinite(spec_clean)
    if not np.any(good):
        raise RuntimeError(f"No valid points to plot after cleaning at (r={r}, c={c}).")

    # ==============================
    # Plot
    # ==============================
    plt.figure(figsize=(9, 4))
    plt.plot(wl_clean[good], spec_clean[good], linewidth=2.0)

    # Shade removed regions (helps the reader understand why there are missing wavelengths)
    for a, b in [(1340, 1450), (1800, 1950)]:
        plt.axvspan(a, b, alpha=0.15)

    plt.xlabel("Wavelength (nm)")
    plt.ylabel("Reflectance")
    plt.title(f"Reflectance Spectrum (r={r}, c={c})\nAtmospheric bands removed")

    plt.ylim(0, 0.2)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    outpath = FIGURES / f"sample_spectrum_r{r}_c{c}_clean.png"
    plt.savefig(outpath, dpi=250)
    plt.show()

    print("Saved:", outpath)


if __name__ == "__main__":
    main()
