from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_ROOT = Path("data/field/NEON_soil-periodic")
DEFAULT_OUT = Path("data/field/wood_neon_soil_chemistry_points.csv")


def _read_many(root: Path, token: str) -> pd.DataFrame:
    paths = sorted(root.rglob(f"*{token}*.csv"))
    if not paths:
        raise FileNotFoundError(f"No NEON files matching *{token}*.csv under {root}")

    frames = []
    for path in paths:
        df = pd.read_csv(path)
        df["source_file"] = str(path)
        df["source_month"] = _month_from_name(path.name) or _month_from_name(path.parent.name)
        frames.append(df)
    return pd.concat(frames, ignore_index=True, sort=False)


def _month_from_name(name: str) -> str | None:
    match = re.search(r"\.(\d{4}-\d{2})\.", name)
    return match.group(1) if match else None


def _mean_numeric(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[col], errors="coerce")


def _collapse_chemistry(chem: pd.DataFrame) -> pd.DataFrame:
    chem = chem.copy()
    chem["nitrogen_pct_value"] = _mean_numeric(chem, "nitrogenPercent")
    chem["carbon_pct_value"] = _mean_numeric(chem, "organicCPercent")
    chem["cn_ratio_value"] = _mean_numeric(chem, "CNratio")

    group_cols = ["sampleID", "cnSampleID"]
    keep_cols = [
        "domainID",
        "siteID",
        "plotID",
        "namedLocation",
        "plotType",
        "startDate",
        "collectDate",
        "sampleType",
        "source_month",
    ]
    keep_cols = [col for col in keep_cols if col in chem.columns]

    grouped = (
        chem.groupby(group_cols, dropna=False)
        .agg(
            nitrogen_pct=("nitrogen_pct_value", "mean"),
            carbon_pct=("carbon_pct_value", "mean"),
            cn_ratio=("cn_ratio_value", "mean"),
            chemistry_rows=("uid", "count"),
            **{col: (col, "first") for col in keep_cols},
        )
        .reset_index()
    )
    return grouped


def build_table(root: Path) -> pd.DataFrame:
    core = _read_many(root, "sls_soilCoreCollection")
    bgc = _read_many(root, "sls_bgcSubsampling")
    chem = _read_many(root, "sls_soilChemistry")

    chem_summary = _collapse_chemistry(chem)
    bgc_cols = [
        "sampleID",
        "cnSampleID",
        "horizon",
        "sampleCondition",
        "bgcArchiveMass",
        "bgcDataQF",
        "source_month",
    ]
    bgc_cols = [col for col in bgc_cols if col in bgc.columns]
    bgc_summary = bgc[bgc_cols].drop_duplicates(["sampleID", "cnSampleID"])

    core_cols = [
        "sampleID",
        "domainID",
        "siteID",
        "plotID",
        "namedLocation",
        "plotType",
        "nlcdClass",
        "coreCoordinateX",
        "coreCoordinateY",
        "geodeticDatum",
        "decimalLatitude",
        "decimalLongitude",
        "coordinateUncertainty",
        "elevation",
        "startDate",
        "collectDate",
        "sampleTiming",
        "horizon",
        "soilTemp",
        "litterDepth",
        "sampleTopDepth",
        "sampleBottomDepth",
        "soilCoreCount",
        "dataQF",
        "source_month",
    ]
    core_cols = [col for col in core_cols if col in core.columns]
    core_summary = core[core_cols].drop_duplicates(["sampleID"])

    joined = chem_summary.merge(
        bgc_summary,
        on=["sampleID", "cnSampleID"],
        how="left",
        suffixes=("", "_bgc"),
    ).merge(
        core_summary,
        on="sampleID",
        how="left",
        suffixes=("", "_core"),
    )

    joined["lat"] = pd.to_numeric(joined["decimalLatitude"], errors="coerce")
    joined["lon"] = pd.to_numeric(joined["decimalLongitude"], errors="coerce")
    joined["som_avg_pct"] = pd.to_numeric(joined["carbon_pct"], errors="coerce") * 1.724
    joined["sampling_point_id"] = joined["sampleID"].astype(str)
    joined["soil_core_id"] = joined["sampleID"].astype(str)
    joined["soil_date_collected"] = pd.to_datetime(joined["collectDate_core"], errors="coerce").dt.date.astype(str)
    joined["carbon_fraction_raw"] = pd.to_numeric(joined["carbon_pct"], errors="coerce") / 100.0
    joined["nitrogen_fraction_raw"] = pd.to_numeric(joined["nitrogen_pct"], errors="coerce") / 100.0

    good = (
        np.isfinite(joined["lat"])
        & np.isfinite(joined["lon"])
        & (
            np.isfinite(pd.to_numeric(joined["carbon_pct"], errors="coerce"))
            | np.isfinite(pd.to_numeric(joined["nitrogen_pct"], errors="coerce"))
        )
    )
    joined = joined.loc[good].copy()

    front_cols = [
        "sampling_point_id",
        "plotID_core",
        "soil_core_id",
        "siteID_core",
        "namedLocation_core",
        "plotType_core",
        "nlcdClass",
        "sampleTiming",
        "horizon_core",
        "sampleTopDepth",
        "sampleBottomDepth",
        "soil_date_collected",
        "collectDate_core",
        "sampleID",
        "cnSampleID",
        "som_avg_pct",
        "carbon_pct",
        "nitrogen_pct",
        "cn_ratio",
        "carbon_fraction_raw",
        "nitrogen_fraction_raw",
        "lat",
        "lon",
        "coordinateUncertainty",
        "coreCoordinateX",
        "coreCoordinateY",
        "chemistry_rows",
    ]
    front_cols = [col for col in front_cols if col in joined.columns]
    rest = [col for col in joined.columns if col not in front_cols]
    return joined[front_cols + rest].sort_values(["soil_date_collected", "sampling_point_id"])


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Join NEON WOOD DP1.10086.001 soil chemistry tables into the soil-spectral input format."
    )
    ap.add_argument("--root", default=str(DEFAULT_ROOT), help="Root folder of the extracted NEON soil-periodic download")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="Output CSV for build_soil_spectral_table")
    args = ap.parse_args()

    out = Path(args.out)
    table = build_table(Path(args.root))
    if table.empty:
        raise RuntimeError("No rows with coordinates and carbon/nitrogen chemistry were produced.")

    out.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(out, index=False)

    print(f"Saved: {out}")
    print(f"Rows with chemistry and coordinates: {len(table)}")
    print(f"Carbon rows: {pd.to_numeric(table['carbon_pct'], errors='coerce').notna().sum()}")
    print(f"Nitrogen rows: {pd.to_numeric(table['nitrogen_pct'], errors='coerce').notna().sum()}")
    print("Note: som_avg_pct is estimated as organicCPercent * 1.724 for screening.")


if __name__ == "__main__":
    main()
