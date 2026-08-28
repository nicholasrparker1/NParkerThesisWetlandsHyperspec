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

MATRIX = ND / "nd_mineral_reference_mir_matrix.npz"
PAIRS = ND / "nd_texture_nearest_neighbors.csv"

OUT_PAIR_SUMMARY = ND / "nd_texture_matched_mir_pair_summary.csv"
OUT_SPECTRA = ND / "nd_texture_matched_mir_spectral_differences.csv"
OUT_FEATURES = ND / "nd_texture_matched_mir_robust_features.csv"


def snv(X):
    means = np.nanmean(X, axis=1, keepdims=True)
    sds = np.nanstd(X, axis=1, ddof=1, keepdims=True)

    return np.divide(
        X - means,
        sds,
        out=np.full_like(X, np.nan),
        where=sds > 0,
    )


def main():

    d = np.load(MATRIX, allow_pickle=True)

    X = np.asarray(d["absorbance"], dtype=float)
    wn = np.asarray(d["wavenumber_cm1"], dtype=float)

    pedons = np.asarray(
        d["user_pedon_id"]
    ).astype(str)

    Xsnv = snv(X)

    lookup = {
        pid: i
        for i, pid in enumerate(pedons)
    }

    pairs = pd.read_csv(PAIRS)

    print("North Dakota texture-matched MIR analysis")
    print("=" * 76)

    print("\nPre-selected texture pairs:")
    print(
        pairs[
            [
                "hydric_pedon",
                "nonhydric_match",
                "texture_distance",
                "hydric_clay_pct",
                "nonhydric_clay_pct",
                "hydric_sand_pct",
                "nonhydric_sand_pct",
            ]
        ].to_string(index=False)
    )

    pair_differences = []
    summary_rows = []

    for _, row in pairs.iterrows():

        hpid = str(row["hydric_pedon"])
        npid = str(row["nonhydric_match"])

        if hpid not in lookup:
            raise ValueError(
                f"Hydric pedon missing from MIR matrix: {hpid}"
            )

        if npid not in lookup:
            raise ValueError(
                f"Nonhydric pedon missing from MIR matrix: {npid}"
            )

        h = Xsnv[lookup[hpid]]
        n = Xsnv[lookup[npid]]

        delta = h - n

        pair_differences.append(delta)

        rms = np.sqrt(
            np.nanmean(delta ** 2)
        )

        summary_rows.append(
            {
                "hydric_pedon": hpid,
                "nonhydric_pedon": npid,
                "texture_distance":
                    row["texture_distance"],
                "spectral_rms_difference_snv":
                    rms,
            }
        )

    D = np.vstack(pair_differences)

    mean_delta = np.nanmean(D, axis=0)
    median_delta = np.nanmedian(D, axis=0)

    positive_count = np.sum(D > 0, axis=0)
    negative_count = np.sum(D < 0, axis=0)

    same_direction_all_5 = (
        (positive_count == len(D))
        | (negative_count == len(D))
    )

    majority_direction_4_of_5 = (
        (positive_count >= 4)
        | (negative_count >= 4)
    )

    spectral = pd.DataFrame(
        {
            "wavenumber_cm1": wn,
            "mean_pair_delta_hydric_minus_nonhydric":
                mean_delta,
            "median_pair_delta_hydric_minus_nonhydric":
                median_delta,
            "pairs_hydric_higher": positive_count,
            "pairs_hydric_lower": negative_count,
            "same_direction_all_5":
                same_direction_all_5,
            "same_direction_at_least_4_of_5":
                majority_direction_4_of_5,
        }
    )

    # Rank regions primarily by consistency,
    # secondarily by median paired difference.
    candidates = spectral[
        spectral["same_direction_at_least_4_of_5"]
    ].copy()

    candidates["abs_median_delta"] = (
        candidates[
            "median_pair_delta_hydric_minus_nonhydric"
        ].abs()
    )

    candidates = candidates.sort_values(
        [
            "same_direction_all_5",
            "abs_median_delta",
        ],
        ascending=[False, False],
    )

    selected = []

    for _, row in candidates.iterrows():

        w = row["wavenumber_cm1"]

        if all(
            abs(w - x["wavenumber_cm1"]) >= 20
            for x in selected
        ):
            selected.append(row.to_dict())

        if len(selected) == 20:
            break

    features = pd.DataFrame(selected)
    pair_summary = pd.DataFrame(summary_rows)

    pair_summary.to_csv(
        OUT_PAIR_SUMMARY,
        index=False,
    )

    spectral.to_csv(
        OUT_SPECTRA,
        index=False,
    )

    features.to_csv(
        OUT_FEATURES,
        index=False,
    )

    print("\nPair-level spectral RMS differences:")
    print(
        pair_summary.to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}",
        )
    )

    print(
        "\nChannels with same direction in all 5 pairs:",
        int(same_direction_all_5.sum()),
    )

    print(
        "Channels with same direction in >=4/5 pairs:",
        int(majority_direction_4_of_5.sum()),
    )

    print("\nMost consistent texture-controlled regions:")

    if features.empty:
        print("NONE")
    else:
        print(
            features[
                [
                    "wavenumber_cm1",
                    "mean_pair_delta_hydric_minus_nonhydric",
                    "median_pair_delta_hydric_minus_nonhydric",
                    "pairs_hydric_higher",
                    "pairs_hydric_lower",
                    "same_direction_all_5",
                ]
            ].to_string(
                index=False,
                float_format=lambda x: f"{x:.4f}",
            )
        )

    print("\nWrote:")
    print(OUT_PAIR_SUMMARY)
    print(OUT_SPECTRA)
    print(OUT_FEATURES)


if __name__ == "__main__":
    main()