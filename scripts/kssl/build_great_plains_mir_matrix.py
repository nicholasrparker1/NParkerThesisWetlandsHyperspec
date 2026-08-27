from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
LIBRARY = Path(r"D:\MIR Snapshot\MIR_Library")
MANIFEST = ROOT / "outputs" / "tables" / "kssl_regional_expansion" / "nd_mt_sd_ne_mir_scan_manifest.csv"
COHORT = ROOT / "outputs" / "tables" / "kssl_regional_expansion" / "nd_mt_sd_ne_surface_mir_cohort.csv"
OUT_DATA = ROOT / "data" / "processed" / "kssl_great_plains_mir"
OUT_TABLES = ROOT / "outputs" / "tables" / "kssl_regional_expansion"
OUT_FIGURES = ROOT / "outputs" / "figures" / "kssl_regional_expansion"
REFERENCE_WN = np.arange(4000.0, 598.0, -2.0)
MIN_REPLICATE_CORRELATION = 0.99

plt.rcParams.update(
    {
        "font.family": "Arial",
        "font.size": 10.5,
        "axes.labelsize": 11,
        "figure.facecolor": "white",
    }
)


def scan_path(row: pd.Series) -> Path:
    return LIBRARY / str(row["lab_proj_name"]) / Path(str(row["scan_path_name"])).with_suffix(".csv").name


def read_spectrum(path: Path) -> np.ndarray:
    values = np.loadtxt(path, delimiter=",")
    if values.ndim != 2 or values.shape[1] < 2:
        raise ValueError("unexpected_csv_structure")
    wn, absorbance = values[:, 0], values[:, 1]
    finite = np.isfinite(wn) & np.isfinite(absorbance)
    wn, absorbance = wn[finite], absorbance[finite]
    if len(wn) < 1000:
        raise ValueError("insufficient_finite_bands")
    order = np.argsort(wn)
    wn, absorbance = wn[order], absorbance[order]
    if wn[0] > 600.0 or wn[-1] < 4000.0:
        raise ValueError("insufficient_wavenumber_span")
    return np.interp(REFERENCE_WN[::-1], wn, absorbance)[::-1]


def choose_master(available: pd.DataFrame) -> pd.DataFrame:
    ranked = (
        available.assign(
            scan_date_parsed=pd.to_datetime(available["scan_date"], format="mixed", errors="coerce"),
            passed=available["qc_file_status"].eq("Passed").astype(int),
        )
        .groupby(["smp_id", "mir_scan_mas_id"], as_index=False)
        .agg(
            passed_scans=("passed", "sum"),
            scan_count=("mir_scan_det_id", "count"),
            latest_scan_date=("scan_date_parsed", "max"),
        )
        .sort_values(
            ["smp_id", "passed_scans", "scan_count", "latest_scan_date", "mir_scan_mas_id"],
            ascending=[True, False, False, False, False],
        )
    )
    ranked["master_rank"] = ranked.groupby("smp_id").cumcount() + 1
    selected = ranked.loc[ranked["master_rank"].eq(1), ["smp_id", "mir_scan_mas_id"]]
    ranked.to_csv(OUT_TABLES / "regional_mir_master_selection_audit.csv", index=False)
    return available.merge(selected, on=["smp_id", "mir_scan_mas_id"], how="inner")


def main() -> None:
    for directory in (OUT_DATA, OUT_TABLES, OUT_FIGURES):
        directory.mkdir(parents=True, exist_ok=True)

    manifest = pd.read_csv(MANIFEST)
    cohort = pd.read_csv(COHORT)
    manifest["csv_path"] = manifest.apply(scan_path, axis=1).astype(str)
    manifest["file_exists"] = manifest["csv_path"].map(lambda value: Path(value).is_file())
    manifest.to_csv(OUT_TABLES / "regional_mir_file_availability.csv", index=False)
    manifest.loc[~manifest["file_exists"]].to_csv(
        OUT_TABLES / "regional_missing_mir_scan_files.csv", index=False
    )
    chosen = choose_master(manifest.loc[manifest["file_exists"]].copy())

    spectra: list[tuple[int, np.ndarray]] = []
    qc_rows: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    for (sample_id, master_id), group in chosen.groupby(["smp_id", "mir_scan_mas_id"], sort=True):
        replicate_spectra, paths = [], []
        for row in group.itertuples(index=False):
            try:
                replicate_spectra.append(read_spectrum(Path(row.csv_path)))
                paths.append(row.csv_path)
            except Exception as exc:
                errors.append({"smp_id": sample_id, "path": row.csv_path, "error": str(exc)})
        if not replicate_spectra:
            continue
        values = np.vstack(replicate_spectra)
        provisional = np.median(values, axis=0)
        correlations = np.array([np.corrcoef(row, provisional)[0, 1] for row in values])
        accepted = np.isfinite(correlations) & (correlations >= MIN_REPLICATE_CORRELATION)
        if accepted.sum() < 2:
            errors.append({"smp_id": sample_id, "path": "|".join(paths), "error": "fewer_than_two_agreeing_replicates"})
            continue
        mean = values[accepted].mean(axis=0)
        rmse = np.sqrt(np.mean((values[accepted] - mean) ** 2, axis=1))
        spectra.append((int(sample_id), mean))
        qc_rows.append(
            {
                "smp_id": int(sample_id),
                "selected_mir_scan_mas_id": int(master_id),
                "available_replicates": len(values),
                "accepted_replicates": int(accepted.sum()),
                "excluded_replicates": int((~accepted).sum()),
                "minimum_replicate_correlation": float(np.nanmin(correlations)),
                "maximum_accepted_replicate_rmse_absorbance": float(rmse.max()),
                "replicate_correlation_threshold": MIN_REPLICATE_CORRELATION,
                "scan_paths": "|".join(paths),
            }
        )

    ids = np.array([row[0] for row in spectra], dtype=np.int64)
    matrix = np.vstack([row[1] for row in spectra])
    np.savez_compressed(
        OUT_DATA / "kssl_nd_mt_sd_ne_mean_mir_spectra.npz",
        smp_id=ids,
        wavenumber_cm1=REFERENCE_WN,
        absorbance=matrix,
    )
    qc = pd.DataFrame(qc_rows).merge(
        cohort[["smp_id", "lay_id", "pedon_key", "state", "lab_proj_name"]],
        on="smp_id",
        how="left",
        validate="one_to_one",
    )
    qc.to_csv(OUT_TABLES / "regional_mir_sample_qc.csv", index=False)
    pd.DataFrame(errors).to_csv(OUT_TABLES / "regional_mir_read_errors.csv", index=False)

    missing_ids = cohort.loc[~cohort["smp_id"].isin(ids)].copy()
    missing_ids.to_csv(OUT_TABLES / "regional_samples_without_usable_mir.csv", index=False)

    colors = {"Montana": "#315D73", "North Dakota": "#0F7C80", "South Dakota": "#D9A441", "Nebraska": "#8C657D"}
    id_to_index = {sample_id: index for index, sample_id in enumerate(ids)}
    fig, ax = plt.subplots(figsize=(10.5, 6))
    for state in colors:
        state_ids = qc.loc[qc["state"].eq(state), "smp_id"].astype(int)
        indices = [id_to_index[value] for value in state_ids if value in id_to_index]
        if not indices:
            continue
        median = np.median(matrix[indices], axis=0)
        lower, upper = np.quantile(matrix[indices], [0.25, 0.75], axis=0)
        ax.plot(REFERENCE_WN, median, color=colors[state], lw=1.8, label=f"{state} (n={len(indices)})")
        ax.fill_between(REFERENCE_WN, lower, upper, color=colors[state], alpha=0.12)
    ax.invert_xaxis()
    ax.set_xlabel(r"Wavenumber (cm$^{-1}$)")
    ax.set_ylabel("Absorbance (unitless)")
    ax.set_title("Median MIR spectra by state after averaging technical replicates", weight="bold")
    ax.legend(frameon=False)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(OUT_FIGURES / "regional_median_mir_spectra_by_state.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    state_summary = (
        qc.groupby("state")
        .agg(
            usable_samples=("smp_id", "nunique"),
            projects=("lab_proj_name", "nunique"),
            median_minimum_replicate_correlation=("minimum_replicate_correlation", "median"),
            excluded_replicates=("excluded_replicates", "sum"),
        )
        .reset_index()
    )
    state_summary.to_csv(OUT_TABLES / "regional_mir_usable_sample_summary.csv", index=False)
    print(state_summary.to_string(index=False))
    print(f"Usable independent samples: {len(ids)}/{len(cohort)}")
    print(f"Spectral variables: {matrix.shape[1]}")


if __name__ == "__main__":
    main()

