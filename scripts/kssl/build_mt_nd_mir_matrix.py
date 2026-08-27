from pathlib import Path
import re

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

plt.rcParams.update({"font.family":"Arial", "font.size":10.5, "axes.titlesize":15,
                     "axes.labelsize":11, "axes.titleweight":"bold", "figure.facecolor":"white"})

ROOT = Path(__file__).resolve().parents[2]
DRIVE_ROOT = Path(r"D:\MIR Snapshot\MIR_Library")
MANIFEST = ROOT / "outputs/tables/kssl_mir_cohort/mt_nd_mir_scan_manifest.csv"
COHORT = ROOT / "outputs/tables/kssl_spatial_results/kssl_mt_nd_spatial_analysis_table.csv"
OUT = ROOT / "data/processed/kssl_mt_nd_mir"
TABLES = ROOT / "outputs/tables/kssl_mir_qc"
FIGURES = ROOT / "outputs/figures/kssl_mir_qc"


def scan_csv_path(row):
    return DRIVE_ROOT / str(row.lab_proj_name) / Path(str(row.scan_path_name)).with_suffix(".csv").name


def read_spectrum(path):
    a = np.loadtxt(path, delimiter=",")
    if a.ndim != 2 or a.shape[1] < 2:
        raise ValueError(f"Unexpected spectral CSV structure: {path}")
    return a[:, 0], a[:, 1]


def safe_group_name(value):
    return re.sub(r"[^A-Za-z0-9]+", "_", str(value)).strip("_")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    manifest = pd.read_csv(MANIFEST)
    cohort = pd.read_csv(COHORT)
    manifest["csv_path"] = manifest.apply(scan_csv_path, axis=1).astype(str)
    manifest["file_exists"] = manifest.csv_path.map(lambda x: Path(x).is_file())
    manifest.to_csv(TABLES / "mt_nd_mir_file_availability.csv", index=False)

    missing = manifest.loc[~manifest.file_exists].copy()
    missing.to_csv(TABLES / "missing_mir_scan_files.csv", index=False)
    available = manifest.loc[manifest.file_exists].copy()
    available["scan_date_parsed"] = pd.to_datetime(available.scan_date, format="mixed", errors="coerce")
    available["passed"] = available.qc_file_status.eq("Passed").astype(int)

    master_rank = (available.groupby(["smp_id", "mir_scan_mas_id"], as_index=False)
                   .agg(passed_scans=("passed", "sum"), scan_count=("mir_scan_det_id", "count"),
                        latest_scan_date=("scan_date_parsed", "max")))
    master_rank = master_rank.sort_values(
        ["smp_id", "passed_scans", "scan_count", "latest_scan_date", "mir_scan_mas_id"],
        ascending=[True, False, False, False, False]
    )
    master_rank["master_rank"] = master_rank.groupby("smp_id").cumcount() + 1
    selected = master_rank.loc[master_rank.master_rank.eq(1), ["smp_id", "mir_scan_mas_id"]]
    chosen = available.merge(selected, on=["smp_id", "mir_scan_mas_id"], how="inner")
    master_rank.to_csv(TABLES / "mir_master_selection_audit.csv", index=False)

    spectra = []
    qc_rows = []
    # Harmonize slightly shifted project grids to a shared 2 cm-1 axis.
    reference_wn = np.arange(4000.0, 598.0, -2.0)
    for (smp_id, master_id), g in chosen.groupby(["smp_id", "mir_scan_mas_id"], sort=True):
        ys, paths = [], []
        for row in g.itertuples(index=False):
            wn, y = read_spectrum(Path(row.csv_path))
            if wn[0] > wn[-1]:
                wn_asc, y_asc = wn[::-1], y[::-1]
            else:
                wn_asc, y_asc = wn, y
            if wn_asc[0] > 600.0 or wn_asc[-1] < 4000.0:
                raise ValueError(f"Spectrum does not span 600-4000 cm-1: {row.csv_path}")
            y_common = np.interp(reference_wn[::-1], wn_asc, y_asc)[::-1]
            ys.append(y_common); paths.append(row.csv_path)
        Y = np.vstack(ys)
        mean = Y.mean(axis=0)
        rmse = np.sqrt(np.mean((Y - mean) ** 2, axis=1))
        corr = [np.corrcoef(y, mean)[0, 1] for y in Y]
        spectra.append((int(smp_id), mean))
        qc_rows.append({
            "smp_id": int(smp_id), "selected_mir_scan_mas_id": int(master_id),
            "replicate_count": len(Y), "mean_replicate_rmse": float(rmse.mean()),
            "max_replicate_rmse": float(rmse.max()), "min_replicate_correlation": float(np.min(corr)),
            "passed_scan_count": int(g.passed.sum()), "scan_paths": "|".join(paths),
        })

    ids = np.array([x[0] for x in spectra], dtype=np.int64)
    matrix = np.vstack([x[1] for x in spectra])
    np.savez_compressed(OUT / "kssl_mt_nd_mir_mean_spectra.npz",
                        smp_id=ids, wavenumber_cm1=reference_wn, absorbance=matrix)
    pd.DataFrame({"wavenumber_cm1": reference_wn}).to_csv(OUT / "mir_wavenumber_axis.csv", index=False)
    pd.DataFrame(matrix, index=ids, columns=[f"wn_{x:.5f}" for x in reference_wn]).rename_axis("smp_id").to_csv(
        OUT / "kssl_mt_nd_mir_mean_spectra_wide.csv")

    qc = pd.DataFrame(qc_rows).merge(
        cohort[["smp_id", "lay_id", "state", "spatial_evidence_group", "hydric_evidence_tier", "RASTERVALU", "nwi_intersect"]],
        on="smp_id", how="left", validate="one_to_one")
    qc.to_csv(TABLES / "mir_sample_qc_summary.csv", index=False)
    missing_samples = cohort.loc[~cohort.smp_id.isin(ids),
        ["smp_id", "lay_id", "state", "spatial_evidence_group", "hydric_evidence_tier"]]
    missing_samples.to_csv(TABLES / "missing_mir_samples.csv", index=False)

    groups = ["Both NWI + SSURGO", "SSURGO only", "NWI only", "Neither"]
    colors = ["#0F7C80", "#D9A441", "#9B5B7B", "#9AA6AD"]
    fig, ax = plt.subplots(figsize=(10.5, 6))
    id_to_idx = {int(v): i for i, v in enumerate(ids)}
    for group, color in zip(groups, colors):
        group_ids = qc.loc[qc.spatial_evidence_group.eq(group), "smp_id"].astype(int)
        idx = [id_to_idx[x] for x in group_ids if x in id_to_idx]
        if not idx: continue
        med = np.median(matrix[idx], axis=0)
        q25, q75 = np.quantile(matrix[idx], [.25, .75], axis=0)
        ax.plot(reference_wn, med, color=color, lw=1.8, label=f"{group} (n={len(idx)})")
        ax.fill_between(reference_wn, q25, q75, color=color, alpha=.12)
    ax.invert_xaxis(); ax.set_xlabel(r"Wavenumber (cm$^{-1}$)"); ax.set_ylabel("Absorbance (unitless)")
    ax.set_title("Median MIR spectra after averaging technical replicates", weight="bold")
    ax.legend(frameon=False); ax.grid(alpha=.2)
    fig.tight_layout(); fig.savefig(FIGURES / "mean_mir_spectra_by_spatial_group.png", dpi=300); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    ax.hist(qc.max_replicate_rmse, bins=35, color="#0F7C80", edgecolor="white")
    ax.set_xlabel("Maximum replicate-to-mean RMSE (unitless absorbance)")
    ax.set_ylabel("Samples")
    ax.set_title("Technical MIR replicates are screened before modeling", weight="bold")
    ax.grid(axis="y", alpha=.2)
    fig.tight_layout(); fig.savefig(FIGURES / "mir_replicate_rmse_distribution.png", dpi=300); plt.close(fig)

    print(f"Usable samples: {len(ids)}/{len(cohort)}")
    print(f"Selected scan files: {len(chosen)}")
    print(f"Spectral variables: {matrix.shape[1]}")
    print(f"Median maximum replicate RMSE: {qc.max_replicate_rmse.median():.6f}")


if __name__ == "__main__":
    main()


