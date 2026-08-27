from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src.io_hyperspectral import read_roi_median_spectrum, snap_to_valid_pixel
from src.models.cover_classification import compute_cover_features, cover_features_to_dict
from src.workflow import find_h5_files, find_h5_for_point, normalize_reflectance, normalize_wavelengths_nm


DEFAULT_WETLAND_XLSX = Path("data/processed/NEON_Soil_Wetland_Context_Table.xlsx")
DEFAULT_OUT = Path("data/processed/NEON_Soil_Wetland_Cover_Classification.xlsx")
PLOT_SHEET = "Plot_Wetland_Context"


def _extract_clean_roi_spectrum_from_files(
    h5_files: list[Path],
    lat: float,
    lon: float,
    *,
    snap: int,
    roi: int,
) -> tuple[np.ndarray, np.ndarray, tuple[int, int], Path]:
    match = find_h5_for_point(lat, lon, h5_files)
    if match is None:
        raise RuntimeError(f"Point ({lat}, {lon}) is not inside any available H5 tile.")

    row, col = snap_to_valid_pixel(
        str(match.h5_path),
        match.reflectance_path,
        match.row,
        match.col,
        radius=snap,
        band=0,
    )
    if row is None or col is None:
        raise RuntimeError(f"No valid pixel found within radius={snap} for lat/lon=({lat}, {lon}).")

    wavelengths, spectrum, _bounds = read_roi_median_spectrum(
        str(match.h5_path),
        match.reflectance_path,
        match.wavelength_path,
        row,
        col,
        roi=roi,
    )
    wavelengths = normalize_wavelengths_nm(wavelengths)
    spectrum = normalize_reflectance(spectrum)
    spectrum[(spectrum <= 0.0) | (spectrum >= 1.2)] = np.nan
    return wavelengths, spectrum, (row, col), match.h5_path


def classify_wetland_context_cover(
    wetland_xlsx: Path,
    out_xlsx: Path,
    *,
    roi: int,
    snap: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if roi < 1 or roi % 2 == 0:
        raise ValueError("--roi must be an odd integer >= 1")
    if not wetland_xlsx.exists():
        raise FileNotFoundError(f"Wetland context workbook not found: {wetland_xlsx}")

    plots = pd.read_excel(wetland_xlsx, sheet_name=PLOT_SHEET)
    required = {"siteID", "plotID", "decimalLatitude", "decimalLongitude", "wetland_context"}
    missing = required - set(plots.columns)
    if missing:
        raise ValueError(f"{PLOT_SHEET} is missing required columns: {', '.join(sorted(missing))}")

    h5_files = find_h5_files()
    print("H5 files available for cover classification:")
    for h5 in h5_files:
        print(" -", h5.name)

    rows: list[dict[str, object]] = []
    for plot in plots.itertuples(index=False):
        site_id = str(getattr(plot, "siteID"))
        plot_id = str(getattr(plot, "plotID"))
        lat = float(getattr(plot, "decimalLatitude"))
        lon = float(getattr(plot, "decimalLongitude"))
        print(f"Classifying {plot_id}...")

        row = plot._asdict()
        row.update(
            {
                "id": f"{site_id}_{plot_id}",
                "roi_px": roi,
                "snap_px": snap,
                "h5_file": "",
                "row": "",
                "col": "",
                "finite_bands": 0,
                "classification_error": "",
            }
        )

        try:
            wl, spec, rc, h5_path = _extract_clean_roi_spectrum_from_files(
                h5_files,
                lat,
                lon,
                snap=snap,
                roi=roi,
            )
            features = compute_cover_features(wl, spec)
            row.update(
                {
                    "h5_file": h5_path.name,
                    "row": rc[0],
                    "col": rc[1],
                    "finite_bands": int(np.sum(np.isfinite(spec))),
                }
            )
            row.update(cover_features_to_dict(features))
        except Exception as exc:
            row.update(
                {
                    "green": np.nan,
                    "red": np.nan,
                    "nir": np.nan,
                    "swir1": np.nan,
                    "swir2": np.nan,
                    "visible_mean": np.nan,
                    "nir_swir_mean": np.nan,
                    "ndvi": np.nan,
                    "ndwi": np.nan,
                    "mndwi": np.nan,
                    "ndmi": np.nan,
                    "nbr2": np.nan,
                    "soil_likelihood": np.nan,
                    "vegetation_likelihood": np.nan,
                    "water_likelihood": np.nan,
                    "cover_class": "not_classified",
                    "usable_for_soil_retrieval": False,
                    "quality_flag": "no_matching_h5_or_extraction_failed",
                    "classification_error": str(exc),
                }
            )
        rows.append(row)

    classified = pd.DataFrame(rows)
    summary = (
        classified.groupby(["siteID", "wetland_context", "cover_class"], dropna=False)
        .size()
        .rename("plot_count")
        .reset_index()
        .sort_values(["siteID", "wetland_context", "cover_class"])
    )

    out_xlsx.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out_xlsx, engine="openpyxl") as writer:
        classified.to_excel(writer, sheet_name="Plot_Wetland_Cover", index=False)
        summary.to_excel(writer, sheet_name="Summary", index=False)

    return classified, summary


def _print_summary(classified: pd.DataFrame) -> None:
    print("\nCover classification summary")
    print(f"Total plots: {len(classified)}")
    print(f"Classified with spectra: {int(classified['classification_error'].eq('').sum())}")
    print(f"Not classified: {int(classified['classification_error'].ne('').sum())}")
    print("\nCover classes:")
    print(classified["cover_class"].value_counts(dropna=False).to_string())
    print("\nUsable for soil retrieval by wetland context:")
    usable = pd.crosstab(classified["wetland_context"], classified["usable_for_soil_retrieval"])
    print(usable.to_string())


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Classify NEON wetland-context soil plots as bare soil, vegetation, water, or mixed cover."
    )
    ap.add_argument("--wetland-xlsx", default=str(DEFAULT_WETLAND_XLSX), help="Wetland context workbook")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="Output Excel workbook")
    ap.add_argument("--roi", type=int, default=3, help="Odd ROI size in pixels")
    ap.add_argument("--snap", type=int, default=5, help="Nearest-valid-pixel search radius")
    args = ap.parse_args()

    try:
        classified, _summary = classify_wetland_context_cover(
            Path(args.wetland_xlsx),
            Path(args.out),
            roi=args.roi,
            snap=args.snap,
        )
    except Exception as e:
        raise SystemExit(f"ERROR: {e}") from e

    print(f"\nSaved workbook: {Path(args.out)}")
    _print_summary(classified)


if __name__ == "__main__":
    main()
