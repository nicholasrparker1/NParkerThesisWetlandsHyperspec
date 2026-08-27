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

PROCESSED_MIR = (
    ROOT
    / "data"
    / "processed"
    / "kssl_mt_nd_mir"
    / "kssl_mt_nd_mir_mean_spectra.npz"
)

RAW_MIR = Path(r"D:\MIR Snapshot\MIR_Library")

HORIZONS = ND / "nd_reference_lab_horizons.csv"

OUT_SAMPLES = ND / "nd_mineral_reference_mir_samples.csv"
OUT_SPECTRA = ND / "nd_mineral_reference_mir_group_spectra.csv"
OUT_FEATURES = ND / "nd_mineral_reference_mir_largest_differences.csv"
OUT_MATRIX = ND / "nd_mineral_reference_mir_matrix.npz"


def is_mineral_horizon(designation):
    """
    Exclude organic O horizons.
    Retain mineral A/E/B/etc. horizons.
    """
    s = str(designation).strip().upper()
    return not s.startswith("O")


def read_raw_scan(path, target_axis):
    """
    Read raw KSSL MIR CSV:
        wavenumber, absorbance

    Interpolate onto the existing project's common MIR axis.
    """
    raw = pd.read_csv(
        path,
        header=None,
        names=["wavenumber_cm1", "absorbance"],
    )

    wn = pd.to_numeric(
        raw["wavenumber_cm1"],
        errors="coerce",
    ).to_numpy()

    absorbance = pd.to_numeric(
        raw["absorbance"],
        errors="coerce",
    ).to_numpy()

    valid = (
        np.isfinite(wn)
        & np.isfinite(absorbance)
    )

    wn = wn[valid]
    absorbance = absorbance[valid]

    # np.interp requires increasing x.
    order = np.argsort(wn)

    wn = wn[order]
    absorbance = absorbance[order]

    interpolated = np.interp(
        target_axis,
        wn,
        absorbance,
    )

    return interpolated


def find_raw_replicates(smp_id):
    """
    Locate raw CSV replicates anywhere in MIR_Library.
    """
    pattern = f"{int(smp_id)}XS*.csv"

    return sorted(
        RAW_MIR.rglob(pattern)
    )


def main():

    h = pd.read_csv(
        HORIZONS,
        low_memory=False,
    )

    d = np.load(
        PROCESSED_MIR,
        allow_pickle=True,
    )

    processed_ids = np.asarray(
        d["smp_id"],
        dtype=int,
    )

    target_axis = np.asarray(
        d["wavenumber_cm1"],
        dtype=float,
    )

    processed_X = np.asarray(
        d["absorbance"],
        dtype=float,
    )

    processed_lookup = {
        int(sid): i
        for i, sid in enumerate(processed_ids)
    }

    # ---------------------------------------------------------
    # Restrict to upper 30 cm and mineral horizons.
    # ---------------------------------------------------------

    h["top_depth_cm"] = pd.to_numeric(
        h["top_depth_cm"],
        errors="coerce",
    )

    h["bottom_depth_cm"] = pd.to_numeric(
        h["bottom_depth_cm"],
        errors="coerce",
    )

    h["overlap_0_30_cm"] = pd.to_numeric(
        h["overlap_0_30_cm"],
        errors="coerce",
    )

    h["smp_id"] = pd.to_numeric(
        h["smp_id"],
        errors="coerce",
    )

    h = h[
        (h["overlap_0_30_cm"] > 0)
        & h["horizon_designation"].apply(
            is_mineral_horizon
        )
    ].copy()

    # ---------------------------------------------------------
    # Select ONE shallowest mineral horizon per pedon.
    # Selection uses no chemistry or spectroscopy.
    # ---------------------------------------------------------

    h = h.sort_values(
        [
            "user_pedon_id",
            "top_depth_cm",
            "bottom_depth_cm",
        ]
    )

    selected = (
        h.groupby(
            "user_pedon_id",
            as_index=False,
        )
        .first()
    )

    print("North Dakota mineral-horizon MIR experiment")
    print("=" * 74)

    print("\nSelected mineral horizons:")
    print(
        selected[
            [
                "user_pedon_id",
                "reference_group",
                "smp_id",
                "horizon_designation",
                "top_depth_cm",
                "bottom_depth_cm",
            ]
        ].to_string(index=False)
    )

    # ---------------------------------------------------------
    # Obtain spectrum for every selected sample.
    #
    # Prefer existing processed spectrum when available.
    # Otherwise recover raw replicates and interpolate them
    # onto the exact same common axis.
    # ---------------------------------------------------------

    spectra = []
    source_rows = []

    for _, row in selected.iterrows():

        sid = int(row["smp_id"])

        if sid in processed_lookup:

            spectrum = processed_X[
                processed_lookup[sid],
                :
            ]

            source = "EXISTING_PROCESSED_MATRIX"
            n_replicates = np.nan

        else:

            paths = find_raw_replicates(sid)

            if not paths:
                print(
                    f"WARNING: no MIR spectrum found "
                    f"for sample {sid}"
                )
                continue

            replicate_spectra = []

            for path in paths:

                replicate_spectra.append(
                    read_raw_scan(
                        path,
                        target_axis,
                    )
                )

            spectrum = np.nanmean(
                np.vstack(replicate_spectra),
                axis=0,
            )

            source = "RECOVERED_RAW_CSV"
            n_replicates = len(paths)

        spectra.append(spectrum)

        source_rows.append(
            {
                **row.to_dict(),
                "mir_source": source,
                "n_raw_replicates_used":
                    n_replicates,
            }
        )

    metadata = pd.DataFrame(source_rows)
    X = np.vstack(spectra)

    # ---------------------------------------------------------
    # Basic structural checks.
    # ---------------------------------------------------------

    print("\nFinal MIR cohort:")
    print(
        metadata.groupby("reference_group")
        .agg(
            samples=("smp_id", "size"),
            pedons=("user_pedon_id", "nunique"),
        )
        .to_string()
    )

    print("\nSpectrum sources:")
    print(
        metadata["mir_source"]
        .value_counts()
        .to_string()
    )

    print(
        "\nMaximum samples per pedon:",
        metadata.groupby(
            "user_pedon_id"
        ).size().max(),
    )

    # ---------------------------------------------------------
    # Save exact matrix for reproducibility.
    # ---------------------------------------------------------

    np.savez_compressed(
        OUT_MATRIX,
        smp_id=metadata["smp_id"]
        .astype(int)
        .to_numpy(),
        user_pedon_id=metadata[
            "user_pedon_id"
        ].astype(str).to_numpy(),
        reference_group=metadata[
            "reference_group"
        ].astype(str).to_numpy(),
        wavenumber_cm1=target_axis,
        absorbance=X,
    )

    metadata.to_csv(
        OUT_SAMPLES,
        index=False,
    )

    # ---------------------------------------------------------
    # Group comparison.
    # ---------------------------------------------------------

    hydric_mask = (
        metadata["reference_group"]
        .eq("HYDRIC_REFERENCE")
        .to_numpy()
    )

    nonhydric_mask = (
        metadata["reference_group"]
        .eq("NONHYDRIC_REFERENCE")
        .to_numpy()
    )

    Xh = X[hydric_mask]
    Xn = X[nonhydric_mask]

    hydric_mean = np.nanmean(
        Xh,
        axis=0,
    )

    nonhydric_mean = np.nanmean(
        Xn,
        axis=0,
    )

    hydric_median = np.nanmedian(
        Xh,
        axis=0,
    )

    nonhydric_median = np.nanmedian(
        Xn,
        axis=0,
    )

    mean_difference = (
        hydric_mean
        - nonhydric_mean
    )

    median_difference = (
        hydric_median
        - nonhydric_median
    )

    hydric_sd = np.nanstd(
        Xh,
        axis=0,
        ddof=1,
    )

    nonhydric_sd = np.nanstd(
        Xn,
        axis=0,
        ddof=1,
    )

    pooled_sd = np.sqrt(
        (
            (len(Xh) - 1)
            * hydric_sd**2
            + (len(Xn) - 1)
            * nonhydric_sd**2
        )
        / (
            len(Xh)
            + len(Xn)
            - 2
        )
    )

    standardized = np.divide(
        mean_difference,
        pooled_sd,
        out=np.full_like(
            mean_difference,
            np.nan,
        ),
        where=pooled_sd > 0,
    )

    spectral = pd.DataFrame(
        {
            "wavenumber_cm1":
                target_axis,
            "hydric_mean_absorbance":
                hydric_mean,
            "nonhydric_mean_absorbance":
                nonhydric_mean,
            "hydric_median_absorbance":
                hydric_median,
            "nonhydric_median_absorbance":
                nonhydric_median,
            "mean_difference_hydric_minus_nonhydric":
                mean_difference,
            "median_difference_hydric_minus_nonhydric":
                median_difference,
            "hydric_sd":
                hydric_sd,
            "nonhydric_sd":
                nonhydric_sd,
            "standardized_mean_difference":
                standardized,
        }
    )

    spectral.to_csv(
        OUT_SPECTRA,
        index=False,
    )

    # ---------------------------------------------------------
    # Rank separated spectral regions.
    # Require >=20 cm^-1 spacing so adjacent channels do not
    # fill the entire output.
    # ---------------------------------------------------------

    ranked = spectral.copy()

    ranked[
        "abs_standardized_difference"
    ] = (
        ranked[
            "standardized_mean_difference"
        ].abs()
    )

    ranked = ranked.sort_values(
        "abs_standardized_difference",
        ascending=False,
    )

    selected_features = []

    for _, row in ranked.iterrows():

        wn = row["wavenumber_cm1"]

        if all(
            abs(
                wn
                - existing["wavenumber_cm1"]
            ) >= 20
            for existing
            in selected_features
        ):
            selected_features.append(
                row.to_dict()
            )

        if len(selected_features) == 20:
            break

    features = pd.DataFrame(
        selected_features
    )

    features.to_csv(
        OUT_FEATURES,
        index=False,
    )

    print(
        "\nLargest mineral-soil spectral differences:"
    )

    print(
        features[
            [
                "wavenumber_cm1",
                "hydric_mean_absorbance",
                "nonhydric_mean_absorbance",
                "mean_difference_hydric_minus_nonhydric",
                "standardized_mean_difference",
            ]
        ].to_string(
            index=False,
            float_format=lambda x: f"{x:.6f}",
        )
    )

    rms = np.sqrt(
        np.nanmean(
            mean_difference**2
        )
    )

    print(
        "\nWhole-spectrum RMS difference:",
        f"{rms:.6f}",
    )

    print("\nWrote:")
    print(OUT_SAMPLES)
    print(OUT_SPECTRA)
    print(OUT_FEATURES)
    print(OUT_MATRIX)


if __name__ == "__main__":
    main()