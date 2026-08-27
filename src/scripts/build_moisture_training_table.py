from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src.io_hyperspectral import read_roi_median_spectrum, snap_to_valid_pixel
from src.workflow import find_h5_files, find_h5_for_point, normalize_reflectance, normalize_wavelengths_nm


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

    df = df[pd.to_numeric(df["moisture"], errors="coerce").notna()].copy()
    if df.empty:
        raise RuntimeError("No rows with numeric moisture values were found.")

    h5_files = find_h5_files()
    print("H5 files available:")
    for h5 in h5_files:
        print(" -", h5.name)

    spectra = []
    labels = []
    summary_rows = []
    wavelengths_nm = None

    for _, row in df.iterrows():
        sample_id = str(row["id"]).strip()
        lat = float(row["lat"])
        lon = float(row["lon"])
        moisture = float(row["moisture"])

        match = find_h5_for_point(lat, lon, h5_files)
        if match is None:
            print(f"Skipping sample {sample_id}: not inside any H5 tile.")
            continue

        snap_row, snap_col = snap_to_valid_pixel(
            str(match.h5_path),
            match.reflectance_path,
            match.row,
            match.col,
            radius=args.snap,
            band=0,
        )
        if snap_row is None or snap_col is None:
            print(f"Skipping sample {sample_id}: no valid pixel found within snap radius.")
            continue

        wl, spec, bounds = read_roi_median_spectrum(
            str(match.h5_path),
            match.reflectance_path,
            match.wavelength_path,
            snap_row,
            snap_col,
            roi=args.roi,
        )

        wl = normalize_wavelengths_nm(wl)
        spec = normalize_reflectance(spec)

        finite_bands = int(np.isfinite(spec).sum())
        if finite_bands < 50:
            print(f"Skipping sample {sample_id}: too few valid bands ({finite_bands}).")
            continue

        if wavelengths_nm is None:
            wavelengths_nm = wl
        elif len(wavelengths_nm) != len(wl):
            raise ValueError("Wavelength length mismatch across samples.")

        spectra.append(spec)
        labels.append(moisture)

        rmin, rmax, cmin, cmax = bounds
        summary_rows.append(
            {
                "id": sample_id,
                "lat": lat,
                "lon": lon,
                "moisture": moisture,
                "h5_file": match.h5_path.name,
                "row_raw": match.row,
                "col_raw": match.col,
                "row_snap": snap_row,
                "col_snap": snap_col,
                "snap_distance_px": float(np.sqrt((snap_row - match.row) ** 2 + (snap_col - match.col) ** 2)),
                "roi": args.roi,
                "rmin": rmin,
                "rmax": rmax,
                "cmin": cmin,
                "cmax": cmax,
                "finite_bands": finite_bands,
            }
        )

        print(
            f"Kept sample {sample_id}: ({lat:.7f}, {lon:.7f}) -> {match.h5_path.name} "
            f"raw (r={match.row}, c={match.col}) -> snapped (r={snap_row}, c={snap_col}), "
            f"finite bands={finite_bands}"
        )

    if not spectra:
        raise RuntimeError("No valid spectra were extracted.")

    X_spectra = np.vstack(spectra).astype(float)
    y_moisture = np.asarray(labels, dtype=float)
    wavelengths_nm = np.asarray(wavelengths_nm, dtype=float)

    out_npz = Path(args.out_npz)
    out_npz.parent.mkdir(parents=True, exist_ok=True)
    np.savez(out_npz, wavelengths_nm=wavelengths_nm, X_spectra=X_spectra, y_moisture=y_moisture)

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summary_rows).to_csv(out_csv, index=False)

    print("\nSaved training data:", out_npz)
    print("Saved summary CSV :", out_csv)
    print("X_spectra shape   :", X_spectra.shape)
    print("y_moisture shape  :", y_moisture.shape)


if __name__ == "__main__":
    main()
