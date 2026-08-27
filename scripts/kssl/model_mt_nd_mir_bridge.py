from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

plt.rcParams.update({"font.family":"Arial", "font.size":10.5, "axes.titlesize":15,
                     "axes.labelsize":11, "axes.titleweight":"bold", "figure.facecolor":"white"})
from scipy.stats import spearmanr
from sklearn.cross_decomposition import PLSRegression
from sklearn.model_selection import GroupKFold
from sklearn.metrics import r2_score, mean_absolute_error, root_mean_squared_error

ROOT = Path(__file__).resolve().parents[2]
NPZ = ROOT / "data/processed/kssl_mt_nd_mir/kssl_mt_nd_mir_mean_spectra.npz"
COHORT = ROOT / "outputs/tables/kssl_spatial_results/kssl_mt_nd_spatial_analysis_table.csv"
OUT_T = ROOT / "outputs/tables/kssl_mir_bridge"
OUT_F = ROOT / "outputs/figures/kssl_mir_bridge"

TARGETS = {
    "total_carbon_pct": "Total carbon (%)",
    "fe_dithionite_pct": "Dithionite Fe (%)",
    "fe_oxalate_pct": "Oxalate Fe (%)",
    "clay_pct": "Clay (%)",
    "ph_water": "pH in water",
    "water_retention_15bar_pct": "15-bar water (%)",
    "cec_nh4oac_cmol_kg": r"CEC (cmol$_c$ kg$^{-1}$)",
    "spatial_evidence_score": "Spatial evidence score (0 to 2)",
}


AXIS_UNITS = {
    "total_carbon_pct": "%",
    "fe_dithionite_pct": "%",
    "fe_oxalate_pct": "%",
    "clay_pct": "%",
    "ph_water": "pH units",
    "water_retention_15bar_pct": "%",
    "cec_nh4oac_cmol_kg": r"cmol$_c$ kg$^{-1}$",
    "spatial_evidence_score": "Spatial evidence score (0 to 2)",
}

def preprocess(X, wn):
    snv = (X - X.mean(axis=1, keepdims=True)) / X.std(axis=1, keepdims=True)
    return np.gradient(snv, wn, axis=1)


def grouped_predictions(X, y, groups, n_components=10):
    unique = pd.Series(groups).nunique()
    if unique < 2: raise ValueError("At least two project groups are required")
    splitter = GroupKFold(n_splits=min(5, unique))
    pred = np.full(len(y), np.nan)
    fold = np.full(len(y), -1)
    for k, (train, test) in enumerate(splitter.split(X, y, groups)):
        ncomp = min(n_components, len(train)-1, X.shape[1])
        model = PLSRegression(n_components=ncomp, scale=True, max_iter=1000)
        model.fit(X[train], y[train])
        pred[test] = model.predict(X[test]).ravel()
        fold[test] = k + 1
    return pred, fold


def main():
    OUT_T.mkdir(parents=True, exist_ok=True); OUT_F.mkdir(parents=True, exist_ok=True)
    z = np.load(NPZ); ids=z["smp_id"].astype(int); wn=z["wavenumber_cm1"]; raw=z["absorbance"]
    X = preprocess(raw, wn)
    cohort = pd.read_csv(COHORT).set_index("smp_id").loc[ids].reset_index()
    cohort["spatial_evidence_score"] = np.select([
        cohort.spatial_evidence_group.eq("Both NWI + SSURGO"),
        cohort.spatial_evidence_group.isin(["SSURGO only", "NWI only"]),
    ], [2, 1], default=0)

    metrics, predictions = [], []
    for target, label in TARGETS.items():
        mask = cohort[target].notna().to_numpy()
        y = cohort.loc[mask, target].to_numpy(float)
        groups = cohort.loc[mask, "lab_proj_name"].fillna("unknown").astype(str).to_numpy()
        pred, fold = grouped_predictions(X[mask], y, groups)
        rho, p = spearmanr(y, pred)
        metrics.append({
            "target":target, "label":label, "n":len(y), "project_groups":pd.Series(groups).nunique(),
            "r2_grouped_cv":r2_score(y,pred), "rmse_grouped_cv":root_mean_squared_error(y,pred),
            "mae_grouped_cv":mean_absolute_error(y,pred), "spearman_rho":rho, "spearman_p":p,
            "pls_components":10,
        })
        part = cohort.loc[mask, ["smp_id","lay_id","lab_proj_name","state","spatial_evidence_group"]].copy()
        part["target"] = target; part["observed"] = y; part["predicted"] = pred; part["fold"] = fold
        predictions.append(part)

    metrics = pd.DataFrame(metrics)
    preds = pd.concat(predictions, ignore_index=True)
    metrics.to_csv(OUT_T / "grouped_cv_metrics.csv", index=False)
    preds.to_csv(OUT_T / "grouped_cv_predictions.csv", index=False)

    plot_targets = ["total_carbon_pct", "clay_pct", "ph_water", "water_retention_15bar_pct",
                    "cec_nh4oac_cmol_kg", "spatial_evidence_score"]
    fig, axes = plt.subplots(2, 3, figsize=(13, 8.2))
    for ax, target in zip(axes.flat, plot_targets):
        p = preds[preds.target.eq(target)]
        ax.scatter(p.observed, p.predicted, s=22, alpha=.65, color="#0F7C80", edgecolor="none")
        lo=min(p.observed.min(),p.predicted.min()); hi=max(p.observed.max(),p.predicted.max())
        ax.plot([lo,hi],[lo,hi],"--",color="#8B969D",lw=1)
        m=metrics.set_index("target").loc[target]
        ax.set_title(
            f"{TARGETS[target]}\n$R^2$={m.r2_grouped_cv:.2f}; Spearman rho={m.spearman_rho:.2f}",
            weight="bold", fontsize=10,
        )
        ax.set_xlabel(f"Observed ({AXIS_UNITS[target]})")
        ax.set_ylabel(f"Predicted ({AXIS_UNITS[target]})")
        ax.grid(alpha=.2)
    fig.suptitle("Project-grouped validation tests transfer beyond individual KSSL projects",weight="bold",fontsize=16)
    fig.tight_layout(rect=(0,0,1,.96)); fig.savefig(OUT_F / "mir_grouped_cv_observed_predicted.png",dpi=300,bbox_inches="tight"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(10,5.5))
    q=metrics.sort_values("spearman_rho")
    colors=["#D9A441" if x=="spatial_evidence_score" else "#0F7C80" for x in q.target]
    bars=ax.barh(q.label,q.spearman_rho,color=colors)
    ax.bar_label(bars,fmt="%.2f",padding=3)
    ax.axvline(0,color="#7D898F",lw=.8); ax.set_xlabel("Out-of-project Spearman rank correlation (rho)")
    ax.set_title("MIR transferability is evaluated separately for chemistry and spatial evidence",weight="bold")
    ax.grid(axis="x",alpha=.2); fig.tight_layout(); fig.savefig(OUT_F / "mir_grouped_cv_summary.png",dpi=300,bbox_inches="tight"); plt.close(fig)
    print(metrics[["target","n","project_groups","r2_grouped_cv","spearman_rho","mae_grouped_cv"]].to_string(index=False))

if __name__ == "__main__": main()
