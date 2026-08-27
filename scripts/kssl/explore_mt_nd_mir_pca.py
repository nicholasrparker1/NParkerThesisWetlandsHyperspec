from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

plt.rcParams.update({"font.family":"Arial", "font.size":10.5, "axes.titlesize":15,
                     "axes.labelsize":11, "axes.titleweight":"bold", "figure.facecolor":"white"})

ROOT = Path(__file__).resolve().parents[2]
NPZ = ROOT / "data/processed/kssl_mt_nd_mir/kssl_mt_nd_mir_mean_spectra.npz"
QC = ROOT / "outputs/tables/kssl_mir_qc/mir_sample_qc_summary.csv"
OUT_T = ROOT / "outputs/tables/kssl_mir_analysis"
OUT_F = ROOT / "outputs/figures/kssl_mir_analysis"

GROUPS = ["Both NWI + SSURGO", "SSURGO only", "NWI only", "Neither"]
COLORS = {"Both NWI + SSURGO":"#0F7C80", "SSURGO only":"#D9A441",
          "NWI only":"#9B5B7B", "Neither":"#9AA6AD"}


def main():
    OUT_T.mkdir(parents=True, exist_ok=True); OUT_F.mkdir(parents=True, exist_ok=True)
    z = np.load(NPZ)
    ids, wn, X = z["smp_id"], z["wavenumber_cm1"], z["absorbance"]
    meta = pd.read_csv(QC).set_index("smp_id").loc[ids].reset_index()

    # Standard normal variate removes sample-level offset and scale. The first
    # derivative emphasizes spectral shape while limiting baseline effects.
    snv = (X - X.mean(axis=1, keepdims=True)) / X.std(axis=1, keepdims=True)
    deriv = np.gradient(snv, wn, axis=1)
    A = deriv - deriv.mean(axis=0, keepdims=True)
    U, S, Vt = np.linalg.svd(A, full_matrices=False)
    scores = U[:, :10] * S[:10]
    variance = S**2 / np.sum(S**2)

    score_df = meta.copy()
    for i in range(10): score_df[f"PC{i+1}"] = scores[:, i]
    score_df.to_csv(OUT_T / "mir_pca_scores.csv", index=False)
    pd.DataFrame({"component":np.arange(1, 11), "explained_variance_ratio":variance[:10],
                  "cumulative_variance":np.cumsum(variance[:10])}).to_csv(OUT_T / "mir_pca_variance.csv", index=False)
    pd.DataFrame({"wavenumber_cm1":wn, "PC1_loading":Vt[0], "PC2_loading":Vt[1]}).to_csv(
        OUT_T / "mir_pca_loadings.csv", index=False)

    fig, ax = plt.subplots(figsize=(9, 6.3))
    for group in GROUPS:
        mask = meta.spatial_evidence_group.eq(group).to_numpy()
        ax.scatter(scores[mask,0], scores[mask,1], s=35 if group != "NWI only" else 55,
                   alpha=.75, color=COLORS[group], edgecolor="white", linewidth=.35,
                   label=f"{group} (n={mask.sum()})")
    ax.axhline(0,color="#C8D0D5",lw=.8); ax.axvline(0,color="#C8D0D5",lw=.8)
    ax.set_xlabel(f"PC1 ({variance[0]:.1%})"); ax.set_ylabel(f"PC2 ({variance[1]:.1%})")
    ax.set_title("MIR spectral variation overlaps across spatial-evidence groups", weight="bold")
    ax.legend(frameon=False, fontsize=9); ax.grid(alpha=.18)
    fig.tight_layout(); fig.savefig(OUT_F / "mir_pca_by_spatial_group.png", dpi=220); plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(10, 6.5), sharex=True)
    axes[0].plot(wn, Vt[0], color="#17324D", lw=1); axes[0].set_ylabel("PC1 loading")
    axes[1].plot(wn, Vt[1], color="#0F7C80", lw=1); axes[1].set_ylabel("PC2 loading")
    axes[1].set_xlabel(r"Wavenumber (cm$^{-1}$)")
    for ax in axes: ax.invert_xaxis(); ax.grid(alpha=.18)
    fig.suptitle("Wavenumbers contributing to the first MIR components", weight="bold")
    fig.tight_layout(); fig.savefig(OUT_F / "mir_pca_loadings.png", dpi=220); plt.close(fig)

    summary = score_df.groupby("spatial_evidence_group", observed=True).agg(
        n=("smp_id","size"), PC1_median=("PC1","median"), PC2_median=("PC2","median"),
        total_carbon_median=("smp_id", lambda s: np.nan)  # placeholder keeps scope explicit
    ).drop(columns="total_carbon_median").reindex(GROUPS)
    summary.to_csv(OUT_T / "mir_pca_group_summary.csv")
    print(f"PC1={variance[0]:.4f}; PC2={variance[1]:.4f}; cumulative={variance[:2].sum():.4f}")

if __name__ == "__main__": main()
