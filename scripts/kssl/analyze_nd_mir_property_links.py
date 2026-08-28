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
META = ND / "nd_mineral_reference_mir_samples.csv"

OUT_CORR = ND / "nd_mineral_mir_property_correlations.csv"
OUT_SUMMARY = ND / "nd_mineral_mir_property_correlation_summary.csv"
OUT_HYDRIC_REGIONS = ND / "nd_mineral_mir_hydric_property_overlap.csv"


PROPERTIES = [
    "estimated_organic_carbon_pct",
    "total_nitrogen_pct",
    "total_sulfur_pct",
    "fe_dithionite_pct",
    "fe_oxalate_pct",
    "al_dithionite_pct",
    "al_oxalate_pct",
    "clay_pct",
    "sand_pct",
]


def snv(X):
    means = np.nanmean(X, axis=1, keepdims=True)
    sds = np.nanstd(X, axis=1, ddof=1, keepdims=True)

    return np.divide(
        X - means,
        sds,
        out=np.full_like(X, np.nan),
        where=sds > 0,
    )


def pearson_by_channel(X, y):
    """
    Pearson correlation between one soil property and
    every spectral channel.
    """

    r = np.full(X.shape[1], np.nan)
    n = np.zeros(X.shape[1], dtype=int)

    for j in range(X.shape[1]):

        x = X[:, j]

        valid = (
            np.isfinite(x)
            & np.isfinite(y)
        )

        n[j] = valid.sum()

        if n[j] < 4:
            continue

        xv = x[valid]
        yv = y[valid]

        if (
            np.nanstd(xv) == 0
            or np.nanstd(yv) == 0
        ):
            continue

        r[j] = np.corrcoef(
            xv,
            yv,
        )[0, 1]

    return r, n


def select_spaced_features(df, value_col, n=10, spacing=20):
    """
    Rank by absolute value while requiring spectral
    features to be at least `spacing` cm^-1 apart.
    """

    ranked = df.copy()

    ranked["abs_rank_value"] = (
        ranked[value_col].abs()
    )

    ranked = ranked.sort_values(
        "abs_rank_value",
        ascending=False,
    )

    selected = []

    for _, row in ranked.iterrows():

        if not np.isfinite(row[value_col]):
            continue

        wn = row["wavenumber_cm1"]

        if all(
            abs(
                wn
                - x["wavenumber_cm1"]
            ) >= spacing
            for x in selected
        ):
            selected.append(
                row.to_dict()
            )

        if len(selected) == n:
            break

    return pd.DataFrame(selected)


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

    matrix_ids = np.asarray(
        d["smp_id"],
        dtype=int,
    )

    meta = pd.read_csv(
        META,
        low_memory=False,
    )

    meta["smp_id"] = pd.to_numeric(
        meta["smp_id"],
        errors="coerce",
    ).astype("Int64")

    # Reorder metadata to EXACTLY match matrix rows.
    meta = (
        meta.set_index("smp_id")
        .loc[matrix_ids]
        .reset_index()
    )

    assert np.array_equal(
        meta["smp_id"].astype(int).to_numpy(),
        matrix_ids,
    )

    Xsnv = snv(X)

    print("North Dakota MIR -> soil-property bridge")
    print("=" * 76)
    print(f"Independent pedons/spectra: {len(meta)}")

    print("\nReference groups:")
    print(
        meta["reference_group"]
        .value_counts()
        .to_string()
    )

    # ---------------------------------------------------------
    # Correlate each laboratory property with every
    # SNV-preprocessed MIR channel.
    # ---------------------------------------------------------

    correlation_frames = []
    summary_rows = []

    for prop in PROPERTIES:

        if prop not in meta.columns:
            print(f"\nWARNING: missing property: {prop}")
            continue

        y = pd.to_numeric(
            meta[prop],
            errors="coerce",
        ).to_numpy(dtype=float)

        n_property = np.isfinite(y).sum()

        r, n = pearson_by_channel(
            Xsnv,
            y,
        )

        result = pd.DataFrame(
            {
                "property": prop,
                "wavenumber_cm1": wn,
                "pearson_r": r,
                "n": n,
            }
        )

        correlation_frames.append(result)

        selected = select_spaced_features(
            result,
            "pearson_r",
            n=10,
            spacing=20,
        )

        strongest_idx = np.nanargmax(
            np.abs(r)
        )

        summary_rows.append(
            {
                "property": prop,
                "n_samples": n_property,
                "strongest_wavenumber_cm1":
                    wn[strongest_idx],
                "strongest_pearson_r":
                    r[strongest_idx],
            }
        )

        print(f"\n{prop}")
        print("-" * 76)
        print(f"Samples with laboratory value: {n_property}")

        print(
            selected[
                [
                    "wavenumber_cm1",
                    "pearson_r",
                    "n",
                ]
            ].to_string(
                index=False,
                float_format=lambda x: f"{x:.3f}",
            )
        )

    correlations = pd.concat(
        correlation_frames,
        ignore_index=True,
    )

    summary = pd.DataFrame(
        summary_rows
    )

    correlations.to_csv(
        OUT_CORR,
        index=False,
    )

    summary.to_csv(
        OUT_SUMMARY,
        index=False,
    )

    # ---------------------------------------------------------
    # Compare property-sensitive channels with the
    # hydric/nonhydric SNV difference.
    #
    # This is descriptive:
    # Are channels separating the reference groups also
    # associated with C/N/S/Fe/Al or simply texture?
    # ---------------------------------------------------------

    hydric = (
        meta["reference_group"]
        .eq("HYDRIC_REFERENCE")
        .to_numpy()
    )

    nonhydric = (
        meta["reference_group"]
        .eq("NONHYDRIC_REFERENCE")
        .to_numpy()
    )

    hydric_mean = np.nanmean(
        Xsnv[hydric],
        axis=0,
    )

    nonhydric_mean = np.nanmean(
        Xsnv[nonhydric],
        axis=0,
    )

    hydric_difference = (
        hydric_mean
        - nonhydric_mean
    )

    overlap_frames = []

    for prop in PROPERTIES:

        c = correlations[
            correlations["property"].eq(prop)
        ].copy()

        c[
            "hydric_minus_nonhydric_mean_snv"
        ] = hydric_difference

        # Simple joint ranking:
        # large property correlation AND large group difference.
        c["joint_signal"] = (
            c["pearson_r"].abs()
            * c[
                "hydric_minus_nonhydric_mean_snv"
            ].abs()
        )

        selected = select_spaced_features(
            c,
            "joint_signal",
            n=10,
            spacing=20,
        )

        selected["property"] = prop

        overlap_frames.append(selected)

    overlap = pd.concat(
        overlap_frames,
        ignore_index=True,
    )

    overlap.to_csv(
        OUT_HYDRIC_REGIONS,
        index=False,
    )

    print("\n" + "=" * 76)
    print("SUMMARY OF STRONGEST PROPERTY ASSOCIATIONS")
    print("=" * 76)

    print(
        summary.to_string(
            index=False,
            float_format=lambda x: f"{x:.3f}",
        )
    )

    print("\n" + "=" * 76)
    print("HYDRIC-SEPARATING REGIONS WITH PROPERTY ASSOCIATIONS")
    print("=" * 76)

    for prop in PROPERTIES:

        x = overlap[
            overlap["property"].eq(prop)
        ]

        if x.empty:
            continue

        print(f"\n{prop}")

        print(
            x[
                [
                    "wavenumber_cm1",
                    "pearson_r",
                    "hydric_minus_nonhydric_mean_snv",
                    "joint_signal",
                ]
            ].head(5).to_string(
                index=False,
                float_format=lambda z: f"{z:.3f}",
            )
        )

    print("\nWrote:")
    print(OUT_CORR)
    print(OUT_SUMMARY)
    print(OUT_HYDRIC_REGIONS)


if __name__ == "__main__":
    main()
    