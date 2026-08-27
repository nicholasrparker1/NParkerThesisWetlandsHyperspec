from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from src.config import DATA_PROCESSED, FIGURES
from src.models.marmit import (
    build_fit_window_mask,
    fit_marmit_mixed,
    interpolate_alpha_to_wavelengths,
    model_wet_reflectance_mixed,
)
from src.models.spectral_wetness import (
    extract_spectral_wetness_features,
    features_to_dict,
)
from src.spectral_plotting import (
    add_bad_band_shading,
    add_spectral_region_bars,
    mask_spectrum_for_plot,
)
from src.spectral_workflow import (
    extract_clean_roi_spectrum,
    intersect_clean_spectra,
    load_alpha_csv,
    lookup_point_in_csv,
)
from src.workflow import load_point_csv


BASELINE_FEATURES = [
    "nd_860_1640",
    "nd_1240_1640",
    "swir_darkness",
    "continuum_depth_2200",
]


def _finite_zscore(values: np.ndarray) -> np.ndarray:
    out = np.full_like(values, np.nan, dtype=float)
    finite = np.isfinite(values)
    if np.sum(finite) < 2:
        return out
    mu = float(np.nanmean(values[finite]))
    sd = float(np.nanstd(values[finite]))
    if sd <= 0.0:
        out[finite] = 0.0
    else:
        out[finite] = (values[finite] - mu) / sd
    return out


def save_method_scatter(outpath: Path, rows: list[dict[str, object]]) -> None:
    usable = [
        row for row in rows
        if np.isfinite(row.get("baseline_relative_wetness", np.nan))
        and np.isfinite(row.get("marmit_phi_um", np.nan))
    ]
    if not usable:
        return

    x = np.asarray([float(row["baseline_relative_wetness"]) for row in usable])
    y = np.asarray([float(row["marmit_phi_um"]) for row in usable])

    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    ax.scatter(x, y, s=72, color="#2f6f73")
    for row in usable:
        ax.text(
            float(row["baseline_relative_wetness"]),
            float(row["marmit_phi_um"]),
            f"  {row['id']}",
            fontsize=9,
            va="center",
        )

    ax.axvline(0.0, color="#999999", linewidth=1.0, linestyle="--")
    ax.set_xlabel("Baseline relative wetness score (standardized)")
    ax.set_ylabel("MARMIT-style phi = L x epsilon (um)")
    ax.set_title("Aerial wetness methods comparison")
    ax.grid(True, linestyle="--", alpha=0.28)
    fig.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=300)
    plt.close(fig)


def save_fit_plot(
    outpath: Path,
    *,
    target_id: str,
    dry_id: int,
    wavelengths_nm: np.ndarray,
    dry_reflectance: np.ndarray,
    target_reflectance: np.ndarray,
    modeled_reflectance: np.ndarray,
    fit_mask: np.ndarray,
    L: float,
    epsilon: float,
    phi: float,
    rmse: float,
    r2: float,
) -> None:
    dry_plot = mask_spectrum_for_plot(wavelengths_nm, dry_reflectance)
    target_plot = mask_spectrum_for_plot(wavelengths_nm, target_reflectance)
    model_plot = mask_spectrum_for_plot(wavelengths_nm, modeled_reflectance)

    fig, ax = plt.subplots(figsize=(11, 6.35))
    add_bad_band_shading(ax)
    ax.plot(wavelengths_nm, dry_plot, color="#d9a400", linewidth=2.0, label=f"Dry reference (ID {dry_id})")
    ax.plot(wavelengths_nm, target_plot, color="#238b45", linewidth=2.0, label=f"Target (ID {target_id})")
    ax.plot(
        wavelengths_nm,
        model_plot,
        color="black",
        linestyle="--",
        linewidth=2.2,
        label="Mixed MARMIT-style model",
    )

    finite_target = target_plot[np.isfinite(target_plot)]
    if np.any(fit_mask) and finite_target.size:
        ax.scatter(
            wavelengths_nm[fit_mask],
            np.full(int(np.sum(fit_mask)), float(np.nanmin(finite_target)) * 0.96),
            marker="|",
            s=16,
            color="#333333",
            alpha=0.30,
            label="Wavelengths used in fit",
        )

    text = (
        f"L = {L:.0f} um\n"
        f"epsilon = {epsilon:.2f}\n"
        f"phi = {phi:.0f} um\n"
        f"RMSE = {rmse:.4f}\n"
        f"R2 = {r2:.3f}"
    )
    ax.text(
        0.015,
        0.97,
        text,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=10,
        bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="#999999", alpha=0.92),
    )

    ax.set_xlabel("Wavelength (nm)", labelpad=13)
    ax.set_ylabel("Reflectance")
    ax.set_title("Improved MARMIT-style fit: dry soil with partial water-layer coverage")
    ax.grid(True, linestyle="--", alpha=0.28)
    ax.legend(loc="upper right")
    ax.minorticks_on()
    add_spectral_region_bars(ax)
    fig.subplots_adjust(left=0.08, right=0.985, top=0.90, bottom=0.27)
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=300)
    plt.close(fig)


def write_csv(outpath: Path, rows: list[dict[str, object]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)

    outpath.parent.mkdir(parents=True, exist_ok=True)
    with open(outpath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Compare no-calibration aerial wetness proxies: simple SWIR features "
            "and an improved MARMIT-style L/epsilon/phi retrieval."
        )
    )
    ap.add_argument("--points", required=True, help="CSV with columns id,lat,lon")
    ap.add_argument("--dry-id", type=int, required=True, help="Bare/dry reference point ID")
    ap.add_argument("--alpha-csv", default="data/processed/water_absorption_coeff_segelstein_400_2500nm_per_um.csv")
    ap.add_argument("--roi", type=int, default=3)
    ap.add_argument("--snap", type=int, default=5)
    ap.add_argument("--thickness-min-um", type=float, default=0.0)
    ap.add_argument("--thickness-max-um", type=float, default=2000.0)
    ap.add_argument("--n-grid", type=int, default=2001)
    ap.add_argument("--plot-target-id", default=None, help="Optional point ID for a detailed MARMIT fit figure")
    ap.add_argument("--include-ids", default=None, help="Optional comma-separated point IDs to process")
    ap.add_argument("--out-csv", default=None)
    ap.add_argument("--out-scatter", default=None)
    ap.add_argument("--out-fit", default=None)
    args = ap.parse_args()

    points = load_point_csv(args.points)
    if args.include_ids is not None:
        include_ids = {part.strip() for part in args.include_ids.split(",") if part.strip()}
        points = [point for point in points if str(point.id) in include_ids]
        if not points:
            raise ValueError("--include-ids did not match any rows in --points")
    dry_lat, dry_lon = lookup_point_in_csv(args.points, args.dry_id)
    wl_dry, spec_dry, dry_rc = extract_clean_roi_spectrum(
        None,
        dry_lat,
        dry_lon,
        snap=args.snap,
        roi=args.roi,
    )

    alpha_wl, alpha_vals = load_alpha_csv(args.alpha_csv)

    rows: list[dict[str, object]] = []
    fit_context_for_plot = None
    plot_target_id = str(args.plot_target_id) if args.plot_target_id is not None else None

    for point in points:
        print(f"Processing point {point.id}...")
        wl_tgt, spec_tgt, tgt_rc = extract_clean_roi_spectrum(
            None,
            point.lat,
            point.lon,
            snap=args.snap,
            roi=args.roi,
        )

        features = extract_spectral_wetness_features(wl_tgt, spec_tgt)
        row: dict[str, object] = {
            "id": point.id,
            "lat": point.lat,
            "lon": point.lon,
            "dry_reference_id": args.dry_id,
            "roi_px": args.roi,
            "snap_px": args.snap,
            "target_row": tgt_rc[0],
            "target_col": tgt_rc[1],
            "dry_row": dry_rc[0],
            "dry_col": dry_rc[1],
            "is_dry_reference": str(point.id) == str(args.dry_id),
        }
        row.update(features_to_dict(features))

        if str(point.id) == str(args.dry_id):
            row.update(
                {
                    "marmit_L_um": 0.0,
                    "marmit_epsilon": 0.0,
                    "marmit_phi_um": 0.0,
                    "marmit_rmse": 0.0,
                    "marmit_r2": 1.0,
                    "marmit_valid_wavelengths": 0,
                    "marmit_hit_L_lower_bound": True,
                    "marmit_hit_L_upper_bound": False,
                    "marmit_fit_warning": "",
                }
            )
            rows.append(row)
            continue

        try:
            wl_fit, dry_fit, tgt_fit = intersect_clean_spectra(
                wl_dry,
                spec_dry,
                wl_tgt,
                spec_tgt,
            )
            alpha_fit = interpolate_alpha_to_wavelengths(wl_fit, alpha_wl, alpha_vals)
            fit_mask = build_fit_window_mask(wl_fit, use_default_windows=True)
            result = fit_marmit_mixed(
                wl_fit,
                tgt_fit,
                dry_fit,
                alpha_fit,
                thickness_min_um=args.thickness_min_um,
                thickness_max_um=args.thickness_max_um,
                n_grid=args.n_grid,
                extra_mask=fit_mask,
            )

            row.update(
                {
                    "marmit_L_um": result.thickness_um,
                    "marmit_epsilon": result.wet_fraction,
                    "marmit_phi_um": result.equivalent_water_thickness_um,
                    "marmit_rmse": result.rmse,
                    "marmit_r2": result.r2,
                    "marmit_valid_wavelengths": int(np.sum(result.valid_mask)),
                    "marmit_hit_L_lower_bound": np.isclose(result.thickness_um, args.thickness_min_um),
                    "marmit_hit_L_upper_bound": np.isclose(result.thickness_um, args.thickness_max_um),
                    "marmit_fit_warning": "",
                }
            )

            if plot_target_id is not None and str(point.id) == plot_target_id:
                model_full = model_wet_reflectance_mixed(
                    dry_fit,
                    alpha_fit,
                    result.thickness_um,
                    result.wet_fraction,
                )
                fit_context_for_plot = {
                    "target_id": point.id,
                    "wavelengths_nm": wl_fit,
                    "dry_reflectance": dry_fit,
                    "target_reflectance": tgt_fit,
                    "modeled_reflectance": model_full,
                    "fit_mask": result.valid_mask,
                    "L": result.thickness_um,
                    "epsilon": result.wet_fraction,
                    "phi": result.equivalent_water_thickness_um,
                    "rmse": result.rmse,
                    "r2": result.r2,
                }

        except Exception as exc:
            row.update(
                {
                    "marmit_L_um": np.nan,
                    "marmit_epsilon": np.nan,
                    "marmit_phi_um": np.nan,
                    "marmit_rmse": np.nan,
                    "marmit_r2": np.nan,
                    "marmit_valid_wavelengths": 0,
                    "marmit_hit_L_lower_bound": False,
                    "marmit_hit_L_upper_bound": False,
                    "marmit_fit_warning": str(exc),
                }
            )

        rows.append(row)

    for feature_name in BASELINE_FEATURES:
        values = np.asarray([float(row.get(feature_name, np.nan)) for row in rows], dtype=float)
        z = _finite_zscore(values)
        for row, value in zip(rows, z):
            row[f"{feature_name}_z"] = float(value) if np.isfinite(value) else np.nan

    z_cols = [f"{name}_z" for name in BASELINE_FEATURES]
    for row in rows:
        vals = np.asarray([float(row.get(col, np.nan)) for col in z_cols], dtype=float)
        row["baseline_relative_wetness"] = float(np.nanmean(vals)) if np.any(np.isfinite(vals)) else np.nan

    out_csv = Path(args.out_csv) if args.out_csv else DATA_PROCESSED / "aerial_wetness_method_comparison.csv"
    write_csv(out_csv, rows)
    print("Saved comparison table:", out_csv)

    out_scatter = Path(args.out_scatter) if args.out_scatter else FIGURES / "aerial_wetness_method_comparison.png"
    save_method_scatter(out_scatter, rows)
    print("Saved method comparison figure:", out_scatter)

    if fit_context_for_plot is not None:
        out_fit = Path(args.out_fit) if args.out_fit else FIGURES / f"marmit_mixed_fit_point_{plot_target_id}.png"
        save_fit_plot(out_fit, dry_id=args.dry_id, **fit_context_for_plot)
        print("Saved detailed MARMIT-style fit figure:", out_fit)


if __name__ == "__main__":
    main()
