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

MIR = (
    ROOT
    / "data"
    / "processed"
    / "kssl_mt_nd_mir"
    / "kssl_mt_nd_mir_mean_spectra.npz"
)

HORIZONS = ND / "nd_reference_lab_horizons.csv"

OUT_SAMPLES = ND / "nd_reference_mir_samples.csv"
OUT_SPECTRAL = ND / "nd_reference_mir_group_spectra.csv"
OUT_FEATURES = ND / "nd_reference_mir_largest_differences.csv"


def main():

    # ---------------------------------------------------------
    # Load reference horizons
    # ---------------------------------------------------------

    h = pd.read_csv(HORIZONS, low_memory=False)

    h["smp_id"] = pd.to_numeric(
        h["smp_id"],
        errors="coerce",
    )

    # Upper-30-cm reference horizons only.
    h = h[
        pd.to_numeric(
            h["overlap_0_30_cm"],
            errors="coerce",
        ) > 0
    ].copy()

    # ---------------------------------------------------------
    # Load existing QC'd mean MIR matrix
    # ---------------------------------------------------------

    d = np.load(MIR, allow_pickle=True)

    mir_ids = pd.to_numeric(
        pd.Series(d["smp_id"]),
        errors="coerce",
    ).to_numpy()

    wavenumber = np.asarray(
        d["wavenumber_cm1"],
        dtype=float,
    )

    X = np.asarray(
        d["absorbance"],
        dtype=float,
    )

    id_to_row = {
        int(sid): i
        for i, sid in enumerate(mir_ids)
        if pd.notna(sid)
    }

    h["has_mir"] = h["smp_id"].apply(
        lambda x:
        pd.notna(x)
        and int(x) in id_to_row
    )

    ref = h[h["has_mir"]].copy()

    print("North Dakota reference MIR analysis")
    print("=" * 72)

    print(f"Upper-30-cm MIR samples: {len(ref)}")

    print("\nBy reference group:")
    print(
        ref.groupby("reference_group")
        .agg(
            samples=("smp_id", "size"),
            pedons=("user_pedon_id", "nunique"),
        )
        .to_string()
    )

    # Safety check: one MIR sample per pedon.
    counts = (
        ref.groupby("user_pedon_id")
        .size()
    )

    print(
        "\nMaximum MIR samples for any one pedon:",
        counts.max(),
    )

    # ---------------------------------------------------------
    # Extract the exact spectra
    # ---------------------------------------------------------

    rows = [
        id_to_row[int(sid)]
        for sid in ref["smp_id"]
    ]

    Xref = X[rows, :]

    # Save sample metadata.
    metadata_cols = [
        "smp_id",
        "user_pedon_id",
        "reference_group",
        "horizon_designation",
        "top_depth_cm",
        "bottom_depth_cm",
        "overlap_0_30_cm",
        "taxon_name",
        "nasis_taxonomy",
        "nasis_drainage_class",
        "estimated_organic_carbon_pct",
        "total_nitrogen_pct",
        "total_sulfur_pct",
        "fe_dithionite_pct",
        "fe_oxalate_pct",
        "clay_pct",
        "sand_pct",
        "silt_pct",
    ]

    metadata_cols = [
        c for c in metadata_cols
        if c in ref.columns
    ]

    ref[metadata_cols].to_csv(
        OUT_SAMPLES,
        index=False,
    )

    # ---------------------------------------------------------
    # Group spectral summaries
    # ---------------------------------------------------------

    hydric_mask = (
        ref["reference_group"]
        .eq("HYDRIC_REFERENCE")
        .to_numpy()
    )

    nonhydric_mask = (
        ref["reference_group"]
        .eq("NONHYDRIC_REFERENCE")
        .to_numpy()
    )

    Xh = Xref[hydric_mask]
    Xn = Xref[nonhydric_mask]

    hydric_mean = np.nanmean(Xh, axis=0)
    nonhydric_mean = np.nanmean(Xn, axis=0)

    hydric_median = np.nanmedian(Xh, axis=0)
    nonhydric_median = np.nanmedian(Xn, axis=0)

    difference_mean = (
        hydric_mean - nonhydric_mean
    )

    difference_median = (
        hydric_median - nonhydric_median
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
            (len(Xh) - 1) * hydric_sd**2
            + (len(Xn) - 1) * nonhydric_sd**2
        )
        / (len(Xh) + len(Xn) - 2)
    )

    standardized_difference = np.divide(
        difference_mean,
        pooled_sd,
        out=np.full_like(
            difference_mean,
            np.nan,
        ),
        where=pooled_sd > 0,
    )

    spectral = pd.DataFrame(
        {
            "wavenumber_cm1": wavenumber,
            "hydric_mean_absorbance":
                hydric_mean,
            "nonhydric_mean_absorbance":
                nonhydric_mean,
            "hydric_median_absorbance":
                hydric_median,
            "nonhydric_median_absorbance":
                nonhydric_median,
            "mean_difference_hydric_minus_nonhydric":
                difference_mean,
            "median_difference_hydric_minus_nonhydric":
                difference_median,
            "hydric_sd":
                hydric_sd,
            "nonhydric_sd":
                nonhydric_sd,
            "standardized_mean_difference":
                standardized_difference,
        }
    )

    spectral.to_csv(
        OUT_SPECTRAL,
        index=False,
    )

    # ---------------------------------------------------------
    # Identify strongest spectral differences.
    #
    # This is descriptive screening, NOT significance testing.
    # Adjacent MIR channels are highly correlated, so we do not
    # interpret individual channels as independent discoveries.
    # ---------------------------------------------------------

    ranked = spectral.copy()

    ranked["abs_standardized_difference"] = (
        ranked[
            "standardized_mean_difference"
        ].abs()
    )

    ranked = ranked.sort_values(
        "abs_standardized_difference",
        ascending=False,
    )

    # Keep peaks separated by at least 20 cm^-1 so that the
    # console isn't just 10 adjacent channels from one feature.
    selected = []

    for _, row in ranked.iterrows():

        wn = row["wavenumber_cm1"]

        if all(
            abs(wn - existing["wavenumber_cm1"])
            >= 20
            for existing in selected
        ):
            selected.append(row.to_dict())

        if len(selected) == 20:
            break

    features = pd.DataFrame(selected)

    features.to_csv(
        OUT_FEATURES,
        index=False,
    )

    # ---------------------------------------------------------
    # Console results
    # ---------------------------------------------------------

    print("\nLargest separated spectral differences:")
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

    # Whole-spectrum distance between group means.
    rms_difference = np.sqrt(
        np.nanmean(
            difference_mean**2
        )
    )

    print(
        "\nWhole-spectrum RMS difference "
        "between group means:",
        f"{rms_difference:.6f}",
    )

    print("\nWrote:")
    print(OUT_SAMPLES)
    print(OUT_SPECTRAL)
    print(OUT_FEATURES)


if __name__ == "__main__":
    main()