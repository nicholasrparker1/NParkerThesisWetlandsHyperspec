from pathlib import Path
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

BASE = (
    ROOT
    / "outputs"
    / "tables"
    / "kssl_neon_linkage"
)

OSBS = BASE / "osbs_validation"

HORIZONS = OSBS / "osbs_reference_horizons.csv"
OUT = OSBS / "osbs_frozen_validation_samples.csv"


def main():

    h = pd.read_csv(HORIZONS, low_memory=False)

    for c in [
        "top_depth_cm",
        "bottom_depth_cm",
        "clay_pct",
        "sand_pct",
        "silt_pct",
        "mir_master_count",
        "mir_scan_count",
    ]:
        if c in h.columns:
            h[c] = pd.to_numeric(h[c], errors="coerce")

    # Mineral horizon: exclude O horizons.
    mineral = h[
        ~h["horizon_designation"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.startswith("O")
    ].copy()

    # Require:
    # 1. MIR availability
    # 2. measured texture for the exact analyzed sample
    usable = mineral[
        (mineral["mir_master_count"] > 0)
        & mineral["clay_pct"].notna()
        & mineral["sand_pct"].notna()
        & mineral["silt_pct"].notna()
    ].copy()

    # Select the shallowest usable mineral horizon independently
    # for every reference pedon.
    usable = usable.sort_values(
        [
            "user_pedon_id",
            "top_depth_cm",
            "bottom_depth_cm",
            "smp_id",
        ]
    )

    frozen = usable.drop_duplicates(
        "user_pedon_id",
        keep="first",
    ).copy()

    frozen = frozen.sort_values(
        [
            "validation_group",
            "user_pedon_id",
        ]
    )

    print("OSBS frozen independent validation samples")
    print("=" * 78)

    print("\nCounts:")
    print(
        frozen["validation_group"]
        .value_counts()
        .to_string()
    )

    cols = [
        "user_pedon_id",
        "validation_group",
        "smp_id",
        "horizon_designation",
        "top_depth_cm",
        "bottom_depth_cm",
        "clay_pct",
        "sand_pct",
        "silt_pct",
        "mir_master_count",
        "mir_scan_count",
    ]

    print("\nFrozen samples:")
    print(
        frozen[cols]
        .to_string(index=False)
    )

    # Check every reference pedon survived.
    expected = (
        h[
            [
                "user_pedon_id",
                "validation_group",
            ]
        ]
        .drop_duplicates()
    )

    missing = expected[
        ~expected["user_pedon_id"].isin(
            frozen["user_pedon_id"]
        )
    ]

    print("\nReference pedons without usable frozen sample:")
    if missing.empty:
        print("NONE")
    else:
        print(missing.to_string(index=False))

    frozen.to_csv(OUT, index=False)

    print("\nWrote:")
    print(OUT)

    print(
        "\nVALIDATION COHORT IS NOW FROZEN."
    )
    print(
        "No MIR spectral values were inspected in sample selection."
    )


if __name__ == "__main__":
    main()