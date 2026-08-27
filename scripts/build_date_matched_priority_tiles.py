from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

import pandas as pd


SOIL_XLSX = Path("data/field/NEON_Master_Soil_Table.xlsx")
PRIORITY_CSV = Path("data/processed/neon_aop_priority_download_list.csv")
OUT_CSV = Path("data/processed/neon_aop_priority_date_matched_download_list.csv")

SITE_AVAILABLE = {
    "CPER": {
        "DP3.30006.001": ["2013-06", "2017-05", "2020-06", "2020-09", "2021-06"],
        "DP3.30006.002": ["2024-06"],
    },
    "DCFS": {
        "DP3.30006.001": ["2016-06", "2017-06", "2019-07", "2020-06", "2021-06"],
        "DP3.30006.002": ["2019-07", "2023-06", "2025-06"],
    },
    "NOGP": {
        "DP3.30006.001": ["2016-07", "2017-06", "2019-07", "2020-06", "2021-06"],
        "DP3.30006.002": ["2023-06", "2025-06"],
    },
    "SJER": {
        "DP3.30006.001": ["2013-06", "2017-03", "2018-03", "2019-03", "2021-03"],
        "DP3.30006.002": ["2023-04", "2024-04", "2026-04"],
    },
    "SRER": {
        "DP3.30006.001": ["2017-08", "2018-08", "2019-09", "2021-09"],
        "DP3.30006.002": ["2022-08", "2024-09", "2025-09"],
    },
    "WOOD": {
        "DP3.30006.001": ["2016-06", "2017-06", "2019-07", "2020-06", "2021-06"],
        "DP3.30006.002": ["2019-07", "2023-06", "2025-06"],
    },
}


def _month_midpoint(month: str) -> pd.Timestamp:
    return pd.Timestamp(f"{month}-15")


def _closest_product_month(site: str, collect_date: pd.Timestamp) -> tuple[str, str, int]:
    candidates = []
    for product, months in SITE_AVAILABLE[site].items():
        for month in months:
            delta = abs((_month_midpoint(month) - collect_date).days)
            candidates.append((delta, product, month))
    delta, product, month = sorted(candidates)[0]
    return product, month, int(delta)


def _fetch_h5_files(product: str, site: str, month: str) -> dict[str, dict[str, object]]:
    url = f"https://data.neonscience.org/api/v0/data/{product}/{site}/{month}"
    command = (
        "$d = Invoke-RestMethod -Uri '"
        + url
        + "'; $d.data.files | Where-Object { $_.name -like '*reflectance.h5' } "
        + "| Select-Object name,url,size | ConvertTo-Json -Depth 3"
    )
    done = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        check=True,
        capture_output=True,
        text=True,
    )
    text = done.stdout.strip()
    if not text:
        return {}
    parsed = json.loads(text)
    if isinstance(parsed, dict):
        parsed = [parsed]
    return {row["name"]: row for row in parsed}


def _date_range_text(dates: pd.Series) -> str:
    dates = pd.to_datetime(dates, errors="coerce").dropna()
    if dates.empty:
        return ""
    if dates.min() == dates.max():
        return dates.min().date().isoformat()
    return f"{dates.min().date().isoformat()} to {dates.max().date().isoformat()}"


def main() -> None:
    soil = pd.read_excel(SOIL_XLSX)
    soil["collectDate"] = pd.to_datetime(soil["collectDate"], errors="coerce")
    priority = pd.read_csv(PRIORITY_CSV)

    file_cache: dict[tuple[str, str, str], dict[str, dict[str, object]]] = {}
    rows = []
    for tile in priority.itertuples(index=False):
        plot_ids = str(tile.plot_ids_covered).split(",")
        plot_dates = soil[soil["plotID"].astype(str).isin(plot_ids)]["collectDate"]
        reference_date = plot_dates.dropna().median()
        product, month, date_delta_days = _closest_product_month(str(tile.siteID), reference_date)

        suffix = "_bidirectional_reflectance.h5" if product.endswith(".002") else "_reflectance.h5"
        tile_name = str(tile.tile_name).replace("_bidirectional_reflectance.h5", suffix)
        cache_key = (product, str(tile.siteID), month)
        if cache_key not in file_cache:
            file_cache[cache_key] = _fetch_h5_files(*cache_key)
        found = file_cache[cache_key].get(tile_name)

        rows.append(
            {
                "siteID": tile.siteID,
                "aop_site": tile.aop_site,
                "soil_collect_date_range": _date_range_text(plot_dates),
                "recommended_product": product,
                "recommended_timeframe": month,
                "days_between_soil_and_aop_midmonth": date_delta_days,
                "tile_name": tile_name,
                "plot_ids_covered": tile.plot_ids_covered,
                "number_of_plots": tile.number_of_plots,
                "file_available": found is not None,
                "size_mb": round(float(found["size"]) / (1024**2), 1) if found is not None and found.get("size") else "",
                "url": found["url"] if found is not None else "",
            }
        )

    out = pd.DataFrame(rows)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False)
    print(f"Saved: {OUT_CSV}")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
