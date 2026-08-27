from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from src.preprocess import spectrum_for_plot


SPECTRAL_REGION_BARS = [
    ("VIS\n400-700", 400.0, 700.0),
    ("NIR\n700-1300", 700.0, 1300.0),
    ("SWIR-I\n1450-1800", 1450.0, 1800.0),
    ("SWIR-II\n1950-2400", 1950.0, 2400.0),
]


@dataclass(frozen=True)
class ReflectancePlotSeries:
    label: str
    wavelengths_nm: np.ndarray
    reflectance: np.ndarray
    color: object | None = None
    p_low: np.ndarray | None = None
    p_high: np.ndarray | None = None


def mask_spectrum_for_plot(
    wavelengths_nm: np.ndarray,
    spectrum: np.ndarray,
    *,
    include_narrow_bad_bands: bool = True,
    min_reflectance: float = 0.0,
    max_reflectance: float = 1.2,
) -> np.ndarray:
    """Return spectrum with invalid and masked wavelength bands set to NaN."""
    _wl, spec_plot, _masked = spectrum_for_plot(
        wavelengths_nm,
        spectrum,
        include_narrow_bad_bands=include_narrow_bad_bands,
        min_reflectance=min_reflectance,
        max_reflectance=max_reflectance,
    )
    return spec_plot


def plot_reflectance_spectra(
    series: list[ReflectancePlotSeries],
    *,
    outpath: str | Path,
    title: str = "Reflectance vs. Wavelength",
    footer: str | None = None,
    show: bool = False,
    figsize: tuple[float, float] = (11, 6),
) -> None:
    """Save the shared publication-style reflectance plot used by all workflows."""
    if not series:
        raise ValueError("At least one spectrum is required to plot")

    fig, ax = plt.subplots(figsize=figsize)
    global_max = 0.0
    plotted = 0

    for item in series:
        wl = np.asarray(item.wavelengths_nm, dtype=float)
        refl = np.asarray(item.reflectance, dtype=float)
        good = np.isfinite(wl) & np.isfinite(refl)
        if not np.any(good):
            continue

        kwargs = {"linewidth": 2.2, "label": item.label}
        if item.color is not None:
            kwargs["color"] = item.color
        (line,) = ax.plot(wl, refl, **kwargs)
        color = item.color if item.color is not None else line.get_color()
        plotted += 1

        if item.p_low is not None and item.p_high is not None:
            p_low = np.asarray(item.p_low, dtype=float)
            p_high = np.asarray(item.p_high, dtype=float)
            if np.any(np.isfinite(p_low)) and np.any(np.isfinite(p_high)):
                ax.fill_between(wl, p_low, p_high, color=color, alpha=0.12)

        local_max = float(np.nanpercentile(refl[good], 98))
        if np.isfinite(local_max):
            global_max = max(global_max, local_max)

    if plotted == 0:
        raise RuntimeError("No valid spectra plotted. Check points, tiles, snap radius, or ROI location.")

    add_bad_band_shading(ax, alpha=0.12)
    ax.set_xlabel("Wavelength (nm)", fontsize=12, labelpad=12)
    ax.set_ylabel("Reflectance", fontsize=12)
    ax.set_title(title, fontsize=13)
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.minorticks_on()
    ax.legend(loc="upper right")
    ax.set_ylim(0, float(global_max * 1.15) if global_max > 0 else 0.2)

    add_spectral_region_bars(ax, y_line=-0.19, y_text=-0.24)

    plt.tight_layout()
    plt.subplots_adjust(bottom=0.31)
    if footer:
        fig.text(
            0.5,
            0.02,
            footer,
            ha="center",
            va="bottom",
            fontsize=9,
            color="#4b5563",
        )

    outpath = Path(outpath)
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outpath, dpi=300)
    if show:
        plt.show()
    else:
        plt.close(fig)


def add_bad_band_shading(
    ax: plt.Axes,
    *,
    windows: list[tuple[float, float]] | None = None,
    include_narrow_bad_bands: bool = True,
    color: str = "#8fbcd4",
    alpha: float = 0.16,
) -> None:
    if windows is None:
        windows = [(1340.0, 1450.0), (1800.0, 1950.0), (2400.0, 2500.0)]
        if include_narrow_bad_bands:
            windows = [(920.0, 960.0), (1110.0, 1145.0), *windows]

    for lo, hi in windows:
        if np.isfinite(hi):
            ax.axvspan(lo, hi, color=color, alpha=alpha, linewidth=0)


def add_spectral_region_bars(
    ax: plt.Axes,
    *,
    y_line: float = -0.18,
    y_text: float = -0.225,
) -> None:
    """Add VIS/NIR/SWIR reference brackets below the wavelength axis."""
    xmin, xmax = ax.get_xlim()

    for label, x0, x1 in SPECTRAL_REGION_BARS:
        xa = max(x0, xmin)
        xb = min(x1, xmax)
        if xb <= xa:
            continue

        ax.plot(
            [xa, xb],
            [y_line, y_line],
            transform=ax.get_xaxis_transform(),
            color="black",
            linewidth=1.0,
            clip_on=False,
        )
        ax.plot(
            [xa, xa],
            [y_line - 0.015, y_line + 0.015],
            transform=ax.get_xaxis_transform(),
            color="black",
            linewidth=1.0,
            clip_on=False,
        )
        ax.plot(
            [xb, xb],
            [y_line - 0.015, y_line + 0.015],
            transform=ax.get_xaxis_transform(),
            color="black",
            linewidth=1.0,
            clip_on=False,
        )
        ax.text(
            (xa + xb) / 2,
            y_text,
            label,
            transform=ax.get_xaxis_transform(),
            ha="center",
            va="top",
            fontsize=10,
            fontweight="bold",
            clip_on=False,
        )
