from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd
from pyproj import Transformer


DEFAULT_SOIL_XLSX = Path("data/field/NEON_Master_Soil_Table.xlsx")
DEFAULT_CANDIDATES = Path("data/processed/neon_aop_required_tile_manifest.csv")
DEFAULT_WETLAND_XLSX = Path("data/processed/NEON_Soil_Wetland_Context_Table.xlsx")
DEFAULT_COVER_XLSX = Path("data/processed/NEON_Soil_Wetland_Cover_Classification.xlsx")
DEFAULT_AUDIT_XLSX = Path("data/processed/neon_aop_tile_requirement_audit.xlsx")
DEFAULT_MINIMUM_CSV = Path("data/processed/neon_aop_minimum_required_download_list.csv")
DEFAULT_PRIORITY_CSV = Path("data/processed/neon_aop_priority_download_list.csv")
TILE_SIZE_M = 1000

SITE_DOMAINS = {
    "CPER": "D10",
    "DCFS": "D09",
    "NOGP": "D09",
    "SJER": "D17",
    "SRER": "D14",
    "WOOD": "D09",
}
SITE_AOP_CODES = {
    "CPER": "CPER",
    "DCFS": "WOOD",
    "NOGP": "NOGP",
    "SJER": "SJER",
    "SRER": "SRER",
    "WOOD": "WOOD",
}
SITE_UTM_ZONES = {
    "CPER": 13,
    "DCFS": 14,
    "NOGP": 14,
    "SJER": 11,
    "SRER": 12,
    "WOOD": 14,
}
SITE_MONTHS = {
    "CPER": "2024-06",
    "DCFS": "2025-06",
    "NOGP": "2025-06",
    "SJER": "2026-04",
    "SRER": "2025-09",
    "WOOD": "2025-06",
}


def _find_column(df: pd.DataFrame, names: list[str]) -> str:
    lookup = {str(col).strip().lower(): col for col in df.columns}
    for name in names:
        found = lookup.get(name.lower())
        if found is not None:
            return found
    raise ValueError(f"Missing required column. Tried: {', '.join(names)}")


def _load_unique_soil_plots(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path)
    site_col = _find_column(df, ["siteID", "site_id"])
    plot_col = _find_column(df, ["plotID", "plot_id"])
    lat_col = _find_column(df, ["decimalLatitude", "latitude", "lat"])
    lon_col = _find_column(df, ["decimalLongitude", "longitude", "lon", "long"])

    plots = df[[site_col, plot_col, lat_col, lon_col]].rename(
        columns={
            site_col: "siteID",
            plot_col: "plotID",
            lat_col: "decimalLatitude",
            lon_col: "decimalLongitude",
        }
    )
    plots["decimalLatitude"] = pd.to_numeric(plots["decimalLatitude"], errors="coerce")
    plots["decimalLongitude"] = pd.to_numeric(plots["decimalLongitude"], errors="coerce")
    plots = plots.dropna(subset=["siteID", "plotID", "decimalLatitude", "decimalLongitude"])
    plots = plots.drop_duplicates(["siteID", "plotID"]).copy()
    plots["siteID"] = plots["siteID"].astype(str)
    plots["plotID"] = plots["plotID"].astype(str)
    return plots.sort_values(["siteID", "plotID"]).reset_index(drop=True)


def _load_wetland_context(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["siteID", "plotID", "wetland_context"])
    df = pd.read_excel(path, sheet_name="Plot_Wetland_Context")
    keep = [col for col in ["siteID", "plotID", "wetland_context", "inside_nwi_wetland"] if col in df.columns]
    return df[keep].copy()


def _load_cover_flags(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["siteID", "plotID", "cover_class", "usable_for_soil_retrieval"])
    df = pd.read_excel(path, sheet_name="Plot_Wetland_Cover")
    keep = [col for col in ["siteID", "plotID", "cover_class", "usable_for_soil_retrieval"] if col in df.columns]
    return df[keep].copy()


def _tile_for_plot(site: str, lat: float, lon: float) -> dict[str, object]:
    zone = SITE_UTM_ZONES[site]
    transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{32600 + zone}", always_xy=True)
    easting, northing = transformer.transform(lon, lat)
    tile_easting = int(easting // TILE_SIZE_M * TILE_SIZE_M)
    tile_northing = int(northing // TILE_SIZE_M * TILE_SIZE_M)
    aop_site = SITE_AOP_CODES[site]
    domain = SITE_DOMAINS[site]
    tile_name = f"NEON_{domain}_{aop_site}_DP3_{tile_easting}_{tile_northing}_bidirectional_reflectance.h5"
    inside = (
        tile_easting <= easting < tile_easting + TILE_SIZE_M
        and tile_northing <= northing < tile_northing + TILE_SIZE_M
    )
    return {
        "aop_site": aop_site,
        "domain": domain,
        "month": SITE_MONTHS[site],
        "utm_zone": zone,
        "plot_utm_easting": easting,
        "plot_utm_northing": northing,
        "tile_easting": tile_easting,
        "tile_northing": tile_northing,
        "tile_name": tile_name,
        "point_intersects_tile": inside,
    }


def _estimate_tile_size_gb(raw_dir: Path) -> float:
    pattern = re.compile(r"NEON_D\d+_[A-Z0-9]+_DP3_\d+_\d+_bidirectional_reflectance\.h5$")
    sizes = [path.stat().st_size for path in raw_dir.glob("*.h5") if pattern.match(path.name.lstrip("1"))]
    if not sizes:
        return 0.65
    return sum(sizes) / len(sizes) / (1024**3)


def build_audit(
    soil_xlsx: Path,
    candidate_csv: Path,
    wetland_xlsx: Path,
    cover_xlsx: Path,
    raw_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    plots = _load_unique_soil_plots(soil_xlsx)
    wetland = _load_wetland_context(wetland_xlsx)
    cover = _load_cover_flags(cover_xlsx)
    plots = plots.merge(wetland, on=["siteID", "plotID"], how="left")
    plots = plots.merge(cover, on=["siteID", "plotID"], how="left")

    tile_rows = []
    for plot in plots.itertuples(index=False):
        row = plot._asdict()
        row.update(_tile_for_plot(row["siteID"], row["decimalLatitude"], row["decimalLongitude"]))
        row["is_bare_soil_candidate"] = (
            str(row.get("cover_class", "")).lower() == "bare_soil_candidate"
            or bool(row.get("usable_for_soil_retrieval", False)) is True
        )
        row["is_wetland_associated"] = str(row.get("wetland_context", "")).lower() in {
            "inside wetland",
            "wetland-adjacent",
        }
        row["is_transition_zone"] = str(row.get("wetland_context", "")).lower() == "transition zone"
        tile_rows.append(row)
    plot_tile_map = pd.DataFrame(tile_rows)

    required = (
        plot_tile_map.groupby(
            ["siteID", "aop_site", "month", "domain", "utm_zone", "tile_easting", "tile_northing", "tile_name"],
            as_index=False,
        )
        .agg(
            plot_ids_covered=("plotID", lambda vals: ",".join(vals)),
            number_of_plots=("plotID", "size"),
            all_points_intersect_tile=("point_intersects_tile", "all"),
            has_multiple_plots=("plotID", lambda vals: len(vals) > 1),
            has_bare_soil_candidate=("is_bare_soil_candidate", "any"),
            has_wetland_associated_plot=("is_wetland_associated", "any"),
            has_transition_zone_plot=("is_transition_zone", "any"),
        )
        .sort_values(["siteID", "tile_easting", "tile_northing"])
    )
    required["required"] = "Yes"
    required["reason"] = required.apply(
        lambda row: (
            f"Contains {row['number_of_plots']} soil plot(s); projected point(s) intersect the 1 km tile footprint."
            if row["all_points_intersect_tile"]
            else "Contains mapped plot(s), but at least one point failed the footprint check."
        ),
        axis=1,
    )

    candidates = pd.read_csv(candidate_csv)
    candidates["candidate_tile"] = True
    audit = candidates.merge(
        required,
        on=["siteID", "aop_site", "month", "domain", "tile_easting", "tile_northing", "tile_name"],
        how="outer",
        suffixes=("_candidate", ""),
    )
    audit["candidate_tile"] = audit["candidate_tile"].fillna(False)
    audit["required"] = audit["required"].fillna("No")
    audit["number_of_plots"] = audit["number_of_plots"].fillna(0).astype(int)
    audit["plot_ids_covered"] = audit["plot_ids_covered"].fillna("")
    audit["reason"] = audit["reason"].where(
        audit["required"].eq("Yes"),
        "Candidate tile does not contain any required soil plot.",
    )

    local_names = {path.name.lstrip("1") for path in raw_dir.glob("*.h5")}
    audit["already_local"] = audit["tile_name"].isin(local_names)
    minimum = audit[audit["required"].eq("Yes")].copy()

    priority = minimum[
        minimum["has_bare_soil_candidate"].fillna(False)
        | minimum["has_wetland_associated_plot"].fillna(False)
    ].copy()
    return plots, plot_tile_map, audit, minimum, priority


def _strategy_summary(
    plots: pd.DataFrame,
    audit: pd.DataFrame,
    minimum: pd.DataFrame,
    priority: pd.DataFrame,
    avg_tile_gb: float,
) -> pd.DataFrame:
    candidate_n = int(audit["candidate_tile"].sum())
    required_n = len(minimum)
    priority_n = len(priority)
    reduction = 0.0 if candidate_n == 0 else 100.0 * (candidate_n - required_n) / candidate_n
    priority_reduction = 0.0 if required_n == 0 else 100.0 * (required_n - priority_n) / required_n
    return pd.DataFrame(
        [
            {"metric": "unique_soil_plots", "value": len(plots)},
            {"metric": "candidate_tiles", "value": candidate_n},
            {"metric": "required_tiles", "value": required_n},
            {"metric": "candidate_to_required_reduction_pct", "value": round(reduction, 2)},
            {"metric": "required_tiles_already_local", "value": int(minimum["already_local"].sum())},
            {"metric": "required_tiles_to_download", "value": int((~minimum["already_local"]).sum())},
            {"metric": "tiles_with_multiple_plots", "value": int(minimum["has_multiple_plots"].fillna(False).sum())},
            {"metric": "tiles_with_bare_soil_candidates", "value": int(minimum["has_bare_soil_candidate"].fillna(False).sum())},
            {
                "metric": "tiles_with_wetland_associated_plots",
                "value": int(minimum["has_wetland_associated_plot"].fillna(False).sum()),
            },
            {"metric": "priority_tiles_bare_soil_or_wetland_associated", "value": priority_n},
            {"metric": "priority_reduction_from_all_required_pct", "value": round(priority_reduction, 2)},
            {"metric": "estimated_gb_per_tile_from_local_dp3_tiles", "value": round(avg_tile_gb, 2)},
            {"metric": "option_a_all_required_estimated_gb", "value": round(required_n * avg_tile_gb, 1)},
            {"metric": "option_b_priority_estimated_gb", "value": round(priority_n * avg_tile_gb, 1)},
        ]
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Audit NEON AOP tile requirements against soil plot coordinates.")
    ap.add_argument("--soil-xlsx", default=str(DEFAULT_SOIL_XLSX))
    ap.add_argument("--candidate-csv", default=str(DEFAULT_CANDIDATES))
    ap.add_argument("--wetland-xlsx", default=str(DEFAULT_WETLAND_XLSX))
    ap.add_argument("--cover-xlsx", default=str(DEFAULT_COVER_XLSX))
    ap.add_argument("--raw-dir", default="data/raw")
    ap.add_argument("--audit-xlsx", default=str(DEFAULT_AUDIT_XLSX))
    ap.add_argument("--minimum-csv", default=str(DEFAULT_MINIMUM_CSV))
    ap.add_argument("--priority-csv", default=str(DEFAULT_PRIORITY_CSV))
    args = ap.parse_args()

    plots, plot_tile_map, audit, minimum, priority = build_audit(
        Path(args.soil_xlsx),
        Path(args.candidate_csv),
        Path(args.wetland_xlsx),
        Path(args.cover_xlsx),
        Path(args.raw_dir),
    )
    avg_tile_gb = _estimate_tile_size_gb(Path(args.raw_dir))
    summary = _strategy_summary(plots, audit, minimum, priority, avg_tile_gb)

    audit_xlsx = Path(args.audit_xlsx)
    audit_xlsx.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(audit_xlsx, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Summary", index=False)
        audit.to_excel(writer, sheet_name="Candidate_Tile_Audit", index=False)
        minimum.to_excel(writer, sheet_name="Minimum_Download_List", index=False)
        priority.to_excel(writer, sheet_name="Priority_Download_List", index=False)
        plot_tile_map.to_excel(writer, sheet_name="Plot_Tile_Map", index=False)

    minimum.to_csv(args.minimum_csv, index=False)
    priority.to_csv(args.priority_csv, index=False)

    print(f"Saved audit workbook: {audit_xlsx}")
    print(f"Saved minimum list: {args.minimum_csv}")
    print(f"Saved priority list: {args.priority_csv}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
