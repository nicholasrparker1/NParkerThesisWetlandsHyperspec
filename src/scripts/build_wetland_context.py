from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    import geopandas as gpd


DEFAULT_SOIL_XLSX = Path("data/field/NEON_Master_Soil_Table.xlsx")
DEFAULT_NWI_DIR = Path("data/raw/nwi")
DEFAULT_OUT = Path("data/processed/NEON_Soil_Wetland_Context_Table.xlsx")
WGS84 = "EPSG:4326"
DISTANCE_CRS = "EPSG:5070"
WETLAND_ADJACENT_DISTANCE_M = 10.0
CONTEXT_COLUMNS = [
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


def _require_geopandas():
    try:
        import geopandas as gpd
    except ImportError as e:
        raise ImportError(
            "This workflow requires geopandas. Install the project requirements, then rerun:\n"
            "  python -m pip install -r requirements.txt"
        ) from e
    return gpd


def _crs_to_string(crs: Any) -> str:
    try:
        from pyproj import CRS
    except ImportError:
        return str(crs)
    return CRS.from_user_input(crs).to_string()


def _clean_column_name(name: Any) -> str:
    return str(name).strip()


def _find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lookup = {_clean_column_name(col).lower(): col for col in df.columns}
    for candidate in candidates:
        found = lookup.get(candidate.lower())
        if found is not None:
            return found
    return None


def _require_column(df: pd.DataFrame, candidates: list[str], label: str) -> str:
    found = _find_column(df, candidates)
    if found is None:
        raise ValueError(f"Soil table is missing a required {label} column. Tried: {', '.join(candidates)}")
    return found


def _list_layers(path: Path) -> pd.DataFrame:
    gpd = _require_geopandas()
    if hasattr(gpd, "list_layers"):
        return gpd.list_layers(path)

    try:
        import fiona
    except ImportError as e:
        raise ImportError(
            "Layer discovery requires geopandas.list_layers or fiona. Update geopandas or install fiona."
        ) from e

    return pd.DataFrame({"name": fiona.listlayers(path)})


def _layer_names(layers: pd.DataFrame) -> list[str]:
    if "name" not in layers.columns:
        return [str(value) for value in layers.iloc[:, 0].tolist()]
    return [str(value) for value in layers["name"].tolist()]


def _read_layer_sample(path: Path, layer: str) -> gpd.GeoDataFrame:
    gpd = _require_geopandas()
    try:
        return gpd.read_file(path, layer=layer, rows=100)
    except TypeError:
        return gpd.read_file(path, layer=layer).head(100)


def _geometry_is_polygon(gdf: "gpd.GeoDataFrame") -> bool:
    if gdf.empty or "geometry" not in gdf:
        return False
    geom_types = set(gdf.geometry.dropna().geom_type.str.lower())
    return any("polygon" in geom_type for geom_type in geom_types)


def _choose_wetland_polygon_layer(path: Path) -> str:
    layers = _list_layers(path)
    names = _layer_names(layers)
    print(f"\nLayers in {path}:")
    for name in names:
        print(f" - {name}")

    scored: list[tuple[int, str]] = []
    for name in names:
        lower = name.lower()
        if "metadata" in lower or "historic" in lower:
            continue
        if "riparian" in lower and "wetland" not in lower:
            continue

        score = 0
        if "wetland" in lower:
            score += 10
        if "polygon" in lower or "poly" in lower:
            score += 4
        if lower.endswith("_wetlands") or lower == "wetlands":
            score += 4
        if "riparian" in lower:
            score -= 3

        try:
            sample = _read_layer_sample(path, name)
        except Exception as e:
            print(f"   WARNING could not sample layer {name}: {e}")
            continue
        if _geometry_is_polygon(sample):
            score += 20
        else:
            continue
        if _find_column(sample, ["ATTRIBUTE", "WETLAND_TYPE", "SYSTEM", "CLASS1", "Cowardin_Code"]) is not None:
            score += 4

        scored.append((score, name))

    if not scored:
        raise RuntimeError(f"No likely wetland polygon layer found in {path}")

    scored.sort(reverse=True)
    selected = scored[0][1]
    print(f"Selected polygon layer: {selected}")
    return selected


def _choose_state_boundary_layer(path: Path) -> str | None:
    names = _layer_names(_list_layers(path))
    for name in names:
        lower = name.lower()
        if any(token in lower for token in ["wetland", "riparian", "metadata", "historic"]):
            continue
        try:
            sample = _read_layer_sample(path, name)
        except Exception:
            continue
        if _geometry_is_polygon(sample):
            return name
    return None


def _plots_inside_package_boundary(path: Path, plots_wgs84: "gpd.GeoDataFrame") -> "gpd.GeoDataFrame":
    boundary_layer = _choose_state_boundary_layer(path)
    if boundary_layer is None:
        print(f"WARNING no state boundary layer found in {path.name}; using all plots for this file.")
        return plots_wgs84

    try:
        boundary = _require_geopandas().read_file(path, layer=boundary_layer)
    except Exception as e:
        print(f"WARNING could not read boundary layer {boundary_layer} in {path.name}: {e}; using all plots.")
        return plots_wgs84

    if boundary.empty or boundary.crs is None:
        print(f"WARNING boundary layer {boundary_layer} in {path.name} is empty or missing CRS; using all plots.")
        return plots_wgs84

    plots_in_boundary_crs = plots_wgs84.to_crs(boundary.crs)
    state_shape = boundary.geometry.union_all()
    mask = plots_in_boundary_crs.geometry.within(state_shape) | plots_in_boundary_crs.geometry.intersects(state_shape)
    selected = plots_wgs84.loc[mask.to_numpy()].copy()
    print(f"Plots inside {boundary_layer}: {len(selected)}")
    return selected


def _read_soil_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Soil master table not found: {path}")
    df = pd.read_excel(path)
    df.columns = [_clean_column_name(col) for col in df.columns]
    if df.empty:
        raise RuntimeError(f"No rows found in soil table: {path}")
    return df


def _build_plot_points(horizon_df: pd.DataFrame) -> "gpd.GeoDataFrame":
    gpd = _require_geopandas()
    site_col = _require_column(horizon_df, ["siteID", "site_id"], "site ID")
    plot_col = _require_column(horizon_df, ["plotID", "plot_id"], "plot ID")
    lat_col = _require_column(horizon_df, ["decimalLatitude", "latitude", "lat"], "latitude")
    lon_col = _require_column(horizon_df, ["decimalLongitude", "longitude", "lon", "long"], "longitude")

    plot_df = horizon_df[[site_col, plot_col, lat_col, lon_col]].drop_duplicates([site_col, plot_col]).copy()
    plot_df = plot_df.rename(
        columns={
            site_col: "siteID",
            plot_col: "plotID",
            lat_col: "decimalLatitude",
            lon_col: "decimalLongitude",
        }
    )
    plot_df["decimalLatitude"] = pd.to_numeric(plot_df["decimalLatitude"], errors="coerce")
    plot_df["decimalLongitude"] = pd.to_numeric(plot_df["decimalLongitude"], errors="coerce")
    missing = plot_df["decimalLatitude"].isna() | plot_df["decimalLongitude"].isna()
    if missing.any():
        print(f"WARNING dropping {int(missing.sum())} plot(s) with missing coordinates before spatial join.")
        plot_df = plot_df.loc[~missing].copy()
    if plot_df.empty:
        raise RuntimeError("No unique plots with valid coordinates were found.")

    return gpd.GeoDataFrame(
        plot_df,
        geometry=gpd.points_from_xy(plot_df["decimalLongitude"], plot_df["decimalLatitude"]),
        crs=WGS84,
    )


def _find_nwi_packages(nwi_dir: Path, explicit_paths: list[str] | None) -> list[Path]:
    if explicit_paths:
        paths = [Path(path) for path in explicit_paths]
    else:
        paths = sorted(nwi_dir.rglob("*.gpkg"))
    missing = [path for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing NWI GeoPackage(s):\n" + "\n".join(f" - {path}" for path in missing))
    if not paths:
        raise FileNotFoundError(
            f"No NWI GeoPackages found under {nwi_dir}. Put the CO/AZ/CA/ND .gpkg files there "
            "or pass them with --nwi-gpkg."
        )
    return paths


def _expanded_wgs84_bbox(points: "gpd.GeoDataFrame", padding_deg: float) -> tuple[float, float, float, float]:
    minx, miny, maxx, maxy = points.total_bounds
    return (minx - padding_deg, miny - padding_deg, maxx + padding_deg, maxy + padding_deg)


def _read_nwi_polygons(paths: list[Path], plots_wgs84: "gpd.GeoDataFrame", padding_deg: float) -> "gpd.GeoDataFrame":
    gpd = _require_geopandas()
    from shapely.geometry import box

    frames: list[gpd.GeoDataFrame] = []

    for path in paths:
        layer = _choose_wetland_polygon_layer(path)
        package_plots = _plots_inside_package_boundary(path, plots_wgs84)
        if package_plots.empty:
            print(f"Skipping {path.name}: no NEON plots fall inside its boundary layer.")
            continue

        bbox = _expanded_wgs84_bbox(package_plots, padding_deg)
        sample = _read_layer_sample(path, layer)
        if sample.crs is None:
            raise ValueError(f"NWI layer {layer} in {path} has no CRS. Cannot calculate distances safely.")

        layer_bbox = tuple(gpd.GeoSeries([box(*bbox)], crs=WGS84).to_crs(sample.crs).total_bounds)
        try:
            gdf = gpd.read_file(path, layer=layer, bbox=layer_bbox)
        except Exception as e:
            print(f"WARNING bbox read failed for {path}; reading full layer instead. Reason: {e}")
            gdf = gpd.read_file(path, layer=layer)

        if gdf.empty:
            print(f"WARNING no NWI polygons from {path} intersect the expanded plot bounding box.")
            continue
        if gdf.crs is None:
            raise ValueError(f"NWI layer {layer} in {path} has no CRS. Cannot calculate distances safely.")

        gdf = gdf[gdf.geometry.notna()].copy()
        gdf = gdf[gdf.geometry.is_valid].copy()
        gdf = gdf[gdf.geometry.geom_type.str.contains("Polygon", case=False, na=False)].copy()
        if gdf.empty:
            print(f"WARNING no valid polygon geometries remained for {path}.")
            continue

        class_col = _find_column(gdf, ["ATTRIBUTE", "Cowardin_Code", "WETLAND_TYPE", "CLASS1", "NWI_CLASS"])
        system_col = _find_column(gdf, ["SYSTEM", "WETLAND_SYSTEM"])
        keep_cols = ["geometry"]
        if class_col is not None:
            keep_cols.append(class_col)
        if system_col is not None and system_col not in keep_cols:
            keep_cols.append(system_col)

        out = gdf[keep_cols].copy()
        out["source_gpkg"] = str(path)
        out["source_layer"] = layer
        out["nwi_class_raw"] = out[class_col].astype(str).str.strip() if class_col is not None else ""
        out["nwi_system_raw"] = out[system_col].astype(str).str.strip() if system_col is not None else ""
        out = out[["nwi_class_raw", "nwi_system_raw", "source_gpkg", "source_layer", "geometry"]].to_crs(WGS84)
        frames.append(out)
        print(f"Loaded {len(out):,} valid NWI polygons from {path.name}.")

    if not frames:
        raise RuntimeError("No valid NWI wetland polygons were loaded near the NEON plots.")

    combined = pd.concat(frames, ignore_index=True)
    return gpd.GeoDataFrame(combined, geometry="geometry", crs=WGS84)


def _nwi_system(code: Any, explicit_system: Any = "") -> str:
    explicit = str(explicit_system or "").strip()
    if explicit:
        return explicit
    text = str(code or "").strip().upper()
    if text.startswith("P"):
        return "Palustrine"
    if text.startswith("R"):
        return "Riverine"
    if text.startswith("L"):
        return "Lacustrine"
    if text.startswith("E"):
        return "Estuarine"
    if text.startswith("M"):
        return "Marine"
    return ""


def _simplified_group(code: Any) -> str:
    text = str(code or "").strip().upper()
    if text.startswith("PEM"):
        return "Palustrine Emergent"
    if text.startswith("PFO"):
        return "Palustrine Forested"
    if text.startswith("PSS"):
        return "Palustrine Scrub-Shrub"
    if text.startswith("PUB") or text.startswith("PAB"):
        return "Pond / aquatic bed"
    if text.startswith("R"):
        return "Riverine"
    if text.startswith("L"):
        return "Lacustrine"
    return "Mapped wetland"


def _wetland_context(inside: bool, distance_m: float | None) -> str:
    if inside:
        return "Inside wetland"
    if distance_m is None or pd.isna(distance_m):
        return "Not within 10 m"
    if distance_m <= WETLAND_ADJACENT_DISTANCE_M:
        return "Wetland-adjacent"
    return "Not within 10 m"


def _assign_context(plots_wgs84: "gpd.GeoDataFrame", wetlands: "gpd.GeoDataFrame") -> pd.DataFrame:
    gpd = _require_geopandas()
    plots_m = plots_wgs84.to_crs(DISTANCE_CRS)
    wetlands_m = wetlands.to_crs(DISTANCE_CRS)
    wetlands_m = wetlands_m.reset_index(drop=True).copy()
    wetlands_m["wetland_index"] = wetlands_m.index
    wetlands_m["nearest_wetland_area_m2"] = wetlands_m.geometry.area

    joined = gpd.sjoin_nearest(
        plots_m,
        wetlands_m[
            [
                "wetland_index",
                "nwi_class_raw",
                "nwi_system_raw",
                "nearest_wetland_area_m2",
                "geometry",
            ]
        ],
        how="left",
        distance_col="distance_to_nearest_wetland_m",
    )
    joined = joined.sort_values(["siteID", "plotID", "distance_to_nearest_wetland_m"]).drop_duplicates(
        ["siteID", "plotID"], keep="first"
    )

    inside_join = gpd.sjoin(
        plots_m,
        wetlands_m[["wetland_index", "geometry"]],
        how="left",
        predicate="intersects",
    )
    inside_flags = (
        inside_join.assign(_inside=inside_join["wetland_index"].notna())
        .groupby(["siteID", "plotID"], dropna=False)["_inside"]
        .any()
        .rename("inside_bool")
        .reset_index()
    )

    out = pd.DataFrame(joined.drop(columns="geometry"))
    out = out.merge(inside_flags, on=["siteID", "plotID"], how="left")
    out["inside_bool"] = out["inside_bool"].fillna(False)
    out["inside_nwi_wetland"] = out["inside_bool"].map({True: "Yes", False: "No"})
    within_10m = pd.to_numeric(out["distance_to_nearest_wetland_m"], errors="coerce") <= WETLAND_ADJACENT_DISTANCE_M
    out["within_10m_of_nwi_wetland"] = within_10m.fillna(False).map({True: "Yes", False: "No"})
    out["inside_or_within_10m_nwi_wetland"] = (out["inside_bool"] | within_10m.fillna(False)).map(
        {True: "Yes", False: "No"}
    )
    out["nearest_nwi_class"] = out["nwi_class_raw"].replace({"": pd.NA})
    out["nearest_nwi_system"] = [
        _nwi_system(code, system) for code, system in zip(out["nearest_nwi_class"], out["nwi_system_raw"])
    ]
    out["wetland_context"] = [
        _wetland_context(bool(inside), dist)
        for inside, dist in zip(out["inside_bool"], out["distance_to_nearest_wetland_m"])
    ]
    out["wetland_group"] = out["nearest_nwi_class"].map(_simplified_group)
    out.loc[out["wetland_context"].eq("Not within 10 m"), "wetland_group"] = "None"
    out["distance_to_nearest_wetland_m"] = out["distance_to_nearest_wetland_m"].round(2)
    out["nearest_wetland_area_m2"] = out["nearest_wetland_area_m2"].round(2)

    cols = [
        "siteID",
        "plotID",
        "decimalLatitude",
        "decimalLongitude",
        "inside_nwi_wetland",
        "within_10m_of_nwi_wetland",
        "inside_or_within_10m_nwi_wetland",
        "distance_to_nearest_wetland_m",
        "nearest_nwi_class",
        "nearest_nwi_system",
        "wetland_context",
        "nearest_wetland_area_m2",
        "wetland_group",
    ]
    return out[[col for col in cols if col in out.columns]]


def _join_to_horizons(horizon_df: pd.DataFrame, plot_context: pd.DataFrame) -> pd.DataFrame:
    site_col = _require_column(horizon_df, ["siteID", "site_id"], "site ID")
    plot_col = _require_column(horizon_df, ["plotID", "plot_id"], "plot ID")
    context_cols = ["siteID", "plotID"] + CONTEXT_COLUMNS
    context_cols = [col for col in context_cols if col in plot_context.columns]
    return horizon_df.merge(
        plot_context[context_cols],
        left_on=[site_col, plot_col],
        right_on=["siteID", "plotID"],
        how="left",
        suffixes=("", "_wetland"),
    )


def _summary_table(plot_context: pd.DataFrame) -> pd.DataFrame:
    return (
        plot_context.groupby(["siteID", "wetland_context"], dropna=False)
        .size()
        .rename("plot_count")
        .reset_index()
        .sort_values(["siteID", "wetland_context"])
    )


def build_wetland_context(
    soil_xlsx: Path,
    nwi_paths: list[Path],
    out_xlsx: Path,
    debug_dir: Path | None = None,
    bbox_padding_deg: float = 0.25,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    horizon_df = _read_soil_table(soil_xlsx)
    plots_wgs84 = _build_plot_points(horizon_df)
    wetlands = _read_nwi_polygons(nwi_paths, plots_wgs84, bbox_padding_deg)

    print(f"\nWetland source CRS: {_crs_to_string(wetlands.crs)}")
    print(f"Distance CRS: {DISTANCE_CRS}")

    plot_context = _assign_context(plots_wgs84, wetlands)
    horizon_context = _join_to_horizons(horizon_df, plot_context)
    summary = _summary_table(plot_context)

    out_xlsx.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out_xlsx, engine="openpyxl") as writer:
        plot_context.to_excel(writer, sheet_name="Plot_Wetland_Context", index=False)
        horizon_context.to_excel(writer, sheet_name="Horizon_Soil_Wetland_Table", index=False)
        summary.to_excel(writer, sheet_name="Summary", index=False)

    if debug_dir is not None:
        debug_dir.mkdir(parents=True, exist_ok=True)
        plot_context.to_csv(debug_dir / "plot_wetland_context_debug.csv", index=False)
        summary.to_csv(debug_dir / "wetland_context_summary_debug.csv", index=False)

    return plot_context, horizon_context, summary


def _print_final_summary(plot_context: pd.DataFrame) -> None:
    counts = plot_context["wetland_context"].value_counts()
    print("\nFinal wetland context summary")
    print(f"Total plots processed: {len(plot_context)}")
    print(f"Inside wetlands: {int(counts.get('Inside wetland', 0))}")
    print(f"Wetland-adjacent within {WETLAND_ADJACENT_DISTANCE_M:g} m: {int(counts.get('Wetland-adjacent', 0))}")
    print(f"Not within {WETLAND_ADJACENT_DISTANCE_M:g} m: {int(counts.get('Not within 10 m', 0))}")
    print("\nCounts by NEON site:")
    print(pd.crosstab(plot_context["siteID"], plot_context["wetland_context"]).to_string())
    print(
        "\nNote: NWI is used here as a screening dataset for mapped wetland proximity and type; "
        "it is not formal hydric soil confirmation."
    )


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Assign NWI mapped wetland context to NEON soil plots and join it back to horizon-level chemistry."
    )
    ap.add_argument("--soil-xlsx", default=str(DEFAULT_SOIL_XLSX), help="NEON soil master table workbook")
    ap.add_argument("--nwi-dir", default=str(DEFAULT_NWI_DIR), help="Directory containing NWI .gpkg files")
    ap.add_argument(
        "--nwi-gpkg",
        action="append",
        help="Explicit NWI GeoPackage path. Repeat for CO/AZ/CA/ND if not using --nwi-dir.",
    )
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="Output Excel workbook")
    ap.add_argument("--debug-dir", default=None, help="Optional directory for small debug CSV files")
    ap.add_argument(
        "--bbox-padding-deg",
        type=float,
        default=0.25,
        help="WGS84 degree padding around all plots when reading NWI polygons.",
    )
    args = ap.parse_args()

    try:
        nwi_paths = _find_nwi_packages(Path(args.nwi_dir), args.nwi_gpkg)
        debug_dir = Path(args.debug_dir) if args.debug_dir is not None else None
        plot_context, _, _ = build_wetland_context(
            soil_xlsx=Path(args.soil_xlsx),
            nwi_paths=nwi_paths,
            out_xlsx=Path(args.out),
            debug_dir=debug_dir,
            bbox_padding_deg=args.bbox_padding_deg,
        )
    except Exception as e:
        raise SystemExit(f"ERROR: {e}") from e

    print(f"\nSaved workbook: {Path(args.out)}")
    _print_final_summary(plot_context)


if __name__ == "__main__":
    main()
