from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data" / "processed" / "kssl_layer_analysis_table.csv"
OUTPUT = ROOT / "outputs" / "tables" / "kssl_regional_expansion"

STATES = [
    "Montana",
    "North Dakota",
    "South Dakota",
    "Nebraska",
    "Wyoming",
    "Colorado",
    "Kansas",
    "Oklahoma",
    "Minnesota",
    "Iowa",
]


def main() -> None:
    data = pd.read_csv(INPUT, low_memory=False)
    surface = data.loc[
        data["surface_or_near_surface"].eq(True)
        & data["qc_flag_count"].fillna(0).eq(0)
        & data["state"].isin(STATES)
    ].copy()

    surface["has_coordinates"] = surface[["latitude", "longitude"]].notna().all(axis=1)
    surface["has_mir"] = surface["mir_master_count"].fillna(0).gt(0)
    surface["gis_mir_ready"] = surface["has_coordinates"] & surface["has_mir"]

    summary = (
        surface.groupby("state", dropna=False)
        .agg(
            quality_screened_surface_layers=("lay_id", "nunique"),
            unique_pedons=("pedon_key", "nunique"),
            layers_with_coordinates=("has_coordinates", "sum"),
            layers_with_mir=("has_mir", "sum"),
            gis_mir_ready_layers=("gis_mir_ready", "sum"),
            kssl_projects=("lab_proj_name", "nunique"),
        )
        .reset_index()
        .sort_values(["gis_mir_ready_layers", "unique_pedons"], ascending=False)
    )

    OUTPUT.mkdir(parents=True, exist_ok=True)
    out = OUTPUT / "great_plains_surface_coverage.csv"
    summary.to_csv(out, index=False)
    print(summary.to_string(index=False))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
