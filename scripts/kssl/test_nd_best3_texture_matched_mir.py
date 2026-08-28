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

OUT = ND / "nd_best3_texture_matched_mir.csv"


def snv(X):
    means = np.nanmean(X, axis=1, keepdims=True)
    sds = np.nanstd(X, axis=1, ddof=1, keepdims=True)

    return (X - means) / sds


def main():

    d = np.load(MATRIX, allow_pickle=True)

    X = np.asarray(d["absorbance"], dtype=float)
    wn = np.asarray(d["wavenumber_cm1"], dtype=float)
    pedons = np.asarray(d["user_pedon_id"]).astype(str)

    Xsnv = snv(X)

    lookup = {p: i for i, p in enumerate(pedons)}

    pairs = pd.read_csv(PAIRS)

    # Best 3 texture matches only
    best3 = (
        pairs
        .sort_values("texture_distance")
        .head(3)
        .copy()
    )

    print("Best 3 texture-matched MIR test")
    print("=" * 72)

    print("\nSelected pairs:")
    print(
        best3[
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

    deltas = []

    for _, row in best3.iterrows():

        hpid = str(row["hydric_pedon"])
        npid = str(row["nonhydric_match"])

        h = Xsnv[lookup[hpid]]
        n = Xsnv[lookup[npid]]

        delta = h - n

        deltas.append(delta)

    D = np.vstack(deltas)

    out = pd.DataFrame(
        {
            "wavenumber_cm1": wn,
            "pair1_delta": D[0],
            "pair2_delta": D[1],
            "pair3_delta": D[2],
            "mean_delta": np.nanmean(D, axis=0),
            "median_delta": np.nanmedian(D, axis=0),
            "hydric_lower_count": np.sum(D < 0, axis=0),
            "hydric_higher_count": np.sum(D > 0, axis=0),
        }
    )

    out.to_csv(OUT, index=False)

    region = out[
        (out["wavenumber_cm1"] >= 1200)
        & (out["wavenumber_cm1"] <= 1400)
    ].copy()

    all3_lower = region[
        region["hydric_lower_count"] == 3
    ]

    print(
        "\nChannels 1200-1400 cm^-1 where hydric is lower in ALL 3 pairs:",
        len(all3_lower),
    )

    if not all3_lower.empty:

        strongest = (
            all3_lower
            .assign(abs_median=lambda x: x["median_delta"].abs())
            .sort_values("abs_median", ascending=False)
            .head(20)
        )

        print("\nStrongest all-3-agree channels:")
        print(
            strongest[
                [
                    "wavenumber_cm1",
                    "pair1_delta",
                    "pair2_delta",
                    "pair3_delta",
                    "mean_delta",
                    "median_delta",
                ]
            ].to_string(
                index=False,
                float_format=lambda x: f"{x:.4f}",
            )
        )

    # Summarize the key 1248-1298 band
    key = out[
        (out["wavenumber_cm1"] >= 1248)
        & (out["wavenumber_cm1"] <= 1298)
    ]

    print("\nKey 1248-1298 cm^-1 band:")
    print(
        "Channels:",
        len(key),
    )

    print(
        "All 3 hydric-lower:",
        int((key["hydric_lower_count"] == 3).sum()),
    )

    print(
        "Mean band delta:",
        f"{key['mean_delta'].mean():.4f}",
    )

    print(
        "Median band delta:",
        f"{key['median_delta'].median():.4f}",
    )

    print("\nWrote:")
    print(OUT)


if __name__ == "__main__":
    main()