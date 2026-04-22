from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import DATA_RAW, REFLECTANCE_PATH, WAVELENGTH_PATH
from src.io_hyperspectral import (
    latlon_to_rowcol,
    read_map_info,
)
from src.scripts.pull_spectrum_latlon import (
    snap_to_valid_pixel,
    read_roi_median_spectrum,
)

MAPINFO_PATH = "NOGP/Reflectance/Metadata/Coordinate_System/Map_Info"

def find_h5_file() -> Path:
    h5_files = list(DATA_RAW.glob("*.h5"))
    if not h5_files:
        raise FileNotFoundError(f"No .h5 files found in {DATA_RAW}")
    return h5_files[0]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=str, default="data/field/moisture_points.csv")
    ap.add_argument("--out_npz", type=str, default="data/processed/moisture_training_data.npz")
    ap.add_argument("--out_csv", type=str, default="data/processed/moisture_training_summary.csv")
    ap.add_argument("--roi", type=int, default=5, help="Odd ROI size in pixels")
    ap.add_argument("--snap", type=int, default=40, help="Snap radius in pixels")
    args = ap.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)

    required_cols = {"id", "lat", "lon", "moisture"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")

    h5 = find_h5_file()
    print("Using H5:", h5)

    mi = read_map_info(str(h5), MAPINFO_PATH)
    print("Program is using EPSG:", mi.get("epsg"))

    spectra = []
    labels = []
    summary_rows = []
    wavelengths_nm = None

    for _, row in df.iterrows():
        sample_id = int(row["id"])
        lat = float(row["lat"])
        lon = float(row["lon"])
        moisture = float(row["moisture"])

        r0, c0 = latlon_to_rowcol(lat, lon, mi)

        r, c = snap_to_valid_pixel(
            str(h5),
            REFLECTANCE_PATH,
            r0,
            c0,
            radius=args.snap,
            band=0,
        )

        if r is None or c is None:
            print(f"Skipping sample {sample_id}: no valid pixel found within snap radius.")
            continue

        wl, spec, bounds = read_roi_median_spectrum(
            str(h5),
            REFLECTANCE_PATH,
            WAVELENGTH_PATH,
            r,
            c,
            roi=args.roi,
        )

        # convert µm -> nm if needed
        wl = wl.astype(float)
        if float(np.nanmax(wl)) < 50.0:
            wl *= 1000.0

        spec = spec.astype(float)

        # scale reflectance if stored as scaled integers
        if np.nanmax(spec) > 2.0:
            spec = spec / 10000.0

        finite_bands = int(np.isfinite(spec).sum())
        if finite_bands < 50:
            print(f"Skipping sample {sample_id}: too few valid bands ({finite_bands}).")
            continue

        if wavelengths_nm is None:
            wavelengths_nm = wl
        else:
            if len(wavelengths_nm) != len(wl):
                raise ValueError("Wavelength length mismatch across samples.")

        spectra.append(spec)
        labels.append(moisture)

        rmin, rmax, cmin, cmax = bounds
        summary_rows.append({
            "id": sample_id,
            "lat": lat,
            "lon": lon,
            "moisture": moisture,
            "row_raw": r0,
            "col_raw": c0,
            "row_snap": r,
            "col_snap": c,
            "snap_distance_px": float(np.sqrt((r - r0) ** 2 + (c - c0) ** 2)),
            "roi": args.roi,
            "rmin": rmin,
            "rmax": rmax,
            "cmin": cmin,
            "cmax": cmax,
            "finite_bands": finite_bands,
        })

        print(
            f"Kept sample {sample_id}: "
            f"({lat:.7f}, {lon:.7f}) -> raw (r={r0}, c={c0}) -> snapped (r={r}, c={c}), "
            f"finite bands={finite_bands}"
        )

    if not spectra:
        raise RuntimeError("No valid spectra were extracted.")

    X_spectra = np.vstack(spectra).astype(float)
    y_moisture = np.asarray(labels, dtype=float)
    wavelengths_nm = np.asarray(wavelengths_nm, dtype=float)

    out_npz = Path(args.out_npz)
    out_npz.parent.mkdir(parents=True, exist_ok=True)

    np.savez(
        out_npz,
        wavelengths_nm=wavelengths_nm,
        X_spectra=X_spectra,
        y_moisture=y_moisture,
    )

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summary_rows).to_csv(out_csv, index=False)

    print("\nSaved training data:", out_npz)
    print("Saved summary CSV :", out_csv)
    print("X_spectra shape   :", X_spectra.shape)
    print("y_moisture shape  :", y_moisture.shape)


if __name__ == "__main__":
    main()