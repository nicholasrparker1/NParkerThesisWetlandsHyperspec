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

OUT_SPECTRA = ND / "nd_mineral_mir_snv_group_spectra.csv"
OUT_FEATURES = ND / "nd_mineral_mir_snv_robust_features.csv"
OUT_LOO = ND / "nd_mineral_mir_leave_one_hydric_out.csv"


def snv(X):
    """Standard normal variate, applied independently to each spectrum."""
    means = np.nanmean(X, axis=1, keepdims=True)
    sds = np.nanstd(X, axis=1, ddof=1, keepdims=True)

    return np.divide(
        X - means,
        sds,
        out=np.full_like(X, np.nan),
        where=sds > 0,
    )


def standardized_difference(Xh, Xn):
    """Hydric minus nonhydric standardized mean difference."""
    h_mean = np.nanmean(Xh, axis=0)
    n_mean = np.nanmean(Xn, axis=0)

    h_sd = np.nanstd(Xh, axis=0, ddof=1)
    n_sd = np.nanstd(Xn, axis=0, ddof=1)

    nh = len(Xh)
    nn = len(Xn)

    pooled = np.sqrt(
        (
            (nh - 1) * h_sd**2
            + (nn - 1) * n_sd**2
        )
        / (nh + nn - 2)
    )

    d = np.divide(
        h_mean - n_mean,
        pooled,
        out=np.full_like(h_mean, np.nan),
        where=pooled > 0,
    )

    return h_mean, n_mean, d


def main():

    d = np.load(MATRIX, allow_pickle=True)

    X = np.asarray(d["absorbance"], dtype=float)
    wn = np.asarray(d["wavenumber_cm1"], dtype=float)

    groups = np.asarray(d["reference_group"]).astype(str)
    pedons = np.asarray(d["user_pedon_id"]).astype(str)

    hydric = groups == "HYDRIC_REFERENCE"
    nonhydric = groups == "NONHYDRIC_REFERENCE"

    print("North Dakota mineral MIR stress test")
    print("=" * 72)
    print(f"Hydric pedons: {hydric.sum()}")
    print(f"Nonhydric pedons: {nonhydric.sum()}")

    # ---------------------------------------------------------
    # SNV preprocessing
    # ---------------------------------------------------------

    Xsnv = snv(X)

    h_mean, n_mean, full_d = standardized_difference(
        Xsnv[hydric],
        Xsnv[nonhydric],
    )

    spectral = pd.DataFrame(
        {
            "wavenumber_cm1": wn,
            "hydric_mean_snv": h_mean,
            "nonhydric_mean_snv": n_mean,
            "snv_standardized_difference": full_d,
        }
    )

    spectral.to_csv(OUT_SPECTRA, index=False)

    # ---------------------------------------------------------
    # Leave one HYDRIC pedon out at a time.
    # Nonhydric reference set remains unchanged.
    # ---------------------------------------------------------

    hydric_pedons = pedons[hydric]

    loo_results = []

    loo_matrix = []

    for pid in hydric_pedons:

        keep_h = hydric & (pedons != pid)

        _, _, loo_d = standardized_difference(
            Xsnv[keep_h],
            Xsnv[nonhydric],
        )

        loo_matrix.append(loo_d)

        finite = np.isfinite(loo_d)

        if finite.any():
            idx = np.nanargmax(np.abs(loo_d))

            loo_results.append(
                {
                    "excluded_hydric_pedon": pid,
                    "remaining_hydric_n": int(keep_h.sum()),
                    "strongest_wavenumber_cm1": wn[idx],
                    "strongest_standardized_difference": loo_d[idx],
                    "max_absolute_standardized_difference":
                        abs(loo_d[idx]),
                }
            )

    loo_matrix = np.vstack(loo_matrix)

    loo_df = pd.DataFrame(loo_results)
    loo_df.to_csv(OUT_LOO, index=False)

    # ---------------------------------------------------------
    # Robustness at every channel.
    #
    # Ask:
    # - Does every leave-one-out run retain the SAME SIGN?
    # - What is the weakest absolute effect across LOO runs?
    # ---------------------------------------------------------

    sign_full = np.sign(full_d)
    sign_loo = np.sign(loo_matrix)

    same_sign_all = np.all(
        sign_loo == sign_full[None, :],
        axis=0,
    )

    min_abs_loo = np.nanmin(
        np.abs(loo_matrix),
        axis=0,
    )

    median_abs_loo = np.nanmedian(
        np.abs(loo_matrix),
        axis=0,
    )

    robustness = pd.DataFrame(
        {
            "wavenumber_cm1": wn,
            "full_snv_standardized_difference": full_d,
            "same_direction_all_hydric_LOO": same_sign_all,
            "minimum_absolute_LOO_difference": min_abs_loo,
            "median_absolute_LOO_difference": median_abs_loo,
        }
    )

    # Require directional stability first.
    ranked = robustness[
        robustness["same_direction_all_hydric_LOO"]
    ].copy()

    ranked = ranked.sort_values(
        "minimum_absolute_LOO_difference",
        ascending=False,
    )

    # Again separate selected channels by >=20 cm-1.
    selected = []

    for _, row in ranked.iterrows():

        w = row["wavenumber_cm1"]

        if all(
            abs(w - x["wavenumber_cm1"]) >= 20
            for x in selected
        ):
            selected.append(row.to_dict())

        if len(selected) == 20:
            break

    features = pd.DataFrame(selected)
    features.to_csv(OUT_FEATURES, index=False)

    # ---------------------------------------------------------
    # Console output
    # ---------------------------------------------------------

    print("\nFull-cohort SNV result:")
    idx = np.nanargmax(np.abs(full_d))

    print(
        "Strongest SNV difference:",
        f"{wn[idx]:.0f} cm^-1",
        f"d={full_d[idx]:.3f}",
    )

    print("\nLeave-one-hydric-pedon-out:")
    print(
        loo_df.to_string(
            index=False,
            float_format=lambda x: f"{x:.3f}",
        )
    )

    print("\nMost robust separated SNV regions:")
    if features.empty:
        print("NONE")
    else:
        print(
            features[
                [
                    "wavenumber_cm1",
                    "full_snv_standardized_difference",
                    "minimum_absolute_LOO_difference",
                    "median_absolute_LOO_difference",
                ]
            ].to_string(
                index=False,
                float_format=lambda x: f"{x:.3f}",
            )
        )

    print("\nWrote:")
    print(OUT_SPECTRA)
    print(OUT_FEATURES)
    print(OUT_LOO)


if __name__ == "__main__":
    main()