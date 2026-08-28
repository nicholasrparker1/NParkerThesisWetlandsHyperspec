from pathlib import Path
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

BASE = (
    ROOT
    / "outputs"
    / "tables"
    / "kssl_neon_linkage"
)

OSBS = BASE / "osbs_validation"

SAMPLES = OSBS / "osbs_frozen_validation_samples.csv"
PAIRS = OSBS / "osbs_frozen_texture_matches.csv"

# Raw MIR library used previously.
MIR_ROOT = Path(r"D:\MIR Snapshot\MIR_Library")

OUT_PAIRS = OSBS / "osbs_nd_band_validation_pairs.csv"
OUT_CHANNELS = OSBS / "osbs_nd_band_validation_channels.csv"
OUT_SUMMARY = OSBS / "osbs_nd_band_validation_summary.csv"
OUT_SPECTRA = OSBS / "osbs_nd_band_validation_spectra.csv"

# -------------------------------------------------------------
# PRE-SPECIFIED NORTH DAKOTA HYPOTHESIS
# -------------------------------------------------------------

BAND_MIN = 1248.0
BAND_MAX = 1298.0

CORE_MIN = 1272.0
CORE_MAX = 1280.0


def read_scan_csv(path):
    x = pd.read_csv(
        path,
        header=None,
        names=["wavenumber", "absorbance"],
    )

    x["wavenumber"] = pd.to_numeric(
        x["wavenumber"],
        errors="coerce",
    )

    x["absorbance"] = pd.to_numeric(
        x["absorbance"],
        errors="coerce",
    )

    return x.dropna()


def load_mean_spectrum(smp_id):

    files = list(
        MIR_ROOT.rglob(f"{int(smp_id)}XS*.csv")
    )

    if not files:
        raise FileNotFoundError(
            f"No MIR CSV files found for sample {smp_id}"
        )

    spectra = []

    for f in files:

        x = read_scan_csv(f)

        # Sort ascending for interpolation.
        x = x.sort_values("wavenumber")

        spectra.append(x)

    # Use first scan's native grid.
    grid = spectra[0]["wavenumber"].to_numpy()

    values = []

    for x in spectra:

        values.append(
            np.interp(
                grid,
                x["wavenumber"].to_numpy(),
                x["absorbance"].to_numpy(),
            )
        )

    mean_abs = np.mean(
        np.vstack(values),
        axis=0,
    )

    return grid, mean_abs, len(files)


def snv(y):

    y = np.asarray(y, dtype=float)

    sd = np.std(y, ddof=0)

    if sd == 0:
        return np.full_like(y, np.nan)

    return (y - np.mean(y)) / sd


def interp_to_grid(w, y, grid):

    order = np.argsort(w)

    return np.interp(
        grid,
        w[order],
        y[order],
    )


def main():

    samples = pd.read_csv(SAMPLES)
    pairs = pd.read_csv(PAIRS)

    print("Independent OSBS validation of North Dakota MIR hypothesis")
    print("=" * 78)

    print(
        f"Pre-specified candidate band: "
        f"{BAND_MIN:.0f}-{BAND_MAX:.0f} cm^-1"
    )

    print(
        f"Pre-specified core region: "
        f"{CORE_MIN:.0f}-{CORE_MAX:.0f} cm^-1"
    )

    # ---------------------------------------------------------
    # Load spectra for ALL frozen samples.
    # No sample selection occurs here.
    # ---------------------------------------------------------

    spectra = {}

    print("\nLoading frozen MIR samples:")

    for _, row in samples.iterrows():

        smp_id = int(row["smp_id"])

        w, a, n_scans = load_mean_spectrum(smp_id)

        spectra[smp_id] = {
            "w": w,
            "raw": a,
            "snv": snv(a),
        }

        print(
            f"{smp_id} | "
            f"{row['validation_group']} | "
            f"{row['user_pedon_id']} | "
            f"{n_scans} scans"
        )

    # Common 2-cm^-1 grid, matching ND analysis.
    grid = np.arange(
        700.0,
        4000.0 + 0.1,
        2.0,
    )

    # ---------------------------------------------------------
    # Frozen pair differences.
    # ---------------------------------------------------------

    pair_spectra = []
    pair_summary = []

    for _, pair in pairs.iterrows():

        hid = int(pair["hydric_smp_id"])
        nid = int(pair["nonhydric_smp_id"])

        hs = interp_to_grid(
            spectra[hid]["w"],
            spectra[hid]["snv"],
            grid,
        )

        ns = interp_to_grid(
            spectra[nid]["w"],
            spectra[nid]["snv"],
            grid,
        )

        delta = hs - ns

        band_mask = (
            (grid >= BAND_MIN)
            & (grid <= BAND_MAX)
        )

        core_mask = (
            (grid >= CORE_MIN)
            & (grid <= CORE_MAX)
        )

        band_delta = float(
            np.mean(delta[band_mask])
        )

        core_delta = float(
            np.mean(delta[core_mask])
        )

        pair_summary.append(
            {
                "hydric_pedon":
                    pair["hydric_pedon"],

                "hydric_smp_id": hid,

                "nonhydric_pedon":
                    pair["nonhydric_pedon"],

                "nonhydric_smp_id": nid,

                "sample_texture_distance":
                    pair["sample_texture_distance"],

                "band_1248_1298_mean_delta":
                    band_delta,

                "core_1272_1280_mean_delta":
                    core_delta,

                "band_supports_nd_direction":
                    band_delta < 0,

                "core_supports_nd_direction":
                    core_delta < 0,
            }
        )

        pair_spectra.append(delta)

    pair_summary = pd.DataFrame(pair_summary)

    D = np.vstack(pair_spectra)

    # Export the complete frozen Florida comparison spectra.
    # Each comparison is:
    # SNV-normalized hydric spectrum - matched nonhydric spectrum.
    spectra_out = pd.DataFrame({
        "wavenumber_cm1": grid
    })

    for i in range(D.shape[0]):
        spectra_out[f"comparison_{i + 1}"] = D[i, :]

    spectra_out["mean_difference"] = np.mean(D, axis=0)
    spectra_out["median_difference"] = np.median(D, axis=0)

    # ---------------------------------------------------------
    # Channel-level validation inside ONLY the pre-specified
    # ND candidate band.
    # ---------------------------------------------------------

    band_mask = (
        (grid >= BAND_MIN)
        & (grid <= BAND_MAX)
    )

    rows = []

    for j in np.where(band_mask)[0]:

        vals = D[:, j]

        rows.append(
            {
                "wavenumber_cm1": grid[j],
                "mean_pair_delta":
                    np.mean(vals),
                "median_pair_delta":
                    np.median(vals),
                "hydric_lower_count":
                    int(np.sum(vals < 0)),
                "hydric_higher_count":
                    int(np.sum(vals > 0)),
            }
        )

    channels = pd.DataFrame(rows)

    # ---------------------------------------------------------
    # Pre-specified summary statistics.
    # ---------------------------------------------------------

    band_pair_values = (
        pair_summary[
            "band_1248_1298_mean_delta"
        ]
        .to_numpy()
    )

    core_pair_values = (
        pair_summary[
            "core_1272_1280_mean_delta"
        ]
        .to_numpy()
    )

    n_band_support = int(
        np.sum(band_pair_values < 0)
    )

    n_core_support = int(
        np.sum(core_pair_values < 0)
    )

    channels_all4 = int(
        (
            channels["hydric_lower_count"] == 4
        ).sum()
    )

    channels_3plus = int(
        (
            channels["hydric_lower_count"] >= 3
        ).sum()
    )

    summary = pd.DataFrame(
        [
            {
                "validation_region":
                    "OSBS_FL107",

                "hydric_pairs": 4,

                "candidate_band":
                    "1248-1298 cm^-1",

                "pairs_supporting_nd_direction":
                    n_band_support,

                "median_pair_band_delta":
                    np.median(band_pair_values),

                "mean_pair_band_delta":
                    np.mean(band_pair_values),

                "core_region":
                    "1272-1280 cm^-1",

                "pairs_supporting_core_direction":
                    n_core_support,

                "median_pair_core_delta":
                    np.median(core_pair_values),

                "channels_in_candidate_band":
                    len(channels),

                "channels_hydric_lower_all4":
                    channels_all4,

                "channels_hydric_lower_3plus":
                    channels_3plus,
            }
        ]
    )

    # ---------------------------------------------------------
    # Print results.
    # ---------------------------------------------------------

    print("\nFrozen pair validation:")
    print(
        pair_summary.to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}",
        )
    )

    print("\nPre-specified ND band result:")
    print("-" * 72)

    print(
        f"Pairs with hydric-lower mean "
        f"1248-1298 signal: "
        f"{n_band_support}/4"
    )

    print(
        f"Median paired band delta: "
        f"{np.median(band_pair_values):.4f}"
    )

    print(
        f"Mean paired band delta: "
        f"{np.mean(band_pair_values):.4f}"
    )

    print("\nPre-specified ND core result:")
    print("-" * 72)

    print(
        f"Pairs with hydric-lower mean "
        f"1272-1280 signal: "
        f"{n_core_support}/4"
    )

    print(
        f"Median paired core delta: "
        f"{np.median(core_pair_values):.4f}"
    )

    print("\nChannel consistency within 1248-1298:")
    print("-" * 72)

    print(
        f"Channels hydric-lower in all 4: "
        f"{channels_all4}/{len(channels)}"
    )

    print(
        f"Channels hydric-lower in >=3/4: "
        f"{channels_3plus}/{len(channels)}"
    )

    print("\nChannel results:")
    print(
        channels.to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}",
        )
    )

    # ---------------------------------------------------------
    # Sensitivity: weakest texture pair excluded.
    #
    # This is explicitly secondary and does NOT alter the
    # primary four-pair validation.
    # ---------------------------------------------------------

    weakest_idx = (
        pair_summary[
            "sample_texture_distance"
        ].idxmax()
    )

    sensitivity = pair_summary.drop(
        index=weakest_idx
    )

    vals = sensitivity[
        "band_1248_1298_mean_delta"
    ].to_numpy()

    print("\nSecondary sensitivity analysis:")
    print("-" * 72)

    print(
        "Excluded weakest texture pair:",
        pair_summary.loc[
            weakest_idx,
            "hydric_pedon",
        ],
    )

    print(
        "Remaining pairs supporting ND direction:",
        f"{int(np.sum(vals < 0))}/3",
    )

    print(
        "Remaining median paired band delta:",
        f"{np.median(vals):.4f}",
    )

    # ---------------------------------------------------------
    # Save.
    # ---------------------------------------------------------

    pair_summary.to_csv(
        OUT_PAIRS,
        index=False,
    )

    channels.to_csv(
        OUT_CHANNELS,
        index=False,
    )

    summary.to_csv(
        OUT_SUMMARY,
        index=False,
    )

    spectra_out.to_csv(
        OUT_SPECTRA,
        index=False,
    )

    print("\nWrote:")
    print(OUT_PAIRS)
    print(OUT_CHANNELS)
    print(OUT_SUMMARY)
    print(OUT_SPECTRA)

if __name__ == "__main__":
    main()