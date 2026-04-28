from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.config import FIGURES
from src.models.marmit import (
    build_fit_window_mask,
    fit_marmit_simple,
    interpolate_alpha_to_wavelengths,
)
from src.scripts.run_marmit_point import (
    extract_clean_roi_spectrum,
    load_alpha_csv,
    lookup_point_in_csv,
    intersect_clean_spectra,
)
def fit_linear_calibration(
    thickness_um: np.ndarray,
    moisture: np.ndarray,
) -> tuple[float, float, float]:
    """
    Fit linear calibration:
        moisture = intercept + slope * thickness_um

    Returns
    -------
    slope, intercept, r2
    """
    x = np.asarray(thickness_um, dtype=float).ravel()
    y = np.asarray(moisture, dtype=float).ravel()

    valid = np.isfinite(x) & np.isfinite(y)
    x = x[valid]
    y = y[valid]

    if x.size < 2:
        raise ValueError("Need at least 2 valid points to fit calibration.")

    slope, intercept = np.polyfit(x, y, 1)
    y_hat = intercept + slope * x

    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else np.nan

    return float(slope), float(intercept), r2


def save_summary_txt(
    out_txt: Path,
    *,
    csv_path: str,
    dry_id: int,
    dry_lat: float,
    dry_lon: float,
    roi: int,
    snap: int,
    thickness_min_um: float,
    thickness_max_um: float,
    n_grid: int,
    fit_windows_label: str,
    slope: float,
    intercept: float,
    r2: float,
    n_points: int,
    provisional_only: bool,
    
) -> None:
    out_txt.parent.mkdir(parents=True, exist_ok=True)
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write("MARMIT calibration summary\n")
        f.write("==========================\n\n")
        f.write(f"Input CSV: {csv_path}\n")
        f.write(f"Dry reference ID: {dry_id}\n")
        f.write(f"Dry reference lat/lon: ({dry_lat}, {dry_lon})\n")
        f.write(f"ROI: {roi} px\n")
        f.write(f"Snap radius: {snap} px\n")
        f.write(f"Thickness search range: {thickness_min_um} to {thickness_max_um} um\n")
        f.write(f"Thickness grid points: {n_grid}\n")
        f.write(f"Fit windows: {fit_windows_label}\n")
        f.write(f"Number of calibration points: {n_points}\n\n")
        f.write("Linear calibration:\n")
        f.write(f"  moisture = {intercept:.8f} + ({slope:.8f}) * L_um\n")
        f.write(f"  R^2 = {r2:.6f}\n")
        f.write(f"Calibration provisional only: {provisional_only}\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=str, default="data/field/moisture_points.csv")
    ap.add_argument("--dry-id", type=int, required=True, help="ID of fixed dry reference point")
    ap.add_argument("--alpha-csv", type=str, required=True)
    ap.add_argument("--roi", type=int, default=5)
    ap.add_argument("--snap", type=int, default=40)
    ap.add_argument("--thickness-min-um", type=float, default=0.0)
    ap.add_argument("--thickness-max-um", type=float, default=2000.0)
    ap.add_argument("--n-grid", type=int, default=2001)
    ap.add_argument("--use-default-fit-windows", action="store_true")
    ap.add_argument(
        "--out_csv",
        type=str,
        default="data/processed/marmit_calibration_table.csv",
    )
    ap.add_argument(
        "--out_plot",
        type=str,
        default=None,
        help="Optional output plot path. Defaults to outputs/figures/marmit_calibration_scatter.png",
    )
    args = ap.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)

    required_cols = {"id", "lat", "lon", "moisture"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")

    alpha_wl, alpha_vals = load_alpha_csv(args.alpha_csv)

    dry_lat, dry_lon = lookup_point_in_csv(str(csv_path), args.dry_id)
    print(f"Using fixed dry reference: id={args.dry_id}, lat={dry_lat}, lon={dry_lon}")

    wl_dry, spec_dry, dry_rc = extract_clean_roi_spectrum(
        None,
        dry_lat,
        dry_lon,
        snap=args.snap,
        roi=args.roi,
    )

    rows = []

    for _, row in df.iterrows():
        point_id = int(row["id"])
        lat = float(row["lat"])
        lon = float(row["lon"])
        moisture = float(row["moisture"])

        if point_id == args.dry_id:
            rows.append(
                {
                    "id": point_id,
                    "lat": lat,
                    "lon": lon,
                    "moisture": moisture,
                    "is_dry_reference": True,
                    "dry_reference_id": args.dry_id,
                    "dry_row": dry_rc[0],
                    "dry_col": dry_rc[1],
                    "target_row": dry_rc[0],
                    "target_col": dry_rc[1],
                    "fitted_L_um": 0.0,
                    "rmse": 0.0,
                    "r2": 1.0,
                    "valid_wavelengths_used": int(len(wl_dry)),
                }
            )
            print(f"Point {point_id}: dry reference -> assigned L = 0 um")
            continue

        try:
            wl_tgt, spec_tgt, tgt_rc = extract_clean_roi_spectrum(
                None,
                lat,
                lon,
                snap=args.snap,
                roi=args.roi,
            )

            wl_fit, dry_fit, tgt_fit = intersect_clean_spectra(
                wl_dry,
                spec_dry,
                wl_tgt,
                spec_tgt,
            )

            alpha_fit = interpolate_alpha_to_wavelengths(
                wavelengths_nm=wl_fit,
                alpha_wavelengths_nm=alpha_wl,
                alpha_values=alpha_vals,
            )

            if args.use_default_fit_windows:
                fit_mask = build_fit_window_mask(wl_fit, use_default_windows=True)
                fit_windows_label = "1000-1300;1550-1750;2000-2300"
            else:
                fit_mask = np.ones_like(wl_fit, dtype=bool)
                fit_windows_label = "all_cleaned_common_wavelengths"

            result = fit_marmit_simple(
                wavelengths_nm=wl_fit,
                observed_reflectance=tgt_fit,
                dry_reflectance=dry_fit,
                alpha_water=alpha_fit,
                thickness_min_um=args.thickness_min_um,
                thickness_max_um=args.thickness_max_um,
                n_grid=args.n_grid,
                extra_mask=fit_mask,
            )

            rows.append(
                {
                    "id": point_id,
                    "lat": lat,
                    "lon": lon,
                    "moisture": moisture,
                    "is_dry_reference": False,
                    "dry_reference_id": args.dry_id,
                    "dry_row": dry_rc[0],
                    "dry_col": dry_rc[1],
                    "target_row": tgt_rc[0],
                    "target_col": tgt_rc[1],
                    "fitted_L_um": result.thickness_um,
                    "rmse": result.rmse,
                    "r2": result.r2,
                    "valid_wavelengths_used": int(np.sum(result.valid_mask)),
                }
            )

            print(
                f"Point {point_id}: moisture={moisture:.4f}, "
                f"L={result.thickness_um:.2f} um, RMSE={result.rmse:.6f}, R^2={result.r2:.4f}"
            )

        except Exception as e:
            print(f"Skipping point {point_id} due to fit failure: {e}")
            rows.append(
                {
                    "id": point_id,
                    "lat": lat,
                    "lon": lon,
                    "moisture": moisture,
                    "is_dry_reference": False,
                    "dry_reference_id": args.dry_id,
                    "dry_row": dry_rc[0],
                    "dry_col": dry_rc[1],
                    "target_row": np.nan,
                    "target_col": np.nan,
                    "fitted_L_um": np.nan,
                    "rmse": np.nan,
                    "r2": np.nan,
                    "valid_wavelengths_used": 0,
                }
            )

    out_df = pd.DataFrame(rows)

    cal_mask = np.isfinite(out_df["fitted_L_um"].values) & np.isfinite(out_df["moisture"].values)
    cal_df = out_df.loc[cal_mask].copy()

    n_cal_points = len(cal_df)

    if n_cal_points < 2:
        raise RuntimeError("Need at least 2 valid fitted points to build calibration.")

    provisional_only = n_cal_points < 3

    if len(cal_df) < 2:
        raise RuntimeError("Need at least 2 valid fitted points to build calibration.")

    slope, intercept, cal_r2 = fit_linear_calibration(
        cal_df["fitted_L_um"].values,
        cal_df["moisture"].values,
    )

    if provisional_only:
        print(
            "WARNING: Calibration is provisional only because fewer than 3 valid "
            "moisture points are available."
        )

    out_df["predicted_moisture_linear"] = intercept + slope * out_df["fitted_L_um"].values

    out_df["calibration_provisional"] = provisional_only
    out_df["calibration_n_points"] = n_cal_points
    out_df["calibration_slope"] = slope
    out_df["calibration_intercept"] = intercept
    out_df["calibration_r2"] = cal_r2

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_csv, index=False)
    print("Saved calibration table:", out_csv)

    if args.out_plot is None:
        out_plot = FIGURES / "marmit_calibration_scatter.png"
    else:
        out_plot = Path(args.out_plot)

    out_plot.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8.5, 5.8))

    ax.scatter(
        cal_df["fitted_L_um"].values,
        cal_df["moisture"].values,
        s=70,
        label="Calibration points",
    )

    x_line = np.linspace(
        float(np.nanmin(cal_df["fitted_L_um"].values)),
        float(np.nanmax(cal_df["fitted_L_um"].values)),
        200,
    )
    y_line = intercept + slope * x_line

    ax.plot(
        x_line,
        y_line,
        linewidth=2.0,
        label=f"Linear fit: moisture = {intercept:.4f} + ({slope:.6f}) L",
    )

    for _, row in cal_df.iterrows():
        ax.text(
            row["fitted_L_um"],
            row["moisture"],
            f"  {int(row['id'])}",
            fontsize=9,
            va="bottom",
        )

    ax.set_xlabel("Fitted effective water thickness L (um)", fontsize=12)
    ax.set_ylabel("Measured moisture", fontsize=12)
    ax.set_title("MARMIT calibration: measured moisture vs fitted L", fontsize=13)
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.legend(loc="best")

    status_text = "PROVISIONAL (2-point)" if provisional_only else "Linear calibration"

    text = (
        f"Dry reference ID: {args.dry_id}\n"
        f"ROI: {args.roi}x{args.roi} px\n"
        f"Snap: {args.snap} px\n"
        f"Fit windows: {fit_windows_label}\n"
        f"Calibration status: {status_text}\n"
        f"Calibration R^2: {cal_r2:.4f}\n"
        f"N points: {n_cal_points}"
    )
    ax.text(
        0.02,
        0.98,
        text,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=10,
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.85),
    )

    plt.tight_layout()
    plt.savefig(out_plot, dpi=300)
    plt.show()
    print("Saved calibration scatter plot:", out_plot)

    summary_txt = out_plot.with_name(f"{out_plot.stem}_summary.txt")
    save_summary_txt(
        summary_txt,
        csv_path=str(csv_path),
        dry_id=args.dry_id,
        dry_lat=dry_lat,
        dry_lon=dry_lon,
        roi=args.roi,
        snap=args.snap,
        thickness_min_um=args.thickness_min_um,
        thickness_max_um=args.thickness_max_um,
        n_grid=args.n_grid,
        fit_windows_label=fit_windows_label,
        slope=slope,
        intercept=intercept,
        r2=cal_r2,
        n_points=len(cal_df),
        provisional_only=provisional_only,
    )
    print("Saved calibration summary:", summary_txt)


if __name__ == "__main__":
    main()
