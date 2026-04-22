import argparse
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

from src.io_hyperspectral import (
    read_pixel_spectrum,
    read_map_info,
    latlon_to_rowcol,
)

DEFAULT_H5 = r".1NEON_D09_WOOD_DP3_480000_5221000_bidirectional_reflectance.h5"
cube_path = "NOGP/Reflectance/Reflectance_Data"
WAVE_PATH = "NOGP/Reflectance/Metadata/Spectral_Data/Wavelength"
MAPINFO_PATH = "NOGP/Reflectance/Metadata/Coordinate_System/Map_Info"
epsg = 32614

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--h5", default=DEFAULT_H5, help="Path to H5 file")
    ap.add_argument("--outdir", default=r".\outputs\figures", help="Where to save PNG/CSV")
    ap.add_argument("--r", type=int, default=None, help="Row index")
    ap.add_argument("--c", type=int, default=None, help="Col index")
    ap.add_argument("--lat", type=float, default=None, help="Latitude (EPSG:4326)")
    ap.add_argument("--lon", type=float, default=None, help="Longitude (EPSG:4326)")
    args = ap.parse_args()

    h5_path = args.h5
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Resolve pixel location
    if args.r is not None and args.c is not None:
        r, c = args.r, args.c
        loc_label = f"r{r}_c{c}"
    elif args.lat is not None and args.lon is not None:
        mi = read_map_info(h5_path, MAPINFO_PATH)
        r, c = latlon_to_rowcol(args.lat, args.lon, mi, epsg=EPSG)
        loc_label = f"lat{args.lat:.5f}_lon{args.lon:.5f}_r{r}_c{c}"
        print(f"lat/lon -> row/col: ({args.lat}, {args.lon}) -> (r={r}, c={c})")
    else:
        raise SystemExit("Provide either --r and --c OR --lat and --lon")

    # Pull spectrum
    wl, spec = read_pixel_spectrum(h5_path, CUBE_PATH, WAVE_PATH, r, c)

    # Save CSV
    csv_path = outdir / f"spectrum_{loc_label}.csv"
    arr = np.column_stack([wl.astype(float), spec.astype(float)])
    np.savetxt(csv_path, arr, delimiter=",", header="wavelength_nm,reflectance", comments="")

    # Plot
    png_path = outdir / f"spectrum_{loc_label}.png"
    plt.figure()
    plt.plot(wl, spec)
    plt.xlabel("Wavelength (nm)")
    plt.ylabel("Reflectance")
    plt.title(f"Spectrum @ (r={r}, c={c})")
    plt.grid(True, alpha=0.3)
    plt.savefig(png_path, dpi=200, bbox_inches="tight")
    plt.close()

    finite = np.isfinite(spec).sum()
    print("=== DONE ===")
    print(f"Saved CSV: {csv_path}")
    print(f"Saved PNG: {png_path}")
    print(f"Finite bands: {finite}/{len(spec)}")
    print(f"Min/Max: {np.nanmin(spec):.4f} / {np.nanmax(spec):.4f}")


if __name__ == "__main__":
    main()
