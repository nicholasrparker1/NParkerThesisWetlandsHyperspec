from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

ND = (
    ROOT
    / "outputs"
    / "tables"
    / "kssl_neon_linkage"
    / "north_dakota_pilot"
)

META = ND / "nd_mineral_reference_mir_samples.csv"
PAIRS = ND / "nd_texture_nearest_neighbors.csv"

OUT = ND / "nd_best3_texture_matched_chemistry.csv"


PROPERTIES = [
    "estimated_organic_carbon_pct",
    "total_carbon_pct",
    "total_nitrogen_pct",
    "total_sulfur_pct",
    "fe_dithionite_pct",
    "fe_oxalate_pct",
    "al_dithionite_pct",
    "al_oxalate_pct",
    "cec_nh4oac_cmol_kg",
    "water_retention_15bar_pct",
    "ph_water",
    "ph_cacl2",
    "clay_pct",
    "silt_pct",
    "sand_pct",
]


def main():

    meta = pd.read_csv(META, low_memory=False)
    pairs = pd.read_csv(PAIRS)

    # Use only the three closest texture matches.
    best3 = (
        pairs
        .sort_values("texture_distance")
        .head(3)
        .copy()
    )

    lookup = (
        meta
        .set_index("user_pedon_id")
    )

    rows = []

    print("Best-3 texture-matched paired chemistry")
    print("=" * 78)

    print("\nPairs:")
    print(
        best3[
            [
                "hydric_pedon",
                "nonhydric_match",
                "texture_distance",
            ]
        ].to_string(index=False)
    )

    for prop in PROPERTIES:

        pair_deltas = []

        for _, pair in best3.iterrows():

            hpid = str(pair["hydric_pedon"])
            npid = str(pair["nonhydric_match"])

            if prop not in meta.columns:
                continue

            h = pd.to_numeric(
                pd.Series([lookup.loc[hpid, prop]]),
                errors="coerce",
            ).iloc[0]

            n = pd.to_numeric(
                pd.Series([lookup.loc[npid, prop]]),
                errors="coerce",
            ).iloc[0]

            if pd.isna(h) or pd.isna(n):
                delta = np.nan
            else:
                delta = h - n

            pair_deltas.append(
                {
                    "property": prop,
                    "hydric_pedon": hpid,
                    "nonhydric_pedon": npid,
                    "hydric_value": h,
                    "nonhydric_value": n,
                    "delta_hydric_minus_nonhydric": delta,
                }
            )

        valid = [
            x["delta_hydric_minus_nonhydric"]
            for x in pair_deltas
            if np.isfinite(
                x["delta_hydric_minus_nonhydric"]
            )
        ]

        if valid:
            positive = sum(x > 0 for x in valid)
            negative = sum(x < 0 for x in valid)

            print(f"\n{prop}")
            print("-" * 78)

            for x in pair_deltas:
                print(
                    f"{x['hydric_pedon']} vs "
                    f"{x['nonhydric_pedon']}: "
                    f"{x['hydric_value']:.4f} vs "
                    f"{x['nonhydric_value']:.4f} "
                    f"(delta={x['delta_hydric_minus_nonhydric']:.4f})"
                )

            print(
                f"Direction: hydric higher {positive}/{len(valid)}, "
                f"hydric lower {negative}/{len(valid)}"
            )

            print(
                "Median paired delta:",
                f"{np.nanmedian(valid):.4f}",
            )

        rows.extend(pair_deltas)

    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False)

    print("\n" + "=" * 78)
    print("CONSISTENT PROPERTIES")
    print("=" * 78)

    summary = (
        out.dropna(
            subset=["delta_hydric_minus_nonhydric"]
        )
        .groupby("property")
        ["delta_hydric_minus_nonhydric"]
        .agg(
            n="count",
            median_delta="median",
            min_delta="min",
            max_delta="max",
        )
        .reset_index()
    )

    summary["all_hydric_higher"] = (
        summary["min_delta"] > 0
    )

    summary["all_hydric_lower"] = (
        summary["max_delta"] < 0
    )

    consistent = summary[
        summary["all_hydric_higher"]
        | summary["all_hydric_lower"]
    ].copy()

    print(
        consistent.to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}",
        )
    )

    print("\nWrote:")
    print(OUT)


if __name__ == "__main__":
    main()