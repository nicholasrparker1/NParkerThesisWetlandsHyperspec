from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.cross_decomposition import PLSRegression
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.model_selection import GroupKFold


ROOT = Path(__file__).resolve().parents[2]
NPZ = ROOT / "data" / "processed" / "kssl_great_plains_mir" / "kssl_nd_mt_sd_ne_mean_mir_spectra.npz"
COHORT = ROOT / "outputs" / "tables" / "kssl_regional_expansion" / "nd_mt_sd_ne_surface_mir_cohort.csv"
OUT_TABLES = ROOT / "outputs" / "tables" / "kssl_regional_expansion"
OUT_FIGURES = ROOT / "outputs" / "figures" / "kssl_regional_expansion"

TARGETS = {
    "total_carbon_pct": ("Total carbon", "%"),
    "clay_pct": ("Clay", "%"),
    "ph_water": ("pH in water", "pH units"),
    "water_retention_15bar_pct": ("15-bar water retention", "%"),
    "water_retention_third_bar_pct": ("1/3-bar water retention", "%"),
    "cec_nh4oac_cmol_kg": ("CEC", r"cmol$_c$ kg$^{-1}$"),
    "fe_dithionite_pct": ("Dithionite-extractable Fe", "%"),
    "fe_oxalate_pct": ("Oxalate-extractable Fe", "%"),
}
PLOT_TARGETS = [
    "total_carbon_pct",
    "clay_pct",
    "ph_water",
    "water_retention_15bar_pct",
    "cec_nh4oac_cmol_kg",
    "fe_dithionite_pct",
]

plt.rcParams.update(
    {
        "font.family": "Arial",
        "font.size": 10.5,
        "axes.labelsize": 11,
        "figure.facecolor": "white",
    }
)


def preprocess(values: np.ndarray, wavenumber: np.ndarray) -> np.ndarray:
    standard_deviation = values.std(axis=1, keepdims=True)
    if np.any(standard_deviation == 0):
        raise ValueError("A spectrum has zero variance and cannot be SNV transformed.")
    snv = (values - values.mean(axis=1, keepdims=True)) / standard_deviation
    return np.gradient(snv, wavenumber, axis=1)


def fit_predict(x_train: np.ndarray, y_train: np.ndarray, x_test: np.ndarray) -> np.ndarray:
    components = min(10, len(y_train) - 1, x_train.shape[1])
    model = PLSRegression(n_components=components, scale=True, max_iter=1000)
    model.fit(x_train, y_train)
    return model.predict(x_test).ravel()


def metric_row(target: str, observed: np.ndarray, predicted: np.ndarray, **fields: object) -> dict[str, object]:
    rho, p_value = spearmanr(observed, predicted)
    return {
        "target": target,
        "label": TARGETS[target][0],
        "unit": TARGETS[target][1],
        "test_n": len(observed),
        "r2": r2_score(observed, predicted),
        "rmse": root_mean_squared_error(observed, predicted),
        "mae": mean_absolute_error(observed, predicted),
        "spearman_rho": rho,
        "spearman_p": p_value,
        **fields,
    }


def main() -> None:
    OUT_TABLES.mkdir(parents=True, exist_ok=True)
    OUT_FIGURES.mkdir(parents=True, exist_ok=True)
    spectral = np.load(NPZ)
    ids = spectral["smp_id"].astype(int)
    x = preprocess(spectral["absorbance"], spectral["wavenumber_cm1"])
    cohort = pd.read_csv(COHORT).set_index("smp_id").loc[ids].reset_index()

    project_metrics, project_predictions = [], []
    state_metrics, state_predictions = [], []
    for target in TARGETS:
        valid = cohort[target].notna().to_numpy()
        y = cohort.loc[valid, target].to_numpy(float)
        groups = cohort.loc[valid, "lab_proj_name"].fillna("unknown").astype(str).to_numpy()
        splitter = GroupKFold(n_splits=min(5, pd.Series(groups).nunique()))
        predicted = np.full(len(y), np.nan)
        folds = np.full(len(y), -1)
        for fold, (train, test) in enumerate(splitter.split(x[valid], y, groups), start=1):
            predicted[test] = fit_predict(x[valid][train], y[train], x[valid][test])
            folds[test] = fold
        project_metrics.append(
            metric_row(
                target,
                y,
                predicted,
                validation="project_grouped_5_fold",
                train_n="varies",
                groups=pd.Series(groups).nunique(),
            )
        )
        frame = cohort.loc[valid, ["smp_id", "pedon_key", "lab_proj_name", "state"]].copy()
        frame["target"] = target
        frame["observed"] = y
        frame["predicted"] = predicted
        frame["fold"] = folds
        project_predictions.append(frame)

        for held_out_state in sorted(cohort["state"].dropna().unique()):
            train = valid & ~cohort["state"].eq(held_out_state).to_numpy()
            test = valid & cohort["state"].eq(held_out_state).to_numpy()
            state_predicted = fit_predict(x[train], cohort.loc[train, target].to_numpy(float), x[test])
            observed = cohort.loc[test, target].to_numpy(float)
            state_metrics.append(
                metric_row(
                    target,
                    observed,
                    state_predicted,
                    validation="leave_one_state_out",
                    held_out_state=held_out_state,
                    train_n=int(train.sum()),
                    groups=cohort.loc[train, "lab_proj_name"].nunique(),
                )
            )
            frame = cohort.loc[test, ["smp_id", "pedon_key", "lab_proj_name", "state"]].copy()
            frame["target"] = target
            frame["observed"] = observed
            frame["predicted"] = state_predicted
            frame["held_out_state"] = held_out_state
            state_predictions.append(frame)

    project_metrics_df = pd.DataFrame(project_metrics)
    state_metrics_df = pd.DataFrame(state_metrics)
    project_predictions_df = pd.concat(project_predictions, ignore_index=True)
    state_predictions_df = pd.concat(state_predictions, ignore_index=True)
    project_metrics_df.to_csv(OUT_TABLES / "regional_project_grouped_metrics.csv", index=False)
    state_metrics_df.to_csv(OUT_TABLES / "regional_leave_one_state_out_metrics.csv", index=False)
    project_predictions_df.to_csv(OUT_TABLES / "regional_project_grouped_predictions.csv", index=False)
    state_predictions_df.to_csv(OUT_TABLES / "regional_leave_one_state_out_predictions.csv", index=False)

    fig, axes = plt.subplots(2, 3, figsize=(13, 8.2))
    indexed_metrics = project_metrics_df.set_index("target")
    for ax, target in zip(axes.flat, PLOT_TARGETS):
        values = project_predictions_df.loc[project_predictions_df["target"].eq(target)]
        row = indexed_metrics.loc[target]
        ax.scatter(values["observed"], values["predicted"], s=16, alpha=0.5, color="#0F7C80", edgecolor="none")
        lower = min(values["observed"].min(), values["predicted"].min())
        upper = max(values["observed"].max(), values["predicted"].max())
        ax.plot([lower, upper], [lower, upper], "--", color="#89959B", lw=1)
        label, unit = TARGETS[target]
        ax.set_title(f"{label} ({unit})\n$R^2$={row.r2:.2f}; Spearman rho={row.spearman_rho:.2f}", fontsize=10, weight="bold")
        ax.set_xlabel(f"Observed ({unit})")
        ax.set_ylabel(f"Predicted ({unit})")
        ax.grid(alpha=0.2)
    fig.suptitle("Regional MIR models are tested on unseen KSSL projects", fontsize=16, weight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(OUT_FIGURES / "regional_project_grouped_observed_predicted.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    matrix = state_metrics_df.pivot(index="target", columns="held_out_state", values="spearman_rho").loc[PLOT_TARGETS]
    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    image = ax.imshow(matrix.to_numpy(), vmin=-1, vmax=1, cmap="RdBu_r", aspect="auto")
    ax.set_xticks(np.arange(len(matrix.columns)), matrix.columns, rotation=20, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)), [TARGETS[target][0] for target in matrix.index])
    for row_index in range(matrix.shape[0]):
        for column_index in range(matrix.shape[1]):
            value = matrix.iloc[row_index, column_index]
            ax.text(column_index, row_index, f"{value:.2f}", ha="center", va="center", color="white" if abs(value) > 0.55 else "black")
    colorbar = fig.colorbar(image, ax=ax)
    colorbar.set_label("Spearman rank correlation (rho)")
    ax.set_title("Leave-one-state-out tests reveal geographic transferability", weight="bold")
    ax.set_xlabel("Held-out test state")
    fig.tight_layout()
    fig.savefig(OUT_FIGURES / "regional_leave_one_state_out_spearman.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    print("Project-grouped validation")
    print(project_metrics_df[["target", "test_n", "groups", "r2", "spearman_rho", "mae"]].to_string(index=False))
    print("\nLeave-one-state-out Spearman rho")
    print(matrix.to_string())


if __name__ == "__main__":
    main()
