from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import pandas as pd
from pyproj import Transformer


WETLAND_COVER_XLSX = Path("data/processed/NEON_Soil_Wetland_Cover_Classification.xlsx")
OUT_CSV = Path("data/processed/neon_aop_required_tile_manifest.csv")
PLOT_SHEET = "Plot_Wetland_Cover"
PRODUCT = "DP3.30006.002"
SITE_MONTHS = {
    "CPER": "2024-06",
    "DCFS": "2025-06",
    "NOGP": "2025-06",
    "SJER": "2026-04",
    "SRER": "2025-09",
    "WOOD": "2025-06",
}
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


def _fetch_site_files(site: str, month: str) -> dict[str, str]:
    url = f"https://data.neonscience.org/api/v0/data/{PRODUCT}/{site}/{month}"
    ps = (
        "$d = Invoke-RestMethod -Uri '"
        + url
        + "'; $d.data.files | Where-Object { $_.name -like '*reflectance.h5' } "
        + "| Select-Object name,url | ConvertTo-Json -Depth 3"
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        check=True,
        capture_output=True,
        text=True,
    )
    text = completed.stdout.strip()
    if not text:
        return {}
    parsed = json.loads(text)
    if isinstance(parsed, dict):
        parsed = [parsed]
    return {row["name"]: row["url"] for row in parsed}


def _tile_for_plot(site: str, lat: float, lon: float) -> tuple[int, int]:
    zone = SITE_UTM_ZONES[site]
    transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{32600 + zone}", always_xy=True)
    easting, northing = transformer.transform(lon, lat)
    return math.floor(easting / 1000) * 1000, math.floor(northing / 1000) * 1000


def main() -> None:
    plots = pd.read_excel(WETLAND_COVER_XLSX, sheet_name=PLOT_SHEET)
    rows = []
    for plot in plots.itertuples(index=False):
        site = str(plot.siteID)
        aop_site = SITE_AOP_CODES[site]
        easting, northing = _tile_for_plot(site, float(plot.decimalLatitude), float(plot.decimalLongitude))
        name = f"NEON_{SITE_DOMAINS[site]}_{aop_site}_DP3_{easting}_{northing}_bidirectional_reflectance.h5"
        rows.append(
            {
                "siteID": site,
                "aop_site": aop_site,
                "plotID": str(plot.plotID),
                "month": SITE_MONTHS[site],
                "domain": SITE_DOMAINS[site],
                "tile_easting": easting,
                "tile_northing": northing,
                "tile_name": name,
                "already_classified": str(plot.cover_class) != "not_classified",
            }
        )

    manifest = pd.DataFrame(rows)
    grouped = (
        manifest.groupby(
            ["siteID", "aop_site", "month", "domain", "tile_easting", "tile_northing", "tile_name"],
            as_index=False,
        )
        .agg(
            plots=("plotID", lambda values: ",".join(values)),
            plot_count=("plotID", "size"),
            already_classified_any=("already_classified", "any"),
        )
        .sort_values(["siteID", "tile_easting", "tile_northing"])
    )

    urls = {}
    for site, month in SITE_MONTHS.items():
        urls.update(_fetch_site_files(site, month))

    grouped["url"] = grouped["tile_name"].map(urls)
    grouped["available_in_selected_month"] = grouped["url"].notna()

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    grouped.to_csv(OUT_CSV, index=False)
    print(f"Saved: {OUT_CSV}")
    print(f"Required unique tiles: {len(grouped)}")
    print(f"Available in selected months: {int(grouped['available_in_selected_month'].sum())}")
    print(f"Missing from selected months: {int((~grouped['available_in_selected_month']).sum())}")
    print(grouped.to_string(index=False))


if __name__ == "__main__":
    main()
