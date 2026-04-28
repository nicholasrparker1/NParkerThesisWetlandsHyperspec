from __future__ import annotations

from pathlib import Path
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from sklearn.decomposition import PCA
from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import ElasticNetCV, LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error

from src.config import FIGURES, TABLES
from src.preprocess import build_bad_band_mask, build_invalid_value_mask
from src.scripts.pull_spectrum_latlon import read_roi_stats_spectrum, snap_to_valid_pixel
from src.workflow import find_h5_files, find_h5_for_point, normalize_reflectance, normalize_wavelengths_nm


# ------------------------------------------------------------
# INPUTS
# ------------------------------------------------------------
POINTS_CSV = Path("data/processed/bare_soil_points.csv")
SOIL_XLSX = Path("data/field/ROCX_soil_good_points.xlsx")

ROI = 3
SNAP = 40

TARGET_WAVELENGTHS_NM = [550, 670, 705, 740, 800, 970, 1200, 1650, 2200]

# Broad wavelength regions
VIS = (400, 700)
NIR = (700, 1300)
SWIR1 = (1450, 1800)
SWIR2 = (1950, 2400)


# ------------------------------------------------------------
# HELPER FUNCTIONS
# ------------------------------------------------------------
def nearest_reflectance(wavelengths: np.ndarray, spectrum: np.ndarray, target_nm: float) -> float:
    good = np.isfinite(wavelengths) & np.isfinite(spectrum)
    if not np.any(good):
        return np.nan

    idx_good = np.where(good)[0]
    idx = idx_good[np.argmin(np.abs(wavelengths[idx_good] - target_nm))]
    return float(spectrum[idx])


def band_mean(wavelengths: np.ndarray, spectrum: np.ndarray, lo_nm: float, hi_nm: float) -> float:
    mask = (
        np.isfinite(wavelengths)
        & np.isfinite(spectrum)
        & (wavelengths >= lo_nm)
        & (wavelengths <= hi_nm)
    )
    if not np.any(mask):
        return np.nan
    return float(np.nanmean(spectrum[mask]))


def safe_ratio(a: float, b: float) -> float:
    if not np.isfinite(a) or not np.isfinite(b) or abs(b) < 1e-12:
        return np.nan
    return float(a / b)


def safe_nd(a: float, b: float) -> float:
    denom = a + b
    if not np.isfinite(a) or not np.isfinite(b) or abs(denom) < 1e-12:
        return np.nan
    return float((a - b) / denom)


def add_spectral_features(out: dict, wl: np.ndarray, med_clean: np.ndarray) -> dict:
    # Single-band reflectance values
    for target in TARGET_WAVELENGTHS_NM:
        out[f"R_{target}nm"] = nearest_reflectance(wl, med_clean, target)

    R550 = out["R_550nm"]
    R670 = out["R_670nm"]
    R705 = out["R_705nm"]
    R740 = out["R_740nm"]
    R800 = out["R_800nm"]
    R970 = out["R_970nm"]
    R1200 = out["R_1200nm"]
    R1650 = out["R_1650nm"]
    R2200 = out["R_2200nm"]

    # Region means
    out["VIS_mean"] = band_mean(wl, med_clean, *VIS)
    out["NIR_mean"] = band_mean(wl, med_clean, *NIR)
    out["SWIR1_mean"] = band_mean(wl, med_clean, *SWIR1)
    out["SWIR2_mean"] = band_mean(wl, med_clean, *SWIR2)

    # Vegetation / wetness / soil-style features
    out["NDVI_800_670"] = safe_nd(R800, R670)
    out["NDWI_800_1200"] = safe_nd(R800, R1200)
    out["NDWI_800_1650"] = safe_nd(R800, R1650)
    out["NIR_SWIR1_ratio"] = safe_ratio(R800, R1650)
    out["NIR_SWIR2_ratio"] = safe_ratio(R800, R2200)
    out["VIS_NIR_ratio"] = safe_ratio(out["VIS_mean"], out["NIR_mean"])
    out["SWIR1_SWIR2_ratio"] = safe_ratio(out["SWIR1_mean"], out["SWIR2_mean"])

    # Simple slopes / contrasts
    out["VIS_to_NIR_contrast"] = R800 - R550 if np.isfinite(R800) and np.isfinite(R550) else np.nan
    out["red_edge_slope_705_740"] = safe_ratio(R740 - R705, 740 - 705)
    out["SWIR_drop_1650_2200"] = R1650 - R2200 if np.isfinite(R1650) and np.isfinite(R2200) else np.nan

    return out


def pearson_r(x: pd.Series, y: pd.Series) -> float:
    good = np.isfinite(x.astype(float)) & np.isfinite(y.astype(float))
    if good.sum() < 3:
        return np.nan
    return float(np.corrcoef(x[good], y[good])[0, 1])


def spearman_rho(x: pd.Series, y: pd.Series) -> float:
    good = np.isfinite(x.astype(float)) & np.isfinite(y.astype(float))
    if good.sum() < 3:
        return np.nan
    return float(pd.Series(x[good]).rank().corr(pd.Series(y[good]).rank()))


def evaluate_loo_model(df: pd.DataFrame, y_col: str, feature_cols: list[str], model_name: str):
    good = df[[y_col] + feature_cols].dropna()
    if len(good) < 5:
        return None

    X = good[feature_cols].astype(float).values
    y = good[y_col].astype(float).values

    loo = LeaveOneOut()

    if model_name == "linear":
        model = make_pipeline(StandardScaler(), LinearRegression())

    elif model_name == "elastic_net":
        # Conservative for tiny datasets. This may still be unstable if n is very small.
        model = make_pipeline(
            StandardScaler(),
            ElasticNetCV(
                l1_ratio=[0.1, 0.5, 0.9, 1.0],
                alphas=np.logspace(-4, 2, 50),
                cv=min(3, len(good)),
                max_iter=10000,
                random_state=42,
            ),
        )

    elif model_name == "random_forest":
        model = RandomForestRegressor(
            n_estimators=500,
            max_depth=3,
            min_samples_leaf=2,
            random_state=42,
        )

    else:
        raise ValueError(model_name)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        y_pred = cross_val_predict(model, X, y, cv=loo)

    rmse = mean_squared_error(y, y_pred, squared=False)
    mae = mean_absolute_error(y, y_pred)

    # R2 can be ugly/negative with tiny data. Still report it honestly.
    r2 = r2_score(y, y_pred)

    return {
        "target": y_col,
        "model": model_name,
        "n": len(good),
        "features": ", ".join(feature_cols),
        "loo_rmse": rmse,
        "loo_mae": mae,
        "loo_r2": r2,
    }


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------
    # 1. Load field/ground truth data
    # --------------------------------------------------------
    soil = pd.read_excel(SOIL_XLSX)

    needed = [
        "sampling_point_id",
        "som_avg_pct",
        "carbon_pct",
        "nitrogen_pct",
        "veg_taxa_recorded_count",
        "habitat_type",
    ]

    missing = [c for c in needed if c not in soil.columns]
    if missing:
        raise ValueError(f"Missing columns in {SOIL_XLSX}: {missing}")

    soil = soil[needed].copy()
    soil["sampling_point_id"] = soil["sampling_point_id"].astype(str)

    points = pd.read_csv(POINTS_CSV)

    if not {"id", "lat", "lon"}.issubset(points.columns):
        raise ValueError("bare_soil_points.csv must have columns: id, lat, lon")

    points["id"] = points["id"].astype(str)

    df = points.merge(
        soil,
        left_on="id",
        right_on="sampling_point_id",
        how="left",
    )

    if df["som_avg_pct"].isna().any():
        missing_ids = df.loc[df["som_avg_pct"].isna(), "id"].tolist()
        raise ValueError(f"These point IDs did not match the Excel table: {missing_ids}")

    # --------------------------------------------------------
    # 2. Locate NEON H5 files
    # --------------------------------------------------------
    h5_files = find_h5_files()

    rows = []
    spectra_rows = []

    # --------------------------------------------------------
    # 3. Extract cleaned ROI median spectrum for each point
    # --------------------------------------------------------
    for _, row in df.iterrows():
        pid = row["id"]
        lat = float(row["lat"])
        lon = float(row["lon"])

        print(f"\n=== {pid}: lat={lat}, lon={lon} ===")

        match = find_h5_for_point(lat, lon, h5_files)
        if match is None:
            print("SKIP: not inside any H5 tile")
            continue

        print("Matched H5:", match.h5_path.name)
        print(f"raw row/col: r={match.row}, c={match.col}")

        r, c = snap_to_valid_pixel(
            str(match.h5_path),
            match.reflectance_path,
            match.row,
            match.col,
            radius=SNAP,
            band=0,
        )

        if r is None or c is None:
            print("SKIP: no valid pixel after snapping")
            continue

        if (r, c) != (match.row, match.col):
            print(f"snapped row/col: r={r}, c={c}")

        wl, med, lo, hi, bounds = read_roi_stats_spectrum(
            str(match.h5_path),
            match.reflectance_path,
            match.wavelength_path,
            r,
            c,
            roi=ROI,
            p_lo=25,
            p_hi=75,
        )

        wl = normalize_wavelengths_nm(wl)
        if np.any(np.isfinite(med)) and np.nanmax(med) > 2.0:
            print("Applied scale factor: /10000")
        med = normalize_reflectance(med)

        bad_mask = build_bad_band_mask(wl, include_narrow=True)
        invalid_mask = build_invalid_value_mask(
            med,
            min_reflectance=0.0,
            max_reflectance=1.2,
        )

        med_clean = med.copy()
        med_clean[bad_mask | invalid_mask] = np.nan

        out = {
            "id": pid,
            "lat": lat,
            "lon": lon,
            "h5_file": match.h5_path.name,
            "row": r,
            "col": c,
            "roi": ROI,
            "snap": SNAP,
            "som_avg_pct": row["som_avg_pct"],
            "carbon_pct": row["carbon_pct"],
            "nitrogen_pct": row["nitrogen_pct"],
            "veg_taxa_recorded_count": row["veg_taxa_recorded_count"],
            "habitat_type": row["habitat_type"],
        }

        out = add_spectral_features(out, wl, med_clean)
        rows.append(out)

        # Long-format full spectrum table
        for w, refl in zip(wl, med_clean):
            if np.isfinite(w) and np.isfinite(refl):
                spectra_rows.append(
                    {
                        "id": pid,
                        "wavelength_nm": float(w),
                        "reflectance": float(refl),
                        "som_avg_pct": row["som_avg_pct"],
                        "carbon_pct": row["carbon_pct"],
                        "nitrogen_pct": row["nitrogen_pct"],
                        "habitat_type": row["habitat_type"],
                    }
                )

    result = pd.DataFrame(rows)
    spectra_long = pd.DataFrame(spectra_rows)

    # --------------------------------------------------------
    # 4. Save feature table and long spectrum table
    # --------------------------------------------------------
    features_csv = TABLES / "soil_organics_hsi_features.csv"
    spectra_csv = TABLES / "soil_organics_clean_spectra_long.csv"

    result.to_csv(features_csv, index=False)
    spectra_long.to_csv(spectra_csv, index=False)

    print("\nSaved feature table:", features_csv)
    print("Saved long spectra table:", spectra_csv)

    # --------------------------------------------------------
    # 5. Correlation table: SOM/C/N vs spectral features
    # --------------------------------------------------------
    response_cols = ["som_avg_pct", "carbon_pct", "nitrogen_pct"]

    spectral_feature_cols = [
        c for c in result.columns
        if c.startswith("R_")
        or c.endswith("_mean")
        or "NDVI" in c
        or "NDWI" in c
        or "ratio" in c
        or "contrast" in c
        or "slope" in c
        or "drop" in c
    ]

    corr_rows = []

    for response in response_cols:
        for feat in spectral_feature_cols:
            corr_rows.append(
                {
                    "response": response,
                    "feature": feat,
                    "n": int(result[[response, feat]].dropna().shape[0]),
                    "pearson_r": pearson_r(result[response], result[feat]),
                    "spearman_rho": spearman_rho(result[response], result[feat]),
                }
            )

    corr_df = pd.DataFrame(corr_rows)
    corr_df["abs_pearson_r"] = corr_df["pearson_r"].abs()

    corr_df = corr_df.sort_values(
        ["response", "abs_pearson_r"],
        ascending=[True, False],
    )

    corr_csv = TABLES / "soil_property_spectral_feature_correlations.csv"
    corr_df.to_csv(corr_csv, index=False)
    print("Saved correlation table:", corr_csv)

    # --------------------------------------------------------
    # 6. PCA using full selected spectrum
    # --------------------------------------------------------
    # Make a wide table: rows = point IDs, columns = wavelength bins
    if not spectra_long.empty:
        spectra_long["wl_bin"] = spectra_long["wavelength_nm"].round(0).astype(int)

        wide = spectra_long.pivot_table(
            index="id",
            columns="wl_bin",
            values="reflectance",
            aggfunc="mean",
        )

        # Keep wavelengths that exist for most points
        min_valid = max(3, int(0.7 * len(wide)))
        wide = wide.dropna(axis=1, thresh=min_valid)

        # Fill remaining gaps with band median
        wide_filled = wide.apply(lambda col: col.fillna(col.median()), axis=0)

        if wide_filled.shape[0] >= 3 and wide_filled.shape[1] >= 3:
            n_comp = min(3, wide_filled.shape[0], wide_filled.shape[1])

            pca_model = make_pipeline(
                StandardScaler(),
                PCA(n_components=n_comp, random_state=42),
            )

            pcs = pca_model.fit_transform(wide_filled.values)
            pca = pca_model.named_steps["pca"]

            pc_cols = [f"PC{i+1}" for i in range(n_comp)]
            pc_df = pd.DataFrame(pcs, index=wide_filled.index, columns=pc_cols).reset_index()

            result = result.merge(pc_df, on="id", how="left")

            pca_csv = TABLES / "soil_organics_hsi_features_with_pca.csv"
            result.to_csv(pca_csv, index=False)
            print("Saved PCA-enhanced feature table:", pca_csv)

            # PCA scatter plot
            plt.figure(figsize=(6, 5))
            sc = plt.scatter(
                result["PC1"],
                result["PC2"],
                c=result["som_avg_pct"].astype(float),
                s=90,
            )

            for _, rr in result.iterrows():
                plt.annotate(
                    rr["id"],
                    (rr["PC1"], rr["PC2"]),
                    fontsize=8,
                    xytext=(4, 4),
                    textcoords="offset points",
                )

            plt.xlabel(f"PC1 ({pca.explained_variance_ratio_[0] * 100:.1f}% variance)")
            plt.ylabel(f"PC2 ({pca.explained_variance_ratio_[1] * 100:.1f}% variance)")
            plt.title("PCA of Cleaned Hyperspectral Soil Spectra")
            plt.colorbar(sc, label="SOM (%)")
            plt.grid(True, linestyle="--", alpha=0.3)
            plt.tight_layout()

            out_png = FIGURES / "soil_spectra_pca_som.png"
            plt.savefig(out_png, dpi=300)
            plt.show()
            print("Saved figure:", out_png)

            # Add PCs to candidate features
            spectral_feature_cols += pc_cols

    # --------------------------------------------------------
    # 7. Plot strongest SOM relationships
    # --------------------------------------------------------
    som_corr = corr_df[corr_df["response"] == "som_avg_pct"].dropna(subset=["pearson_r"])
    top_feats = som_corr.head(8)["feature"].tolist()

    for feat in top_feats:
        x = result[feat].astype(float)
        y = result["som_avg_pct"].astype(float)
        good = np.isfinite(x) & np.isfinite(y)

        if good.sum() < 3:
            continue

        plt.figure(figsize=(6, 4))
        plt.scatter(x[good], y[good], s=75)

        for _, rr in result.loc[good].iterrows():
            plt.annotate(
                rr["id"],
                (rr[feat], rr["som_avg_pct"]),
                fontsize=8,
                xytext=(4, 4),
                textcoords="offset points",
            )

        r = np.corrcoef(x[good], y[good])[0, 1]

        plt.xlabel(feat)
        plt.ylabel("SOM (%)")
        plt.title(f"SOM vs {feat}\nPearson r = {r:.2f}")
        plt.grid(True, linestyle="--", alpha=0.3)
        plt.tight_layout()

        safe_feat = feat.replace("/", "_").replace(" ", "_")
        out_png = FIGURES / f"som_vs_{safe_feat}.png"
        plt.savefig(out_png, dpi=300)
        plt.show()
        print("Saved figure:", out_png)

    # --------------------------------------------------------
    # 8. Conservative model testing
    # --------------------------------------------------------
    # With few points, these are exploratory only.
    # This is here to follow a legitimate modeling/validation process,
    # not to overclaim predictive performance.

    model_rows = []

    candidate_features_basic = [
        "R_550nm",
        "R_800nm",
        "R_1650nm",
        "R_2200nm",
        "VIS_mean",
        "NIR_mean",
        "SWIR1_mean",
        "SWIR2_mean",
        "NDVI_800_670",
        "NDWI_800_1650",
        "NIR_SWIR1_ratio",
        "VIS_to_NIR_contrast",
    ]

    candidate_features_basic = [c for c in candidate_features_basic if c in result.columns]

    # Use top few correlated features to avoid too many predictors for tiny n
    top_som_features = (
        corr_df[corr_df["response"] == "som_avg_pct"]
        .dropna(subset=["pearson_r"])
        .head(4)["feature"]
        .tolist()
    )

    feature_sets = {
        "basic_interpretable": candidate_features_basic,
        "top4_correlated": top_som_features,
    }

    # Add PCA feature set if available
    pc_cols_available = [c for c in ["PC1", "PC2", "PC3"] if c in result.columns]
    if pc_cols_available:
        feature_sets["pca"] = pc_cols_available

    for target in ["som_avg_pct", "carbon_pct", "nitrogen_pct"]:
        for set_name, feats in feature_sets.items():
            if len(feats) == 0:
                continue

            # If n is tiny, Random Forest is not very meaningful,
            # but include it as a diagnostic because Bachmann-style
            # work often uses tree-based methods at larger sample sizes.
            for model_name in ["linear", "elastic_net", "random_forest"]:
                metrics = evaluate_loo_model(result, target, feats, model_name)
                if metrics is not None:
                    metrics["feature_set"] = set_name
                    model_rows.append(metrics)

    model_df = pd.DataFrame(model_rows)

    if not model_df.empty:
        model_csv = TABLES / "soil_property_model_validation_leave_one_out.csv"
        model_df.to_csv(model_csv, index=False)
        print("Saved model validation table:", model_csv)

    print("\nDONE.")
    print("Main outputs:")
    print(" -", features_csv)
    print(" -", spectra_csv)
    print(" -", corr_csv)
    if not model_df.empty:
        print(" -", model_csv)


if __name__ == "__main__":
    main()
