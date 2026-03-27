"""
run_marmit_point.py

Simplified MARMIT-style fit for one observed bare-soil point using:
- one dry-reference bare-soil point
- one target observed point
- optional open-water comparison point

Workflow:
1. Extract ROI median spectra from H5 using lat/lon
2. Clean/mask spectra using preprocess.py
3. Intersect common cleaned wavelengths
4. Interpolate water absorption coefficients onto common wavelengths
5. Apply an additional fit-window mask over trusted wavelength regions
6. Fit effective surface-water thickness using simplified MARMIT-style model
7. Plot observed vs dry vs modeled (+ optional water spectrum)
8. Save residual plot, SSE-vs-thickness plot, and CSV summary

Important:
- dry reference should be a bare-soil / driest available point
- target should be a bare-soil point, not open water
- water point is plotted for comparison only, never fit
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from src.config import DATA_RAW, FIGURES, REFLECTANCE_PATH, WAVELENGTH_PATH
from src.io_hyperspectral import latlon_to_rowcol, read_map_info
from src.preprocess import clean_spectrum
from src.models.marmit import (
    build_fit_window_mask,
    fit_marmit_simple,
    interpolate_alpha_to_wavelengths,
)
from src.scripts.pull_spectrum_latlon import (
    MAPINFO_PATH,
    snap_to_valid_pixel,
    read_roi_median_spectrum,
)

def lookup_point_in_csv(csv_path: str, point_id: int) -> tuple[float, float]:
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        required = {"id", "lat", "lon"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"{csv_path} must contain columns: id, lat, lon")

        for row in reader:
            if int(row["id"]) == int(point_id):
                return float(row["lat"]), float(row["lon"])

    raise ValueError(f"Point id {point_id} not found in {csv_path}")

def load_alpha_csv(csv_path: str) -> tuple[np.ndarray, np.ndarray]:
    wl = []
    alpha = []
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        required = {"wavelength_nm", "alpha_water"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(
                f"{csv_path} must contain columns: wavelength_nm, alpha_water"
            )
        for row in reader:
            wl.append(float(row["wavelength_nm"]))
            alpha.append(float(row["alpha_water"]))
    return np.asarray(wl, dtype=float), np.asarray(alpha, dtype=float)


def extract_clean_roi_spectrum(
    h5_path: str,
    lat: float,
    lon: float,
    *,
    snap: int,
    roi: int,
) -> tuple[np.ndarray, np.ndarray, tuple[int, int]]:
    """
    Returns:
      wl_clean, spec_clean, (r,c)
    """
    mi = read_map_info(h5_path, MAPINFO_PATH)
    r0, c0 = latlon_to_rowcol(lat, lon, mi)

    r, c = snap_to_valid_pixel(
        h5_path,
        REFLECTANCE_PATH,
        r0,
        c0,
        radius=snap,
        band=0,
    )
    if r is None or c is None:
        raise RuntimeError(
            f"No valid pixel found within radius={snap} for lat/lon=({lat}, {lon})"
        )

    wl, spec, _bounds = read_roi_median_spectrum(
        h5_path,
        REFLECTANCE_PATH,
        WAVELENGTH_PATH,
        r,
        c,
        roi=roi,
    )

    wl = wl.astype(float)
    if float(np.nanmax(wl)) < 50.0:
        wl *= 1000.0

    spec = spec.astype(float)
    if np.nanmax(spec) > 2.0:
        spec = spec / 10000.0

    wl_clean, spec_clean, _keep = clean_spectrum(
        wl,
        spec,
        include_narrow_bad_bands=True,
        max_reflectance=1.2,
    )

    return wl_clean, spec_clean, (r, c)


def intersect_clean_spectra(
    wl1: np.ndarray,
    s1: np.ndarray,
    wl2: np.ndarray,
    s2: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Intersect two cleaned spectra by exact common wavelengths.
    """
    common = np.intersect1d(wl1, wl2)
    if common.size < 10:
        raise RuntimeError("Too few common wavelengths between spectra.")

    idx1 = np.nonzero(np.isin(wl1, common))[0]
    idx2 = np.nonzero(np.isin(wl2, common))[0]

    return common, s1[idx1], s2[idx2]


def intersect_three_clean_spectra(
    wl1: np.ndarray, s1: np.ndarray,
    wl2: np.ndarray, s2: np.ndarray,
    wl3: np.ndarray, s3: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    common = np.intersect1d(np.intersect1d(wl1, wl2), wl3)
    if common.size < 10:
        raise RuntimeError("Too few common wavelengths between the three spectra.")

    i1 = np.nonzero(np.isin(wl1, common))[0]
    i2 = np.nonzero(np.isin(wl2, common))[0]
    i3 = np.nonzero(np.isin(wl3, common))[0]

    return common, s1[i1], s2[i2], s3[i3]


def save_fit_summary_csv(
        out_csv: Path,
        *,
        dry_lat: float,
        dry_lon: float,
        target_lat: float,
        target_lon: float,
        water_lat: float | None,
        water_lon: float | None,
        dry_rc: tuple[int, int],
        tgt_rc: tuple[int, int],
        wat_rc: tuple[int, int] | None,
        roi: int,
        snap: int,
        thickness_min_um: float,
        thickness_max_um: float,
        n_grid: int,
        valid_wavelengths_used: int,
        fit_windows: str,
        thickness_um: float,
        rmse: float,
        r2: float,
        provisional_smc: float | None,
        provisional_smc_slope: float | None,
    ) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["parameter", "value"])
        writer.writerow(["dry_lat", dry_lat])
        writer.writerow(["dry_lon", dry_lon])
        writer.writerow(["target_lat", target_lat])
        writer.writerow(["target_lon", target_lon])
        writer.writerow(["water_lat", water_lat if water_lat is not None else ""])
        writer.writerow(["water_lon", water_lon if water_lon is not None else ""])
        writer.writerow(["dry_row", dry_rc[0]])
        writer.writerow(["dry_col", dry_rc[1]])
        writer.writerow(["target_row", tgt_rc[0]])
        writer.writerow(["target_col", tgt_rc[1]])
        writer.writerow(["water_row", wat_rc[0] if wat_rc is not None else ""])
        writer.writerow(["water_col", wat_rc[1] if wat_rc is not None else ""])
        writer.writerow(["roi_px", roi])
        writer.writerow(["snap_px", snap])
        writer.writerow(["thickness_min_um", thickness_min_um])
        writer.writerow(["thickness_max_um", thickness_max_um])
        writer.writerow(["n_grid", n_grid])
        writer.writerow(["fit_windows_nm", fit_windows])
        writer.writerow(["valid_wavelengths_used", valid_wavelengths_used])
        writer.writerow(["best_fit_thickness_um", thickness_um])
        writer.writerow(["rmse", rmse])
        writer.writerow(["r2", r2])
        writer.writerow(["provisional_smc", provisional_smc if provisional_smc is not None else ""])
        writer.writerow(["provisional_smc_slope", provisional_smc_slope if provisional_smc_slope is not None else ""])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--points-csv", type=str, default=None)
    ap.add_argument("--smc-dry", type=float, default=None, help="Approximate dry-point SMC for provisional calibration")
    ap.add_argument("--smc-wet", type=float, default=None, help="Approximate wet-point SMC for provisional calibration")
    ap.add_argument("--dry-id", type=int, default=None)
    ap.add_argument("--target-id", type=int, default=None)
    ap.add_argument("--water-id", type=int, default=None)
    ap.add_argument("--dry-lat", type=float, default=None)
    ap.add_argument("--dry-lon", type=float, default=None)
    ap.add_argument("--target-lat", type=float, default=None)
    ap.add_argument("--target-lon", type=float, default=None)
    ap.add_argument("--water-lat", type=float, default=None)
    ap.add_argument("--water-lon", type=float, default=None)
    ap.add_argument("--alpha-csv", type=str, required=True)
    ap.add_argument("--snap", type=int, default=40)
    ap.add_argument("--roi", type=int, default=5)
    ap.add_argument("--thickness-min-um", type=float, default=0.0)
    ap.add_argument("--thickness-max-um", type=float, default=2000.0)
    ap.add_argument("--n-grid", type=int, default=2001)
    ap.add_argument("--out", type=str, default=None)
    ap.add_argument("--use-default-fit-windows", action="store_true")
    args = ap.parse_args()

    if args.points_csv is not None:
        if args.dry_id is not None:
            args.dry_lat, args.dry_lon = lookup_point_in_csv(args.points_csv, args.dry_id)
        if args.target_id is not None:
            args.target_lat, args.target_lon = lookup_point_in_csv(args.points_csv, args.target_id)
        if args.water_id is not None:
            args.water_lat, args.water_lon = lookup_point_in_csv(args.points_csv, args.water_id)
    if args.dry_lat is None or args.dry_lon is None or args.target_lat is None or args.target_lon is None:
        raise ValueError(
            "You must provide either direct dry/target lat/lon or use --points-csv with --dry-id and --target-id."
        )

    h5_files = list(DATA_RAW.glob("*.h5"))
    if not h5_files:
        raise FileNotFoundError(f"No .h5 files found in {DATA_RAW}")
    h5 = str(h5_files[0])
    print("Using H5:", h5)

    # Extract dry and target spectra
    wl_dry, spec_dry, dry_rc = extract_clean_roi_spectrum(
        h5,
        args.dry_lat,
        args.dry_lon,
        snap=args.snap,
        roi=args.roi,
    )
    wl_tgt, spec_tgt, tgt_rc = extract_clean_roi_spectrum(
        h5,
        args.target_lat,
        args.target_lon,
        snap=args.snap,
        roi=args.roi,
    )

    # Optional water spectrum
    have_water = args.water_lat is not None and args.water_lon is not None
    wat_rc = None
    if have_water:
        wl_wat, spec_wat, wat_rc = extract_clean_roi_spectrum(
            h5,
            args.water_lat,
            args.water_lon,
            snap=args.snap,
            roi=args.roi,
        )
        wl_fit, dry_fit, tgt_fit, wat_fit = intersect_three_clean_spectra(
            wl_dry, spec_dry,
            wl_tgt, spec_tgt,
            wl_wat, spec_wat,
        )
    else:
        wl_fit, dry_fit, tgt_fit = intersect_clean_spectra(
            wl_dry, spec_dry,
            wl_tgt, spec_tgt,
        )
        wat_fit = None

    # Load and interpolate water absorption coefficients
    alpha_wl, alpha_vals = load_alpha_csv(args.alpha_csv)
    alpha_fit = interpolate_alpha_to_wavelengths(
        wavelengths_nm=wl_fit,
        alpha_wavelengths_nm=alpha_wl,
        alpha_values=alpha_vals,
    )

    # Additional fit-window mask
    if args.use_default_fit_windows:
        fit_mask = build_fit_window_mask(wl_fit, use_default_windows=True)
        fit_windows_label = "1000-1300;1550-1750;2000-2300"
    else:
        fit_mask = np.ones_like(wl_fit, dtype=bool)
        fit_windows_label = "all_cleaned_common_wavelengths"

    # Fit simplified MARMIT-style effective thickness
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

    valid_n = int(np.sum(result.valid_mask))

    print("\n=== Fit result ===")
    print(f"Dry reference row/col: {dry_rc}")
    print(f"Target row/col:        {tgt_rc}")
    if have_water:
        print(f"Water row/col:         {wat_rc}")
    print(f"Best-fit thickness (um): {result.thickness_um:.2f}")
    print(f"RMSE:                    {result.rmse:.6f}")
    print(f"R^2:                     {result.r2:.4f}")
    print(f"Valid wavelengths used:  {valid_n}")
    print(f"Fit windows:             {fit_windows_label}")


    # --------------------------------------------------------
    # Optional provisional SMC calibration from two points
    # Assumes:
    #   L_dry = 0
    #   dry point moisture = smc_dry
    #   current fitted target thickness = L_wet
    #   current wet point moisture = smc_wet
    # --------------------------------------------------------
    smc_est = None
    smc_slope = None

    if args.smc_dry is not None and args.smc_wet is not None:
        if result.thickness_um <= 0:
            print("WARNING: Best-fit thickness is <= 0, cannot build provisional SMC calibration.")
        else:
            smc_slope = (args.smc_wet - args.smc_dry) / result.thickness_um
            smc_est = args.smc_dry + smc_slope * result.thickness_um

            print("\n=== Provisional SMC calibration ===")
            print(f"Assumed dry-point SMC:   {args.smc_dry:.4f}")
            print(f"Assumed wet-point SMC:   {args.smc_wet:.4f}")
            print(f"Assumed L_dry:           0.00 um")
            print(f"Fitted L_wet:            {result.thickness_um:.2f} um")
            print(f"Linear calibration slope:{smc_slope:.8f} SMC/um")
            print(f"Estimated target SMC:    {smc_est:.4f}")

            print("\nProvisional calibration equation:")
            print(f"SMC(L) = {args.smc_dry:.6f} + ({smc_slope:.8f}) * L")

    outpath = args.out
    if outpath is None:
        outpath = FIGURES / "marmit_point_fit.png"
    else:
        outpath = Path(outpath)

    outpath.parent.mkdir(parents=True, exist_ok=True)
    stem = outpath.stem
    parent = outpath.parent

    # --------------------------------------------------------
    # Main spectral fit plot
    # Plot full cleaned/intersected spectra, but fit only selected windows
    # --------------------------------------------------------
    fig, ax = plt.subplots(figsize=(11, 6))

    # Plot full cleaned spectra
    ax.plot(
        wl_fit,
        dry_fit,
        linewidth=2.0,
        label="Dry reference (upland)",
    )
    ax.plot(
        wl_fit,
        tgt_fit,
        linewidth=2.0,
        label="Observed target (shore)",
    )

    # Plot modeled curve over the full common spectrum where it exists
    modeled_plot = np.full_like(wl_fit, np.nan, dtype=float)
    modeled_plot[result.valid_mask] = result.modeled_reflectance[result.valid_mask]
    ax.plot(
        wl_fit,
        modeled_plot,
        linestyle="--",
        linewidth=2.2,
        label=f"Simplified MARMIT-style fit (L={result.thickness_um:.1f} um)",
    )

    if wat_fit is not None:
        ax.plot(
            wl_fit,
            wat_fit,
            linewidth=2.0,
            alpha=0.85,
            label="Open water (comparison only)",
        )

    # Shade fit windows when used
    if args.use_default_fit_windows:
        for lo, hi in [(1000, 1300), (1550, 1750), (2000, 2300)]:
            ax.axvspan(lo, hi, alpha=0.10, color="gray")

    ax.set_xlabel("Wavelength (nm)", fontsize=12)
    ax.set_ylabel("Reflectance", fontsize=12)
    ax.set_title(
        "Simplified MARMIT-style fit for cleaned bare-soil spectrum\n"
        "Dry reference + observed shore spectrum + modeled wet-soil spectrum",
        fontsize=13,
    )
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.minorticks_on()
    ax.legend(loc="best")

    text = (
        f"Fit parameter L: {result.thickness_um:.2f} um\n"
        f"RMSE: {result.rmse:.5f}\n"
        f"R^2: {result.r2:.3f}\n"
        f"ROI: {args.roi}x{args.roi} px\n"
        f"Snap: {args.snap} px\n"
        f"Valid bands: {valid_n}\n"
        f"Fit windows: {fit_windows_label}"
    )

    if smc_est is not None:
        text += f"\nProvisional SMC: {smc_est:.3f}"
    ax.text(
        0.02, 0.98, text,
        transform=ax.transAxes,
        ha="left", va="top",
        fontsize=10,
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.85),
    )

    plt.tight_layout()
    plt.savefig(outpath, dpi=300)
    plt.show()
    print("Saved main fit figure:", outpath)

    # --------------------------------------------------------
    # Residual plot
    # --------------------------------------------------------
    residual_path = parent / f"{stem}_residuals.png"
    fig2, ax2 = plt.subplots(figsize=(11, 4.8))
    ax2.plot(
        result.wavelengths_nm[result.valid_mask],
        result.residuals_full[result.valid_mask],
        linewidth=1.8,
    )
    ax2.axhline(0.0, linestyle="--", linewidth=1.2)
    ax2.set_xlabel("Wavelength (nm)", fontsize=12)
    ax2.set_ylabel("Residual (Observed - Modeled)", fontsize=12)
    ax2.set_title("Simplified MARMIT-style residual spectrum", fontsize=13)
    ax2.grid(True, linestyle="--", alpha=0.3)
    ax2.minorticks_on()
    plt.tight_layout()
    plt.savefig(residual_path, dpi=300)
    plt.show()
    print("Saved residual figure:", residual_path)

    # --------------------------------------------------------
    # SSE vs thickness plot
    # --------------------------------------------------------
    sse_path = parent / f"{stem}_sse_curve.png"
    fig3, ax3 = plt.subplots(figsize=(8.2, 4.8))
    ax3.plot(result.thickness_grid_um, result.sse_grid, linewidth=2.0)
    ax3.axvline(result.thickness_um, linestyle="--", linewidth=1.5)
    ax3.set_xlabel("Thickness L (um)", fontsize=12)
    ax3.set_ylabel("SSE", fontsize=12)
    ax3.set_title("Objective function vs. effective water thickness", fontsize=13)
    ax3.grid(True, linestyle="--", alpha=0.3)
    plt.tight_layout()
    plt.savefig(sse_path, dpi=300)
    plt.show()
    print("Saved SSE curve figure:", sse_path)

    # --------------------------------------------------------
    # CSV summary
    # --------------------------------------------------------
    summary_csv = parent / f"{stem}_summary.csv"
    save_fit_summary_csv(
        summary_csv,
        dry_lat=args.dry_lat,
        dry_lon=args.dry_lon,
        target_lat=args.target_lat,
        target_lon=args.target_lon,
        water_lat=args.water_lat,
        water_lon=args.water_lon,
        dry_rc=dry_rc,
        tgt_rc=tgt_rc,
        wat_rc=wat_rc,
        roi=args.roi,
        snap=args.snap,
        thickness_min_um=args.thickness_min_um,
        thickness_max_um=args.thickness_max_um,
        n_grid=args.n_grid,
        valid_wavelengths_used=valid_n,
        fit_windows=fit_windows_label,
        thickness_um=result.thickness_um,
        rmse=result.rmse,
        r2=result.r2,
        provisional_smc=smc_est,
        provisional_smc_slope=smc_slope,
    )
    print("Saved summary CSV:", summary_csv)


if __name__ == "__main__":
    main()