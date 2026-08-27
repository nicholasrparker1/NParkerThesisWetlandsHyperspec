from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pyproj import Transformer

from src.config import DATA_PROCESSED
from src.io_hyperspectral import read_roi_mean_spectrum, snap_to_valid_pixel
from src.preprocess import build_bad_band_mask, build_invalid_value_mask
from src.workflow import find_h5_files, find_h5_for_point, normalize_reflectance, normalize_wavelengths_nm


DEFAULT_SOIL_XLSX = Path("data/field/ROCX_soil_good_points.xlsx")
DEFAULT_OUT = DATA_PROCESSED / "soil_spectral_table.csv"
MAX_ROI = 3

# Conservative literature-style exclusions for airborne VNIR-SWIR data.
# The 1300-1450 nm window deliberately masks the shoulder around 1350 nm,
# where apparent correlations can be dominated by water/atmospheric effects.
CONSERVATIVE_BROAD_BAD_WINDOWS_NM = [
    (1300.0, 1450.0),
    (1800.0, 1950.0),
    (2400.0, np.inf),
]


def _clean_column_name(name: Any) -> str:
    return str(name).strip()


def _find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lookup = {_clean_column_name(col).lower(): col for col in df.columns}
    for candidate in candidates:
        found = lookup.get(candidate.lower())
        if found is not None:
            return found
    return None


def _sample_id(row: pd.Series, df: pd.DataFrame, fallback_index: int) -> str:
    id_col = _find_column(
        df,
        [
            "id",
            "sample_id",
            "sampling_point_id",
            "soil_core_id",
            "sample_id_written_on_bag",
        ],
    )
    if id_col is None or pd.isna(row[id_col]) or str(row[id_col]).strip() == "":
        return f"soil_{fallback_index + 1}"
    return str(row[id_col]).strip()


def _read_soil_workbook(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Soil input not found: {path}")

    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        try:
            df = pd.read_excel(path)
        except ImportError as e:
            raise ImportError(
                "Reading .xlsx files requires openpyxl. Install project requirements or run from the project virtualenv."
            ) from e

    df.columns = [_clean_column_name(col) for col in df.columns]
    if df.empty:
        raise RuntimeError(f"No soil rows found in {path}")
    return df


def _coerce_numeric_column(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(df[col], errors="coerce")


def _add_lat_lon_if_needed(df: pd.DataFrame, default_epsg: int) -> tuple[pd.DataFrame, int]:
    lat_col = _find_column(df, ["lat", "latitude"])
    lon_col = _find_column(df, ["lon", "longitude", "long"])
    epsg_col = _find_column(df, ["epsg", "utm_epsg", "coord_epsg", "coordinate_epsg"])

    epsg = default_epsg
    if epsg_col is not None:
        epsg_values = pd.to_numeric(df[epsg_col], errors="coerce").dropna().unique()
        if len(epsg_values) > 0:
            epsg = int(epsg_values[0])

    if lat_col is not None and lon_col is not None:
        df["lat"] = _coerce_numeric_column(df, lat_col)
        df["lon"] = _coerce_numeric_column(df, lon_col)
        return df, epsg

    easting_col = _find_column(df, ["easting_m", "easting", "utm_easting", "x"])
    northing_col = _find_column(df, ["northing_m", "northing", "utm_northing", "y"])
    if easting_col is None or northing_col is None:
        raise ValueError(
            "Soil workbook must contain either lat/lon columns or UTM easting/northing columns."
        )

    easting = _coerce_numeric_column(df, easting_col)
    northing = _coerce_numeric_column(df, northing_col)
    transformer = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
    lon, lat = transformer.transform(easting.to_numpy(dtype=float), northing.to_numpy(dtype=float))
    df["lat"] = lat
    df["lon"] = lon
    return df, epsg


def _wavelength_column_name(wavelength_nm: float) -> str:
    rounded = f"{float(wavelength_nm):.1f}".replace(".", "_")
    return f"refl_{rounded}"


def _roi_bounds(row: int, col: int, roi: int, rows: int | None = None, cols: int | None = None) -> tuple[int, int, int, int]:
    half = roi // 2
    r0 = max(0, row - half)
    r1 = row + half + 1
    c0 = max(0, col - half)
    c1 = col + half + 1
    if rows is not None:
        r1 = min(rows, r1)
    if cols is not None:
        c1 = min(cols, c1)
    return r0, r1, c0, c1


def _clean_roi_mean_spectrum(wl: np.ndarray, spec: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    wl_nm = normalize_wavelengths_nm(wl)
    spec = normalize_reflectance(spec)

    bad_band_mask = build_bad_band_mask(
        wl_nm,
        broad_windows=CONSERVATIVE_BROAD_BAD_WINDOWS_NM,
        include_narrow=True,
    )
    invalid_mask = build_invalid_value_mask(spec, min_reflectance=0.0, max_reflectance=1.2)

    spec_clean = spec.astype(float, copy=True)
    spec_clean[bad_band_mask | invalid_mask] = np.nan
    return wl_nm, spec_clean


def _range_text(df: pd.DataFrame, col: str) -> str:
    if col not in df.columns:
        return "not found"
    values = pd.to_numeric(df[col], errors="coerce").dropna()
    if values.empty:
        return "no numeric values"
    return f"{values.min():.4g} to {values.max():.4g}"


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Build a combined soil chemistry + NEON hyperspectral reflectance table."
    )
    ap.add_argument("--soil-xlsx", default=str(DEFAULT_SOIL_XLSX), help="Soil workbook path")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="Output CSV path")
    ap.add_argument("--roi", type=int, default=3, help="Odd ROI size in pixels; maximum allowed is 3")
    ap.add_argument("--snap", type=int, default=40, help="Snap radius in pixels")
    ap.add_argument("--epsg", type=int, default=32618, help="Input UTM EPSG if workbook has no EPSG column")
    ap.add_argument("--first-n", type=int, default=None, help="Only process the first N soil rows after loading coordinates")
    args = ap.parse_args()

    if args.roi < 1 or args.roi % 2 == 0:
        raise ValueError("--roi must be an odd integer >= 1")
    if args.roi > MAX_ROI:
        raise ValueError(f"--roi must be <= {MAX_ROI} for this conservative soil-spectra workflow")
    if args.first_n is not None and args.first_n < 1:
        raise ValueError("--first-n must be >= 1")

    soil_path = Path(args.soil_xlsx)
    out_path = Path(args.out)

    df = _read_soil_workbook(soil_path)
    df, input_epsg = _add_lat_lon_if_needed(df, args.epsg)
    original_sample_count = len(df)
    if args.first_n is not None:
        df = df.head(args.first_n).copy()

    h5_files = find_h5_files()
    print("H5 files available:")
    for h5 in h5_files:
        print(" -", h5.name)

    output_rows: list[dict[str, Any]] = []
    skip_reasons: Counter[str] = Counter()
    wavelength_columns: list[str] | None = None

    for idx, soil_row in df.iterrows():
        sample_id = _sample_id(soil_row, df, idx)
        lat = soil_row.get("lat")
        lon = soil_row.get("lon")

        if pd.isna(lat) or pd.isna(lon):
            reason = "missing or invalid coordinates"
            skip_reasons[reason] += 1
            print(f"WARNING skipping {sample_id}: {reason}.")
            continue

        lat = float(lat)
        lon = float(lon)

        match = find_h5_for_point(lat, lon, h5_files)
        if match is None:
            reason = "not inside any discovered H5 bounds"
            skip_reasons[reason] += 1
            print(f"WARNING skipping {sample_id}: {reason} (lat={lat:.7f}, lon={lon:.7f}).")
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
            reason = f"no valid pixel within snap radius {args.snap}"
            skip_reasons[reason] += 1
            print(f"WARNING skipping {sample_id}: {reason}.")
            continue

        snap_distance = float(np.sqrt((snap_row - match.row) ** 2 + (snap_col - match.col) ** 2))

        try:
            r0, r1, c0, c1 = _roi_bounds(snap_row, snap_col, args.roi)
            wl, spec = read_roi_mean_spectrum(
                str(match.h5_path),
                match.reflectance_path,
                match.wavelength_path,
                r0,
                r1,
                c0,
                c1,
            )
            wl_nm, spec_clean = _clean_roi_mean_spectrum(wl, spec)
        except Exception as e:
            reason = f"spectrum extraction failed: {e}"
            skip_reasons[reason] += 1
            print(f"WARNING skipping {sample_id}: {reason}")
            continue

        finite_bands = int(np.isfinite(spec_clean).sum())
        if finite_bands == 0:
            reason = "no finite reflectance bands after masking"
            skip_reasons[reason] += 1
            print(f"WARNING skipping {sample_id}: {reason}.")
            continue

        current_wavelength_columns = [_wavelength_column_name(w) for w in wl_nm]
        if wavelength_columns is None:
            wavelength_columns = current_wavelength_columns
        elif wavelength_columns != current_wavelength_columns:
            reason = "wavelength grid mismatch"
            skip_reasons[reason] += 1
            print(f"WARNING skipping {sample_id}: {reason} for {match.h5_path.name}.")
            continue

        out_row = soil_row.to_dict()
        out_row.update(
            {
                "matched_h5": match.h5_path.name,
                "row": match.row,
                "col": match.col,
                "snapped_row": snap_row,
                "snapped_col": snap_col,
                "snap_distance_px": snap_distance,
                "roi": args.roi,
                "epsg": input_epsg,
            }
        )
        out_row.update(dict(zip(current_wavelength_columns, spec_clean)))
        output_rows.append(out_row)

        print(
            f"Kept {sample_id}: {match.h5_path.name} "
            f"raw (r={match.row}, c={match.col}) -> snapped (r={snap_row}, c={snap_col}), "
            f"finite bands={finite_bands}"
        )

    if not output_rows:
        raise RuntimeError("No soil spectra were extracted. Check coordinates, H5 coverage, snap radius, and ROI.")

    out_df = pd.DataFrame(output_rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False)

    print("\nSummary")
    print("-------")
    if args.first_n is not None:
        print(f"Input soil samples: first {len(df)} of {original_sample_count}")
    else:
        print(f"Input soil samples: {len(df)}")
    print(f"Matched/extracted: {len(output_rows)}")
    print(f"Skipped: {sum(skip_reasons.values())}")
    if skip_reasons:
        print("Skip reasons:")
        for reason, count in skip_reasons.items():
            print(f" - {reason}: {count}")
    else:
        print("Skip reasons: none")
    print(f"SOM range: {_range_text(df, 'som_avg_pct')}")
    print(f"Carbon range: {_range_text(df, 'carbon_pct')}")
    print(f"Nitrogen range: {_range_text(df, 'nitrogen_pct')}")
    print(f"Output CSV: {out_path}")


if __name__ == "__main__":
    main()
