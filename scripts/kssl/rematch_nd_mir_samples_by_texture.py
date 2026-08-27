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
OUT = ND / "nd_mir_sample_level_texture_matches.csv"


TEXTURE_VARS = [
    "clay_pct",
    "sand_pct",
    "silt_pct",
]


def main():

    df = pd.read_csv(
        META,
        low_memory=False,
    )

    for col in TEXTURE_VARS:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )

    hydric = df[
        df["reference_group"]
        .eq("HYDRIC_REFERENCE")
    ].copy()

    nonhydric = df[
        df["reference_group"]
        .eq("NONHYDRIC_REFERENCE")
    ].copy()

    print("MIR sample-level texture rematching")
    print("=" * 76)

    print(f"Hydric MIR samples: {len(hydric)}")
    print(f"Nonhydric MIR samples: {len(nonhydric)}")

    # ---------------------------------------------------------
    # Standardize using the actual 21 MIR samples.
    # ---------------------------------------------------------

    tex = df[TEXTURE_VARS].copy()

    means = tex.mean()
    stds = tex.std(ddof=0).replace(0, np.nan)

    for col in TEXTURE_VARS:
        df[f"z_{col}"] = (
            df[col] - means[col]
        ) / stds[col]

    hydric = df[
        df["reference_group"]
        .eq("HYDRIC_REFERENCE")
    ].copy()

    nonhydric = df[
        df["reference_group"]
        .eq("NONHYDRIC_REFERENCE")
    ].copy()

    rows = []

    for _, h in hydric.iterrows():

        candidates = nonhydric.copy()

        distance_sq = np.zeros(
            len(candidates),
            dtype=float,
        )

        valid_dims = np.zeros(
            len(candidates),
            dtype=int,
        )

        for col in TEXTURE_VARS:

            hz = h[f"z_{col}"]

            nz = pd.to_numeric(
                candidates[f"z_{col}"],
                errors="coerce",
            )

            valid = (
                nz.notna()
                & pd.notna(hz)
            )

            distance_sq += np.where(
                valid,
                (nz - hz) ** 2,
                0,
            )

            valid_dims += valid.astype(int)

        candidates[
            "sample_texture_distance"
        ] = np.where(
            valid_dims > 0,
            np.sqrt(distance_sq),
            np.nan,
        )

        candidates = candidates.sort_values(
            "sample_texture_distance"
        )

        best = candidates.iloc[0]

        rows.append(
            {
                "hydric_pedon":
                    h["user_pedon_id"],

                "hydric_smp_id":
                    int(h["smp_id"]),

                "nonhydric_pedon":
                    best["user_pedon_id"],

                "nonhydric_smp_id":
                    int(best["smp_id"]),

                "sample_texture_distance":
                    best[
                        "sample_texture_distance"
                    ],

                "hydric_horizon":
                    h["horizon_designation"],

                "nonhydric_horizon":
                    best["horizon_designation"],

                "hydric_clay_pct":
                    h["clay_pct"],

                "nonhydric_clay_pct":
                    best["clay_pct"],

                "delta_clay_pct":
                    h["clay_pct"]
                    - best["clay_pct"],

                "hydric_sand_pct":
                    h["sand_pct"],

                "nonhydric_sand_pct":
                    best["sand_pct"],

                "delta_sand_pct":
                    h["sand_pct"]
                    - best["sand_pct"],

                "hydric_silt_pct":
                    h["silt_pct"],

                "nonhydric_silt_pct":
                    best["silt_pct"],

                "delta_silt_pct":
                    h["silt_pct"]
                    - best["silt_pct"],
            }
        )

    matches = pd.DataFrame(rows)

    matches.to_csv(
        OUT,
        index=False,
    )

    print("\nNew MIR-sample texture matches:")
    print(
        matches.to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}",
        )
    )

    print("\nDistance ranking:")
    print(
        matches[
            [
                "hydric_pedon",
                "nonhydric_pedon",
                "sample_texture_distance",
                "delta_clay_pct",
                "delta_sand_pct",
                "delta_silt_pct",
            ]
        ]
        .sort_values(
            "sample_texture_distance"
        )
        .to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}",
        )
    )

    print("\nWrote:")
    print(OUT)


if __name__ == "__main__":
    main()