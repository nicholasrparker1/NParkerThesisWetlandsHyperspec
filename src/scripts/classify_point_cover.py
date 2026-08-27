from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

from src.config import DATA_PROCESSED
from src.models.cover_classification import (
    compute_cover_features,
    cover_features_to_dict,
)
from src.spectral_workflow import extract_clean_roi_spectrum
from src.workflow import load_point_csv


def _write_rows(outpath: Path, rows: list[dict[str, object]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)

    outpath.parent.mkdir(parents=True, exist_ok=True)
    with open(outpath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _parse_include_ids(include_ids: str | None) -> set[str] | None:
    if include_ids is None:
        return None
    out = {part.strip() for part in include_ids.split(",") if part.strip()}
    return out or None


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Classify point/ROI spectra as bare soil, vegetation, water, "
            "mixed, or low-signal using NDVI/NDWI-style diagnostics."
        )
    )
    ap.add_argument("--points", required=True, help="CSV with at least id,lat,lon columns")
    ap.add_argument("--roi", type=int, default=3, help="Odd ROI size in pixels")
    ap.add_argument("--snap", type=int, default=5, help="Nearest-valid-pixel search radius")
    ap.add_argument("--include-ids", default=None, help="Optional comma-separated IDs to process")
    ap.add_argument("--out", default=None, help="Output CSV path")
    args = ap.parse_args()

    if args.roi < 1 or args.roi % 2 == 0:
        raise ValueError("--roi must be an odd integer >= 1")

    include_ids = _parse_include_ids(args.include_ids)
    points = load_point_csv(args.points)
    if include_ids is not None:
        points = [point for point in points if str(point.id) in include_ids]
        if not points:
            raise ValueError("--include-ids did not match any rows in --points")

    rows: list[dict[str, object]] = []
    for point in points:
        print(f"Classifying point {point.id}...")
        row: dict[str, object] = {
            "id": point.id,
            "lat": point.lat,
            "lon": point.lon,
            "roi_px": args.roi,
            "snap_px": args.snap,
        }

        for key, value in point.fields.items():
            if key not in row:
                row[key] = value

        try:
            wl, spec, rc = extract_clean_roi_spectrum(
                None,
                point.lat,
                point.lon,
                snap=args.snap,
                roi=args.roi,
            )
            features = compute_cover_features(wl, spec)
            row.update(
                {
                    "row": rc[0],
                    "col": rc[1],
                    "finite_bands": int(np.sum(np.isfinite(spec))),
                    "classification_error": "",
                }
            )
            row.update(cover_features_to_dict(features))

        except Exception as exc:
            row.update(
                {
                    "row": "",
                    "col": "",
                    "finite_bands": 0,
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
                    "cover_class": "error",
                    "usable_for_soil_retrieval": False,
                    "quality_flag": "classification_failed",
                    "classification_error": str(exc),
                }
            )

        rows.append(row)

    outpath = (
        Path(args.out)
        if args.out is not None
        else DATA_PROCESSED / f"point_cover_classification_{Path(args.points).stem}.csv"
    )
    _write_rows(outpath, rows)
    print("Saved point cover classification:", outpath)


if __name__ == "__main__":
    main()
