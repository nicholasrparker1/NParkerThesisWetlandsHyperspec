from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data" / "processed" / "kssl_layer_analysis_table.csv"
OUTPUT = ROOT / "outputs" / "tables" / "kssl_regional_expansion"
STATES = ["Montana", "North Dakota", "South Dakota", "Nebraska"]


def main() -> None:
    data = pd.read_csv(INPUT, low_memory=False)
    cohort = data.loc[
        data["state"].isin(STATES)
        & data["surface_or_near_surface"].eq(True)
        & data["qc_flag_count"].fillna(0).eq(0)
        & data[["latitude", "longitude"]].notna().all(axis=1)
        & data["mir_master_count"].fillna(0).gt(0)
    ].copy()

    # One independent shallowest layer per pedon. Stable IDs break exact ties.
    cohort = cohort.sort_values(
        ["pedon_key", "top_depth_cm", "bottom_depth_cm", "lay_id", "smp_id"],
        na_position="last",
    )
    cohort = cohort.drop_duplicates("pedon_key", keep="first")
    cohort["regional_cohort_rule"] = (
        "one shallowest quality-screened surface layer per geolocated pedon with MIR record"
    )

    OUTPUT.mkdir(parents=True, exist_ok=True)
    out = OUTPUT / "nd_mt_sd_ne_surface_mir_cohort.csv"
    cohort.to_csv(out, index=False)
    summary = (
        cohort.groupby("state")
        .agg(samples=("smp_id", "nunique"), pedons=("pedon_key", "nunique"), projects=("lab_proj_name", "nunique"))
        .reset_index()
    )
    summary.to_csv(OUTPUT / "nd_mt_sd_ne_surface_mir_cohort_summary.csv", index=False)
    print(summary.to_string(index=False))
    print(f"Total independent pedons: {cohort.pedon_key.nunique()}")
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
