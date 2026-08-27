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
MATCHES = ND / "nd_mir_sample_level_texture_matches.csv"

OUT = ND / "nd_sample_texture_matched_mir.csv"


def snv(X):
    mean = np.nanmean(X, axis=1, keepdims=True)
    sd = np.nanstd(X, axis=1, ddof=1, keepdims=True)

    return np.divide(
        X - mean,
        sd,
        out=np.full_like(X, np.nan),
        where=sd > 0,
    )


def summarize_band(df, low, high, name):

    x = df[
        (df["wavenumber_cm1"] >= low)
        & (df["wavenumber_cm1"] <= high)
    ]

    print(f"\n{name}: {low}-{high} cm^-1")
    print("-" * 72)

    print("Channels:", len(x))

    print(
        "Hydric lower in all 5:",
        int((x["hydric_lower_count"] == 5).sum()),
    )

    print(
        "Hydric lower in >=4/5:",
        int((x["hydric_lower_count"] >= 4).sum()),
    )

    print(
        "Median mean-pair delta:",
        f"{x['mean_delta'].median():.4f}",
    )

    print(
        "Median of channel medians:",
        f"{x['median_delta'].median():.4f}",
    )


def main():

    d = np.load(
        MATRIX,
        allow_pickle=True,
    )

    X = np.asarray(
        d["absorbance"],
        dtype=float,
    )

    wn = np.asarray(
        d["wavenumber_cm1"],
        dtype=float,
    )

    smp_ids = np.asarray(
        d["smp_id"],
        dtype=int,
    )

    Xsnv = snv(X)

    lookup = {
        smp_id: i
        for i, smp_id in enumerate(smp_ids)
    }

    matches = pd.read_csv(MATCHES)

    matches = matches.sort_values(
        "sample_texture_distance"
    ).reset_index(drop=True)

    print("Exact-sample texture-matched MIR test")
    print("=" * 72)

    print("\nFrozen sample-level pairs:")
    print(
        matches[
            [
                "hydric_pedon",
                "hydric_smp_id",
                "nonhydric_pedon",
                "nonhydric_smp_id",
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

    deltas = []
    pair_names = []

    for _, row in matches.iterrows():

        hid = int(row["hydric_smp_id"])
        nid = int(row["nonhydric_smp_id"])

        if hid not in lookup:
            raise ValueError(
                f"Missing hydric sample {hid}"
            )

        if nid not in lookup:
            raise ValueError(
                f"Missing nonhydric sample {nid}"
            )

        delta = (
            Xsnv[lookup[hid]]
            - Xsnv[lookup[nid]]
        )

        deltas.append(delta)

        pair_names.append(
            f"{hid}_minus_{nid}"
        )

    D = np.vstack(deltas)

    out = pd.DataFrame(
        {
            "wavenumber_cm1": wn,
            "mean_delta": np.nanmean(D, axis=0),
            "median_delta": np.nanmedian(D, axis=0),
            "hydric_lower_count": np.sum(D < 0, axis=0),
            "hydric_higher_count": np.sum(D > 0, axis=0),
        }
    )

    for i, name in enumerate(pair_names):
        out[name] = D[i]

    out.to_csv(
        OUT,
        index=False,
    )

    print(
        "\nWhole spectrum channels hydric-lower in all 5:",
        int((out["hydric_lower_count"] == 5).sum()),
    )

    print(
        "Whole spectrum channels hydric-higher in all 5:",
        int((out["hydric_higher_count"] == 5).sum()),
    )

    summarize_band(
        out,
        1248,
        1298,
        "Previously identified candidate region",
    )

    summarize_band(
        out,
        1200,
        1400,
        "Broader candidate region",
    )

    candidate = out[
        (out["wavenumber_cm1"] >= 1200)
        & (out["wavenumber_cm1"] <= 1400)
    ].copy()

    candidate["abs_median"] = (
        candidate["median_delta"].abs()
    )

    strongest = (
        candidate
        .sort_values(
            "abs_median",
            ascending=False,
        )
        .head(20)
    )

    print(
        "\nStrongest channels within 1200-1400 cm^-1:"
    )

    print(
        strongest[
            [
                "wavenumber_cm1",
                "mean_delta",
                "median_delta",
                "hydric_lower_count",
                "hydric_higher_count",
            ]
        ].to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}",
        )
    )

    # ------------------------------------------------------
    # Also evaluate only the three closest sample matches.
    # This subset is defined ONLY by texture distance.
    # ------------------------------------------------------

    D3 = D[:3]

    best3 = pd.DataFrame(
        {
            "wavenumber_cm1": wn,
            "mean_delta": np.nanmean(D3, axis=0),
            "median_delta": np.nanmedian(D3, axis=0),
            "hydric_lower_count": np.sum(D3 < 0, axis=0),
            "hydric_higher_count": np.sum(D3 > 0, axis=0),
        }
    )

    key3 = best3[
        (best3["wavenumber_cm1"] >= 1248)
        & (best3["wavenumber_cm1"] <= 1298)
    ]

    print("\nBest-3 exact-sample matches")
    print("-" * 72)

    print(
        "1248-1298 channels hydric-lower in all 3:",
        int((key3["hydric_lower_count"] == 3).sum()),
        "/",
        len(key3),
    )

    print(
        "1248-1298 median mean delta:",
        f"{key3['mean_delta'].median():.4f}",
    )

    print("\nWrote:")
    print(OUT)


if __name__ == "__main__":
    main()