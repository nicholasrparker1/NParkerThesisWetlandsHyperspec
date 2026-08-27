from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.config import DATA_PROCESSED


DEFAULT_SOIL_SPECTRAL_TABLE = DATA_PROCESSED / "soil_spectral_table.csv"
DEFAULT_COVER_TABLE = DATA_PROCESSED / "point_cover_classification_soil_spectral_table.csv"
DEFAULT_WETLAND_CONTEXT_TABLE = DATA_PROCESSED / "NEON_Soil_Wetland_Context_Table.xlsx"
DEFAULT_OUT = DATA_PROCESSED / "hydric_evidence_table.csv"

SOIL_TARGET_COLUMNS = [
    "som_avg_pct",
    "carbon_pct",
    "nitrogen_pct",
    "hydrogen_pct",
    "w (%)",
    "moisture",
]

PROVENANCE_COLUMNS = [
    "sampling_point_id",
    "sample_id",
    "soil_core_id",
    "sample_id_written_on_bag",
    "plotID",
    "plot_id_parent",
    "siteID",
    "area",
    "habitat_type",
    "hydrology",
    "lat",
    "lon",
    "matched_h5",
    "row",
    "col",
    "snapped_row",
    "snapped_col",
    "snap_distance_px",
    "roi",
    "epsg",
]

COVER_COLUMNS = [
    "cover_class",
    "usable_for_soil_retrieval",
    "quality_flag",
    "soil_likelihood",
    "vegetation_likelihood",
    "water_likelihood",
    "ndvi",
    "ndwi",
    "mndwi",
    "ndmi",
    "nbr2",
]

WETLAND_CONTEXT_COLUMNS = [
    "inside_nwi_wetland",
    "within_10m_of_nwi_wetland",
    "inside_or_within_10m_nwi_wetland",
    "distance_to_nearest_wetland_m",
    "nearest_nwi_class",
    "nearest_nwi_system",
    "wetland_group",
    "wetland_context",
    "nearest_wetland_area_m2",
]

WETLAND_ADJACENT_DISTANCE_M = 10.0


def _read_table(path: Path, *, sheet_name: str | int | None = None) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Input table not found: {path}")
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path, sheet_name=0 if sheet_name is None else sheet_name)
    return pd.read_csv(path)


def _reflectance_columns(df: pd.DataFrame) -> list[str]:
    return [col for col in df.columns if str(col).startswith("refl_")]


def _first_existing(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _point_key(df: pd.DataFrame) -> pd.Series:
    id_col = _first_existing(
        df,
        ["sampling_point_id", "sample_id", "soil_core_id", "id", "sample_id_written_on_bag"],
    )
    if id_col is not None:
        return df[id_col].astype(str).str.strip()
    if {"lat", "lon"}.issubset(df.columns):
        lat = pd.to_numeric(df["lat"], errors="coerce").round(7).astype(str)
        lon = pd.to_numeric(df["lon"], errors="coerce").round(7).astype(str)
        return lat + "," + lon
    raise ValueError("Table needs a point ID column or lat/lon columns.")


def _available_columns(df: pd.DataFrame, columns: list[str]) -> list[str]:
    return [col for col in columns if col in df.columns]


def _finite_band_summary(df: pd.DataFrame, refl_cols: list[str]) -> pd.DataFrame:
    if not refl_cols:
        return pd.DataFrame(
            {
                "reflectance_band_count": np.zeros(len(df), dtype=int),
                "finite_reflectance_band_count": np.zeros(len(df), dtype=int),
                "finite_reflectance_fraction": np.nan,
            }
        )

    refl = df[refl_cols].apply(pd.to_numeric, errors="coerce")
    finite_count = refl.notna().sum(axis=1)
    return pd.DataFrame(
        {
            "reflectance_band_count": len(refl_cols),
            "finite_reflectance_band_count": finite_count,
            "finite_reflectance_fraction": finite_count / float(len(refl_cols)),
        }
    )


def _merge_cover(evidence: pd.DataFrame, cover_path: Path | None) -> pd.DataFrame:
    if cover_path is None or not cover_path.exists():
        evidence["cover_table_used"] = False
        return evidence

    cover = _read_table(cover_path)
    cover = cover.copy()
    cover["evidence_point_key"] = _point_key(cover)
    keep = ["evidence_point_key", *_available_columns(cover, COVER_COLUMNS)]
    cover = cover[keep].drop_duplicates("evidence_point_key")

    merged = evidence.merge(cover, on="evidence_point_key", how="left")
    merged["cover_table_used"] = True
    return merged


def _merge_wetland_context(evidence: pd.DataFrame, wetland_context_path: Path | None) -> pd.DataFrame:
    existing_context = _available_columns(evidence, WETLAND_CONTEXT_COLUMNS)
    if existing_context:
        evidence["wetland_context_table_used"] = False
        evidence["wetland_context_matched"] = True
        return evidence
    if wetland_context_path is None or not wetland_context_path.exists():
        evidence["wetland_context_table_used"] = False
        evidence["wetland_context_matched"] = False
        return evidence

    context = _read_table(wetland_context_path, sheet_name="Plot_Wetland_Context")
    context = context.copy()
    if "plotID" not in context.columns:
        raise ValueError(f"{wetland_context_path} needs a plotID column in Plot_Wetland_Context.")

    context["wetland_plot_key"] = context["plotID"].astype(str).str.strip()
    keep = ["wetland_plot_key", *_available_columns(context, WETLAND_CONTEXT_COLUMNS)]
    context = context[keep].drop_duplicates("wetland_plot_key")

    evidence = evidence.copy()
    plot_col = _first_existing(evidence, ["plotID", "plot_id_parent"])
    if plot_col is None:
        evidence["wetland_context_table_used"] = False
        return evidence

    evidence["wetland_plot_key"] = evidence[plot_col].astype(str).str.strip()
    merged = evidence.merge(context, on="wetland_plot_key", how="left")
    merged["wetland_context_table_used"] = True
    merged["wetland_context_matched"] = merged[_available_columns(merged, WETLAND_CONTEXT_COLUMNS)].notna().any(axis=1)
    return merged.drop(columns=["wetland_plot_key"])


def _apply_10m_wetland_rule(evidence: pd.DataFrame) -> pd.DataFrame:
    if "distance_to_nearest_wetland_m" not in evidence.columns:
        return evidence

    evidence = evidence.copy()
    distance = pd.to_numeric(evidence["distance_to_nearest_wetland_m"], errors="coerce")
    inside = (
        evidence["inside_nwi_wetland"].astype(str).str.strip().str.lower().eq("yes")
        if "inside_nwi_wetland" in evidence.columns
        else pd.Series(False, index=evidence.index)
    )
    known_context = distance.notna() | inside
    within_10m = inside | (distance <= WETLAND_ADJACENT_DISTANCE_M)

    evidence["within_10m_of_nwi_wetland"] = np.select(
        [within_10m, known_context],
        ["Yes", "No"],
        default="",
    )
    evidence["inside_or_within_10m_nwi_wetland"] = np.select(
        [within_10m, known_context],
        ["Yes", "No"],
        default="",
    )
    evidence["wetland_context"] = np.select(
        [inside, within_10m, known_context],
        ["Inside wetland", "Wetland-adjacent", "Not within 10 m"],
        default="Unknown",
    )
    if "wetland_group" in evidence.columns:
        evidence.loc[evidence["wetland_context"].eq("Not within 10 m"), "wetland_group"] = "None"
    return evidence


def build_evidence_table(
    soil_spectral_table: Path,
    out: Path,
    *,
    cover_table: Path | None = None,
    wetland_context_table: Path | None = None,
) -> pd.DataFrame:
    soil = _read_table(soil_spectral_table)
    soil = soil.copy()
    soil["evidence_point_key"] = _point_key(soil)

    refl_cols = _reflectance_columns(soil)
    columns = [
        "evidence_point_key",
        *_available_columns(soil, PROVENANCE_COLUMNS),
        *_available_columns(soil, SOIL_TARGET_COLUMNS),
    ]
    evidence = soil[columns].copy()
    evidence = pd.concat([evidence, _finite_band_summary(soil, refl_cols)], axis=1)
    evidence = _merge_cover(evidence, cover_table)
    evidence = _merge_wetland_context(evidence, wetland_context_table)
    evidence = _apply_10m_wetland_rule(evidence)

    target_cols = _available_columns(evidence, SOIL_TARGET_COLUMNS)
    for col in target_cols:
        evidence[f"has_{col.replace(' ', '_').replace('(', '').replace(')', '').replace('%', 'pct')}"] = (
            pd.to_numeric(evidence[col], errors="coerce").notna()
        )

    if "usable_for_soil_retrieval" not in evidence.columns:
        evidence["usable_for_soil_retrieval"] = ""
    if "quality_flag" not in evidence.columns:
        evidence["quality_flag"] = ""

    out.parent.mkdir(parents=True, exist_ok=True)
    evidence.to_csv(out, index=False)
    return evidence


def _summary(df: pd.DataFrame, out: Path) -> list[str]:
    lines = [
        f"Saved hydric evidence table: {out}",
        f"Rows: {len(df)}",
        f"Columns: {len(df.columns)}",
    ]
    if "usable_for_soil_retrieval" in df.columns:
        counts = df["usable_for_soil_retrieval"].astype(str).value_counts(dropna=False)
        lines.append("Usable-for-soil-retrieval counts:")
        lines.extend(f"  {key}: {value}" for key, value in counts.items())
    if "cover_class" in df.columns:
        counts = df["cover_class"].astype(str).value_counts(dropna=False)
        lines.append("Cover classes:")
        lines.extend(f"  {key}: {value}" for key, value in counts.items())
    return lines


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Build a compact hydric-soil evidence table from existing soil "
            "spectral and optional cover-screening outputs."
        )
    )
    ap.add_argument("--soil-spectral-table", default=str(DEFAULT_SOIL_SPECTRAL_TABLE))
    ap.add_argument("--cover-table", default=None, help="Optional point cover classification CSV")
    ap.add_argument("--wetland-context-table", default=None, help="Optional NWI wetland context workbook/CSV")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    cover_table = Path(args.cover_table) if args.cover_table else None
    wetland_context_table = Path(args.wetland_context_table) if args.wetland_context_table else None
    df = build_evidence_table(
        Path(args.soil_spectral_table),
        Path(args.out),
        cover_table=cover_table,
        wetland_context_table=wetland_context_table,
    )
    print("\n".join(_summary(df, Path(args.out))))


if __name__ == "__main__":
    main()
