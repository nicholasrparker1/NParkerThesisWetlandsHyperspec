from pathlib import Path
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

OSBS = (
    ROOT
    / "outputs"
    / "tables"
    / "kssl_neon_linkage"
    / "osbs_validation"
)

INPUT = OSBS / "osbs_frozen_validation_samples.csv"
OUT = OSBS / "osbs_frozen_texture_matches.csv"

TEXTURE_VARS = [
    "clay_pct",
    "sand_pct",
    "silt_pct",
]


def main():

    df = pd.read_csv(INPUT, low_memory=False)

    for col in TEXTURE_VARS:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )

    hydric = df[
        df["validation_group"]
        .eq("HYDRIC_VALIDATION")
    ].copy()

    nonhydric = df[
        df["validation_group"]
        .eq("NONHYDRIC_VALIDATION")
    ].copy()

    print("OSBS frozen exact-sample texture matching")
    print("=" * 76)
    print(f"Hydric samples: {len(hydric)}")
    print(f"Nonhydric samples: {len(nonhydric)}")

    # Standardize texture across the entire frozen cohort.
    means = df[TEXTURE_VARS].mean()
    stds = (
        df[TEXTURE_VARS]
        .std(ddof=0)
        .replace(0, np.nan)
    )

    for col in TEXTURE_VARS:
        df[f"z_{col}"] = (
            df[col] - means[col]
        ) / stds[col]

    hydric = df[
        df["validation_group"]
        .eq("HYDRIC_VALIDATION")
    ].copy()

    nonhydric = df[
        df["validation_group"]
        .eq("NONHYDRIC_VALIDATION")
    ].copy()

    rows = []

    for _, h in hydric.iterrows():

        candidates = nonhydric.copy()

        d2 = np.zeros(len(candidates))

        for col in TEXTURE_VARS:
            d2 += (
                candidates[f"z_{col}"]
                - h[f"z_{col}"]
            ) ** 2

        candidates[
            "sample_texture_distance"
        ] = np.sqrt(d2)

        best = (
            candidates
            .sort_values(
                "sample_texture_distance"
            )
            .iloc[0]
        )

        rows.append(
            {
                "hydric_pedon":
                    h["user_pedon_id"],

                "hydric_smp_id":
                    int(h["smp_id"]),

                "hydric_horizon":
                    h["horizon_designation"],

                "hydric_top_depth_cm":
                    h["top_depth_cm"],

                "hydric_bottom_depth_cm":
                    h["bottom_depth_cm"],

                "nonhydric_pedon":
                    best["user_pedon_id"],

                "nonhydric_smp_id":
                    int(best["smp_id"]),

                "nonhydric_horizon":
                    best["horizon_designation"],

                "nonhydric_top_depth_cm":
                    best["top_depth_cm"],

                "nonhydric_bottom_depth_cm":
                    best["bottom_depth_cm"],

                "sample_texture_distance":
                    best[
                        "sample_texture_distance"
                    ],

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

    matches = (
        pd.DataFrame(rows)
        .sort_values(
            "sample_texture_distance"
        )
    )

    matches.to_csv(
        OUT,
        index=False,
    )

    print("\nFrozen OSBS texture pairs:")
    print(
        matches.to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}",
        )
    )

    print("\nDistance summary:")
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
        ].to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}",
        )
    )

    print("\nWrote:")
    print(OUT)

    print(
        "\nOSBS TEXTURE PAIRS ARE NOW FROZEN."
    )
    print(
        "No MIR spectral values were inspected."
    )


if __name__ == "__main__":
    main()