from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator, ScalarFormatter
import numpy as np
import pandas as pd

from src.config import FIGURES, TABLES
from src.spectral_plotting import add_bad_band_shading


DEFAULT_IN = Path("data/processed/soil_spectral_table.csv")
DEFAULT_CORR_OUT = TABLES / "soil_spectral_correlations.csv"
DEFAULT_SUMMARY_OUT = TABLES / "soil_spectral_correlation_top_bands.csv"
DEFAULT_CURVE_FIG = FIGURES / "soil_spectral_correlations.png"
DEFAULT_SCATTER_FIG = FIGURES / "soil_spectral_top_band_scatterplots.png"

TARGET_COLUMNS = ["som_avg_pct", "carbon_pct", "nitrogen_pct"]
TARGET_LABELS = {
    "som_avg_pct": "Soil Organic Matter Average %",
    "carbon_pct": "Carbon %",
    "nitrogen_pct": "Nitrogen %",
}

# Match the conservative screening mask used during table construction.
# This keeps the correlation search away from common atmospheric/water regions
# and the unstable shoulder just below 1350 nm.
EXCLUDED_WINDOWS_NM = [
    (920.0, 960.0),
    (1110.0, 1145.0),
    (1300.0, 1450.0),
    (1800.0, 1950.0),
    (2400.0, np.inf),
]


def _parse_wavelength_nm(refl_col: str) -> float:
    """
    Convert names like refl_381_7 back to 381.7 nm.
    """
    match = re.fullmatch(r"refl_(\d+)_(\d+)", refl_col)
    if not match:
        raise ValueError(f"Could not parse wavelength from reflectance column: {refl_col}")
    return float(f"{match.group(1)}.{match.group(2)}")


def _find_reflectance_columns(df: pd.DataFrame) -> list[str]:
    refl_cols = [col for col in df.columns if re.fullmatch(r"refl_\d+_\d+", str(col))]
    return sorted(refl_cols, key=_parse_wavelength_nm)


def _is_excluded_wavelength(wavelength_nm: float) -> bool:
    return any(lo <= wavelength_nm <= hi for lo, hi in EXCLUDED_WINDOWS_NM)


def _filter_to_literature_screening_bands(refl_cols: list[str]) -> list[str]:
    return [
        col
        for col in refl_cols
        if not _is_excluded_wavelength(_parse_wavelength_nm(col))
    ]


def _sample_id_column(df: pd.DataFrame) -> str | None:
    for col in ["sampling_point_id", "sample_id", "id", "soil_core_id"]:
        if col in df.columns:
            return col
    return None


def _target_label(target: str) -> str:
    return TARGET_LABELS.get(target, target.replace("_", " ").title())


def _pearson_r(x: pd.Series, y: pd.Series) -> float:
    good = np.isfinite(x.astype(float)) & np.isfinite(y.astype(float))
    if int(good.sum()) < 3:
        return np.nan
    return float(np.corrcoef(x[good], y[good])[0, 1])


def _spearman_rho(x: pd.Series, y: pd.Series) -> float:
    good = np.isfinite(x.astype(float)) & np.isfinite(y.astype(float))
    if int(good.sum()) < 3:
        return np.nan
    xr = pd.Series(x[good]).rank()
    yr = pd.Series(y[good]).rank()
    return float(xr.corr(yr))


def _make_correlation_table(df: pd.DataFrame, refl_cols: list[str], targets: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for target in targets:
        y = pd.to_numeric(df[target], errors="coerce")
        for col in refl_cols:
            x = pd.to_numeric(df[col], errors="coerce")
            n = int((np.isfinite(x) & np.isfinite(y)).sum())
            rows.append(
                {
                    "target": target,
                    "wavelength_nm": _parse_wavelength_nm(col),
                    "refl_col": col,
                    "n": n,
                    "pearson_r": _pearson_r(x, y),
                    "spearman_rho": _spearman_rho(x, y),
                }
            )

    corr = pd.DataFrame(rows)
    corr["abs_pearson_r"] = corr["pearson_r"].abs()
    corr["abs_spearman_rho"] = corr["spearman_rho"].abs()
    return corr.sort_values(["target", "wavelength_nm"]).reset_index(drop=True)


def _plot_correlation_curves(corr: pd.DataFrame, out_png: Path) -> None:
    fig, axes = plt.subplots(len(TARGET_COLUMNS), 1, figsize=(11, 9), sharex=True)
    if len(TARGET_COLUMNS) == 1:
        axes = [axes]

    colors = {
        "som_avg_pct": "#7a4f20",
        "carbon_pct": "#2c6e49",
        "nitrogen_pct": "#355c9a",
    }

    for ax, target in zip(axes, TARGET_COLUMNS):
        sub = corr[corr["target"] == target].sort_values("wavelength_nm")
        ax.plot(
            sub["wavelength_nm"],
            sub["pearson_r"],
            color=colors.get(target, "black"),
            linewidth=2.0,
            label="Pearson r",
        )
        ax.plot(
            sub["wavelength_nm"],
            sub["spearman_rho"],
            color=colors.get(target, "black"),
            linewidth=1.3,
            linestyle="--",
            alpha=0.75,
            label="Spearman rho",
        )
        ax.axhline(0, color="0.25", linewidth=0.8)
        add_bad_band_shading(
            ax,
            windows=EXCLUDED_WINDOWS_NM,
            color="0.7",
            alpha=0.13,
        )
        ax.set_ylabel(_target_label(target))
        ax.set_ylim(-1.05, 1.05)
        ax.grid(True, linestyle="--", alpha=0.3)
        ax.legend(loc="upper right")

    axes[-1].set_xlabel("Wavelength (nm)")
    fig.suptitle("Soil Chemistry vs NEON Reflectance Correlations", fontsize=14)
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=300)
    plt.close(fig)


def _plot_top_scatterplots(df: pd.DataFrame, corr: pd.DataFrame, out_png: Path, top_n: int) -> pd.DataFrame:
    top_rows = []
    for target in TARGET_COLUMNS:
        sub = corr[corr["target"] == target].dropna(subset=["pearson_r"])
        sub = sub.sort_values("abs_pearson_r", ascending=False).head(top_n)
        top_rows.append(sub)

    top = pd.concat(top_rows, ignore_index=True) if top_rows else pd.DataFrame()
    if top.empty:
        return top

    nrows = len(TARGET_COLUMNS)
    ncols = top_n
    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(5.2 * ncols, 4.2 * nrows),
        squeeze=False,
        constrained_layout=True,
    )
    id_col = _sample_id_column(df)

    for row_idx, target in enumerate(TARGET_COLUMNS):
        sub = top[top["target"] == target].reset_index(drop=True)
        for col_idx in range(ncols):
            ax = axes[row_idx][col_idx]
            if col_idx >= len(sub):
                ax.axis("off")
                continue

            info = sub.loc[col_idx]
            refl_col = info["refl_col"]
            x = pd.to_numeric(df[refl_col], errors="coerce")
            y = pd.to_numeric(df[target], errors="coerce")
            good = np.isfinite(x) & np.isfinite(y)

            ax.scatter(x[good], y[good], s=45, color="#284b63", alpha=0.85)
            if int(good.sum()) >= 3:
                slope, intercept = np.polyfit(x[good], y[good], 1)
                xx = np.linspace(float(x[good].min()), float(x[good].max()), 100)
                ax.plot(xx, slope * xx + intercept, color="#d1495b", linewidth=1.5)

            if id_col is not None and int(good.sum()) <= 40:
                for _, rr in df.loc[good].iterrows():
                    ax.annotate(
                        str(rr[id_col]),
                        (rr[refl_col], rr[target]),
                        fontsize=6,
                        xytext=(3, 3),
                        textcoords="offset points",
                        alpha=0.75,
                    )

            ax.set_title(
                f"{_target_label(target)}\n{info['wavelength_nm']:.1f} nm, r={info['pearson_r']:.2f}",
                fontsize=11,
            )
            ax.set_xlabel(f"Reflectance at {info['wavelength_nm']:.1f} nm")
            ax.set_ylabel(_target_label(target))
            ax.xaxis.set_major_locator(MaxNLocator(nbins=4, prune=None))
            formatter = ScalarFormatter(useOffset=False)
            formatter.set_scientific(False)
            ax.xaxis.set_major_formatter(formatter)
            ax.tick_params(axis="x", labelsize=8)
            ax.tick_params(axis="y", labelsize=9)
            ax.grid(True, linestyle="--", alpha=0.25)

    fig.suptitle("Top Reflectance Bands by Absolute Pearson Correlation", fontsize=16)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=300)
    plt.close(fig)
    return top


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Correlate soil chemistry columns with NEON hyperspectral reflectance bands."
    )
    ap.add_argument("--table", default=str(DEFAULT_IN), help="Input soil spectral table CSV")
    ap.add_argument("--corr-out", default=str(DEFAULT_CORR_OUT), help="Full correlation table CSV")
    ap.add_argument("--top-out", default=str(DEFAULT_SUMMARY_OUT), help="Top-band summary CSV")
    ap.add_argument("--curve-fig", default=str(DEFAULT_CURVE_FIG), help="Correlation curve PNG")
    ap.add_argument("--scatter-fig", default=str(DEFAULT_SCATTER_FIG), help="Top-band scatterplot PNG")
    ap.add_argument("--top-n", type=int, default=3, help="Top bands per target for scatterplots")
    args = ap.parse_args()

    in_path = Path(args.table)
    if not in_path.exists():
        raise FileNotFoundError(f"Input table not found: {in_path}")

    df = pd.read_csv(in_path)
    all_refl_cols = _find_reflectance_columns(df)
    if not all_refl_cols:
        raise ValueError(f"No reflectance columns named like refl_381_7 were found in {in_path}")
    refl_cols = _filter_to_literature_screening_bands(all_refl_cols)
    if not refl_cols:
        raise ValueError("No reflectance columns remain after conservative wavelength masking.")

    missing_targets = [col for col in TARGET_COLUMNS if col not in df.columns]
    if missing_targets:
        raise ValueError(f"Input table is missing target columns: {missing_targets}")

    print(f"Input table: {in_path}")
    print(f"Rows: {len(df)}")
    print(f"Reflectance bands in table: {len(all_refl_cols)}")
    print(f"Reflectance bands used after conservative masking: {len(refl_cols)}")
    print(f"Wavelength range used: {_parse_wavelength_nm(refl_cols[0]):.1f} to {_parse_wavelength_nm(refl_cols[-1]):.1f} nm")
    print("Excluded wavelength windows:", EXCLUDED_WINDOWS_NM)

    corr = _make_correlation_table(df, refl_cols, TARGET_COLUMNS)

    corr_out = Path(args.corr_out)
    corr_out.parent.mkdir(parents=True, exist_ok=True)
    corr.to_csv(corr_out, index=False)

    _plot_correlation_curves(corr, Path(args.curve_fig))
    top = _plot_top_scatterplots(df, corr, Path(args.scatter_fig), args.top_n)

    top_out = Path(args.top_out)
    top_out.parent.mkdir(parents=True, exist_ok=True)
    top.sort_values(["target", "abs_pearson_r"], ascending=[True, False]).to_csv(top_out, index=False)

    print("\nTop bands by target:")
    for target in TARGET_COLUMNS:
        sub = top[top["target"] == target].sort_values("abs_pearson_r", ascending=False)
        print(f"\n{target}:")
        for _, row in sub.iterrows():
            print(
                f" - {row['wavelength_nm']:.1f} nm ({row['refl_col']}): "
                f"Pearson r={row['pearson_r']:.3f}, Spearman rho={row['spearman_rho']:.3f}, n={int(row['n'])}"
            )

    print("\nSaved:")
    print(f" - {corr_out}")
    print(f" - {top_out}")
    print(f" - {Path(args.curve_fig)}")
    print(f" - {Path(args.scatter_fig)}")


if __name__ == "__main__":
    main()
