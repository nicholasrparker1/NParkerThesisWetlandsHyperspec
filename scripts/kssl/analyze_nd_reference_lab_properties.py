from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "outputs" / "tables" / "kssl_neon_linkage"
ND = BASE / "north_dakota_pilot"

MASTER = ND / "nd_master.csv"
AUDIT = ND / "nd_hydric_morphology_audit.csv"

OUT_HORIZONS = ND / "nd_reference_lab_horizons.csv"
OUT_PEDONS = ND / "nd_reference_lab_pedon_summary.csv"
OUT_COMPARE = ND / "nd_reference_lab_property_comparison.csv"


LAB_VARS = [
    "estimated_organic_carbon_pct",
    "total_carbon_pct",
    "total_nitrogen_pct",
    "total_sulfur_pct",
    "fe_dithionite_pct",
    "fe_oxalate_pct",
    "al_dithionite_pct",
    "al_oxalate_pct",
    "clay_pct",
    "sand_pct",
    "silt_pct",
    "ph_water",
    "ph_cacl2",
    "carbonate_pct",
    "cec_nh4oac_cmol_kg",
    "bulk_density_ovendry_g_cm3",
    "bulk_density_third_bar_g_cm3",
    "water_retention_15bar_pct",
    "water_retention_third_bar_pct",
]


def median_or_nan(x):
    x = pd.to_numeric(x, errors="coerce")
    return x.median() if x.notna().any() else np.nan


def main():

    master = pd.read_csv(MASTER, low_memory=False)
    audit = pd.read_csv(AUDIT, low_memory=False)

    # ---------------------------------------------------------
    # Define reference groups WITHOUT using KSSL lab chemistry.
    # ---------------------------------------------------------

    positive = audit[
        (audit["match_confidence"] == "EXACT")
        & (audit["selected_hydricrating"] == "Yes")
        & (audit["aquic_taxonomy"] == True)
        & audit["selected_drainagecl"].isin(
            ["Poorly drained", "Very poorly drained"]
        )
    ].copy()

    negative = audit[
        (audit["match_confidence"] == "EXACT")
        & (audit["selected_hydricrating"] == "No")
        & (audit["aquic_taxonomy"] == False)
        & audit["selected_drainagecl"].isin(
            [
                "Moderately well drained",
                "Well drained",
                "Somewhat excessively drained",
                "Excessively drained",
            ]
        )
    ].copy()

    print("Reference cohort")
    print("=" * 70)
    print(f"Positive pedons: {len(positive)}")
    print(f"Negative pedons: {len(negative)}")

    print("\nPositive IDs:")
    print(positive["user_pedon_id"].to_string(index=False))

    print("\nNegative IDs:")
    print(negative["user_pedon_id"].to_string(index=False))

    group_map = {
        **dict.fromkeys(positive["user_pedon_id"], "HYDRIC_REFERENCE"),
        **dict.fromkeys(negative["user_pedon_id"], "NONHYDRIC_REFERENCE"),
    }

    ref = master[
        master["user_pedon_id"].isin(group_map)
    ].copy()

    ref["reference_group"] = ref["user_pedon_id"].map(group_map)

    # Restrict the first comparison to the upper 30 cm.
    # This keeps the experiment relevant to near-surface sensing
    # and avoids allowing deep horizons to dominate pedon summaries.
    ref["top_depth_cm"] = pd.to_numeric(
        ref["top_depth_cm"], errors="coerce"
    )
    ref["bottom_depth_cm"] = pd.to_numeric(
        ref["bottom_depth_cm"], errors="coerce"
    )

    upper = ref[ref["top_depth_cm"] < 30].copy()

    # Keep only actual observed overlap with 0–30 cm.
    upper["overlap_0_30_cm"] = (
        np.minimum(upper["bottom_depth_cm"], 30)
        - np.maximum(upper["top_depth_cm"], 0)
    ).clip(lower=0)

    upper = upper[upper["overlap_0_30_cm"] > 0].copy()

    upper.to_csv(OUT_HORIZONS, index=False)

    # ---------------------------------------------------------
    # Pedon-level median laboratory properties.
    # Each pedon is one independent observational unit.
    # ---------------------------------------------------------

    available_vars = [
        v for v in LAB_VARS if v in upper.columns
    ]

    pedon_rows = []

    for (pid, group), g in upper.groupby(
        ["user_pedon_id", "reference_group"]
    ):
        row = {
            "user_pedon_id": pid,
            "reference_group": group,
            "n_upper30_horizons": len(g),
        }

        for var in available_vars:
            row[var] = median_or_nan(g[var])

        pedon_rows.append(row)

    pedons = pd.DataFrame(pedon_rows)
    pedons.to_csv(OUT_PEDONS, index=False)

    # ---------------------------------------------------------
    # Descriptive comparison only.
    # No classifier and no significance fishing yet.
    # ---------------------------------------------------------

    rows = []

    for var in available_vars:

        h = pd.to_numeric(
            pedons.loc[
                pedons["reference_group"] == "HYDRIC_REFERENCE",
                var,
            ],
            errors="coerce",
        ).dropna()

        n = pd.to_numeric(
            pedons.loc[
                pedons["reference_group"] == "NONHYDRIC_REFERENCE",
                var,
            ],
            errors="coerce",
        ).dropna()

        h_med = h.median() if len(h) else np.nan
        n_med = n.median() if len(n) else np.nan

        rows.append(
            {
                "property": var,
                "n_hydric": len(h),
                "n_nonhydric": len(n),
                "hydric_median": h_med,
                "nonhydric_median": n_med,
                "median_difference_hydric_minus_nonhydric":
                    h_med - n_med
                    if pd.notna(h_med) and pd.notna(n_med)
                    else np.nan,
                "hydric_min": h.min() if len(h) else np.nan,
                "hydric_max": h.max() if len(h) else np.nan,
                "nonhydric_min": n.min() if len(n) else np.nan,
                "nonhydric_max": n.max() if len(n) else np.nan,
            }
        )

    compare = pd.DataFrame(rows)

    compare["absolute_median_difference"] = (
        compare[
            "median_difference_hydric_minus_nonhydric"
        ].abs()
    )

    compare = compare.sort_values(
        "absolute_median_difference",
        ascending=False,
        na_position="last",
    )

    compare.to_csv(OUT_COMPARE, index=False)

    print("\nUpper-30-cm horizons:")
    print(
        upper.groupby("reference_group")
        .size()
        .to_string()
    )

    print("\nPedon-level laboratory comparison:")
    print(
        compare[
            [
                "property",
                "n_hydric",
                "n_nonhydric",
                "hydric_median",
                "nonhydric_median",
                "median_difference_hydric_minus_nonhydric",
            ]
        ].to_string(index=False)
    )

    print("\nWrote:")
    print(OUT_HORIZONS)
    print(OUT_PEDONS)
    print(OUT_COMPARE)


if __name__ == "__main__":
    main()
