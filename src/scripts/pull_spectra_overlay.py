from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

import numpy as np

from src.config import FIGURES
from src.io_hyperspectral import read_roi_stats_spectrum, snap_to_valid_pixel
from src.preprocess import build_bad_band_mask, build_invalid_value_mask
from src.spectral_plotting import ReflectancePlotSeries, plot_reflectance_spectra
from src.workflow import (
    find_h5_files,
    find_h5_for_point,
    load_point_csv,
    normalize_reflectance,
    normalize_wavelengths_nm,
    rainbow_colors,
)


def _rgba_to_css(color: tuple[float, float, float, float] | np.ndarray) -> str:
    rgba = np.asarray(color, dtype=float)
    r, g, b = [int(round(float(channel) * 255)) for channel in rgba[:3]]
    a = float(rgba[3]) if rgba.size > 3 else 1.0
    return f"rgba({r},{g},{b},{a:.3f})"


def _finite_float_list(values: np.ndarray) -> list[float | None]:
    out: list[float | None] = []
    for value in np.asarray(values, dtype=float):
        out.append(float(value) if np.isfinite(value) else None)
    return out


def _figure_title() -> str:
    return "Reflectance vs. Wavelength"


def _roi_size_text(roi: int) -> str:
    return f"ROI size: {roi} m x {roi} m"


def _source_note(points_path: Path, spectra: list[dict[str, object]] | None = None) -> str:
    site = None
    if spectra:
        h5_names = sorted({str(spectrum.get("h5", "")) for spectrum in spectra if spectrum.get("h5")})
        if len(h5_names) == 1:
            parts = h5_names[0].split("_")
            if len(parts) >= 3 and parts[0] == "NEON":
                site = parts[2]

    source = f"NEON {site} airborne hyperspectral reflectance" if site else "NEON airborne hyperspectral reflectance"
    return f"Data source: {source}; points: {points_path.name}."


def _write_interactive_html(
    outpath: Path,
    points_path: Path,
    spectra: list[dict[str, object]],
    roi: int,
    snap: int,
    p_lo: float,
    p_hi: float,
) -> None:
    payload = {
        "points_file": points_path.name,
        "roi": roi,
        "snap": snap,
        "p_lo": p_lo,
        "p_hi": p_hi,
        "spectra": spectra,
    }
    data_json = json.dumps(payload, allow_nan=False)
    title = _figure_title()
    escaped_title = html.escape(title)

    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <style>
    body {{
      font-family: Arial, sans-serif;
      margin: 24px;
      color: #1f2933;
      background: #ffffff;
    }}
    h1 {{
      font-size: 22px;
      margin: 0 0 4px;
    }}
    .meta {{
      margin: 0 0 16px;
      color: #52606d;
      font-size: 14px;
    }}
    #wrap {{
      position: relative;
      max-width: 1180px;
    }}
    canvas {{
      width: 100%;
      height: 660px;
      border: 1px solid #d9e2ec;
      border-radius: 6px;
      background: #ffffff;
    }}
    #tooltip {{
      position: absolute;
      display: none;
      pointer-events: none;
      background: rgba(17, 24, 39, 0.94);
      color: white;
      border-radius: 5px;
      padding: 8px 10px;
      font-size: 12px;
      line-height: 1.35;
      white-space: nowrap;
      box-shadow: 0 6px 18px rgba(0, 0, 0, 0.22);
    }}
  </style>
</head>
<body>
  <h1>{escaped_title}</h1>
  <p class="meta">{html.escape(_source_note(points_path, spectra))} {html.escape(_roi_size_text(roi))} | Snap={snap} | Percentile band={p_lo:g}-{p_hi:g}. Hover near a curve to inspect wavelength and reflectance.</p>
  <div id="wrap">
    <canvas id="plot"></canvas>
    <div id="tooltip"></div>
  </div>
  <script>
    const payload = {data_json};
    const canvas = document.getElementById('plot');
    const tooltip = document.getElementById('tooltip');
    const ctx = canvas.getContext('2d');
    const margin = {{left: 78, right: 28, top: 28, bottom: 72}};
    const badWindows = [[920, 960], [1110, 1145], [1340, 1450], [1800, 1950]];

    function resize() {{
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      canvas.width = Math.round(rect.width * dpr);
      canvas.height = Math.round(rect.height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      draw();
    }}

    function allFinite(values) {{
      const out = [];
      for (const spectrum of payload.spectra) {{
        for (const v of spectrum[values]) {{
          if (Number.isFinite(v)) out.push(v);
        }}
      }}
      return out;
    }}

    function extent(values, fallbackMin, fallbackMax) {{
      if (!values.length) return [fallbackMin, fallbackMax];
      return [Math.min(...values), Math.max(...values)];
    }}

    const xExtent = extent(allFinite('wavelength_nm'), 350, 2500);
    const yExtentRaw = extent(allFinite('reflectance'), 0, 0.2);
    const yExtent = [0, Math.max(0.02, yExtentRaw[1] * 1.12)];

    function plotRect() {{
      const rect = canvas.getBoundingClientRect();
      return {{
        x0: margin.left,
        y0: margin.top,
        x1: rect.width - margin.right,
        y1: rect.height - margin.bottom,
        w: rect.width - margin.left - margin.right,
        h: rect.height - margin.top - margin.bottom,
      }};
    }}

    function xScale(x) {{
      const r = plotRect();
      return r.x0 + (x - xExtent[0]) / (xExtent[1] - xExtent[0]) * r.w;
    }}

    function yScale(y) {{
      const r = plotRect();
      return r.y1 - (y - yExtent[0]) / (yExtent[1] - yExtent[0]) * r.h;
    }}

    function drawLine(spectrum, key, alpha=1, width=2) {{
      ctx.save();
      ctx.strokeStyle = spectrum.color.replace(/,[^,]+\\)$/, `,${{alpha}})`);
      ctx.lineWidth = width;
      ctx.beginPath();
      let started = false;
      for (let i = 0; i < spectrum.wavelength_nm.length; i++) {{
        const x = spectrum.wavelength_nm[i];
        const y = spectrum[key][i];
        if (!Number.isFinite(x) || !Number.isFinite(y)) {{
          started = false;
          continue;
        }}
        const px = xScale(x);
        const py = yScale(y);
        if (!started) {{
          ctx.moveTo(px, py);
          started = true;
        }} else {{
          ctx.lineTo(px, py);
        }}
      }}
      ctx.stroke();
      ctx.restore();
    }}

    function draw() {{
      const rect = canvas.getBoundingClientRect();
      ctx.clearRect(0, 0, rect.width, rect.height);
      const r = plotRect();

      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, rect.width, rect.height);

      for (const [a, b] of badWindows) {{
        const x0 = Math.max(r.x0, xScale(a));
        const x1 = Math.min(r.x1, xScale(b));
        if (x1 > x0) {{
          ctx.fillStyle = 'rgba(148, 163, 184, 0.16)';
          ctx.fillRect(x0, r.y0, x1 - x0, r.h);
        }}
      }}

      ctx.strokeStyle = '#1f2933';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(r.x0, r.y0);
      ctx.lineTo(r.x0, r.y1);
      ctx.lineTo(r.x1, r.y1);
      ctx.stroke();

      ctx.fillStyle = '#334e68';
      ctx.font = '12px Arial';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      const xTicks = [400, 700, 1000, 1300, 1600, 1900, 2200, 2500].filter(x => x >= xExtent[0] && x <= xExtent[1]);
      for (const x of xTicks) {{
        const px = xScale(x);
        ctx.strokeStyle = 'rgba(82, 96, 109, 0.18)';
        ctx.beginPath();
        ctx.moveTo(px, r.y0);
        ctx.lineTo(px, r.y1);
        ctx.stroke();
        ctx.fillText(String(x), px, r.y1 + 8);
      }}

      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      const yTicks = 5;
      for (let i = 0; i <= yTicks; i++) {{
        const y = yExtent[0] + (yExtent[1] - yExtent[0]) * i / yTicks;
        const py = yScale(y);
        ctx.strokeStyle = 'rgba(82, 96, 109, 0.18)';
        ctx.beginPath();
        ctx.moveTo(r.x0, py);
        ctx.lineTo(r.x1, py);
        ctx.stroke();
        ctx.fillText(y.toFixed(3), r.x0 - 8, py);
      }}

      for (const spectrum of payload.spectra) {{
        drawLine(spectrum, 'p_low', 0.32, 1);
        drawLine(spectrum, 'p_high', 0.32, 1);
        drawLine(spectrum, 'reflectance', 1, 2.25);
      }}

      ctx.fillStyle = '#1f2933';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'bottom';
      ctx.font = '14px Arial';
      ctx.fillText('Wavelength (nm)', (r.x0 + r.x1) / 2, rect.height - 18);
      ctx.save();
      ctx.translate(18, (r.y0 + r.y1) / 2);
      ctx.rotate(-Math.PI / 2);
      ctx.fillText('Reflectance', 0, 0);
      ctx.restore();
    }}

    function nearestPoint(mouseX, mouseY) {{
      let best = null;
      for (const spectrum of payload.spectra) {{
        for (let i = 0; i < spectrum.wavelength_nm.length; i++) {{
          const x = spectrum.wavelength_nm[i];
          const y = spectrum.reflectance[i];
          if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
          const px = xScale(x);
          const py = yScale(y);
          const dx = px - mouseX;
          const dy = py - mouseY;
          const d2 = dx * dx + dy * dy;
          if (best === null || d2 < best.d2) {{
            best = {{spectrum, i, px, py, d2}};
          }}
        }}
      }}
      return best;
    }}

    canvas.addEventListener('mousemove', (event) => {{
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      const best = nearestPoint(x, y);
      draw();
      if (!best || best.d2 > 18 * 18) {{
        tooltip.style.display = 'none';
        return;
      }}
      ctx.save();
      ctx.fillStyle = best.spectrum.color;
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(best.px, best.py, 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      ctx.restore();

      const i = best.i;
      tooltip.innerHTML =
        `<b>${{best.spectrum.id}}</b><br>` +
        `Wavelength: ${{best.spectrum.wavelength_nm[i].toFixed(1)}} nm<br>` +
        `Reflectance: ${{best.spectrum.reflectance[i].toFixed(5)}}<br>` +
        `P${{payload.p_lo}}: ${{Number.isFinite(best.spectrum.p_low[i]) ? best.spectrum.p_low[i].toFixed(5) : 'NA'}}<br>` +
        `P${{payload.p_hi}}: ${{Number.isFinite(best.spectrum.p_high[i]) ? best.spectrum.p_high[i].toFixed(5) : 'NA'}}<br>` +
        `H5: ${{best.spectrum.h5}}`;
      tooltip.style.display = 'block';
      tooltip.style.left = `${{Math.min(x + 14, rect.width - 280)}}px`;
      tooltip.style.top = `${{Math.max(6, y - 74)}}px`;
    }});

    canvas.addEventListener('mouseleave', () => {{
      tooltip.style.display = 'none';
      draw();
    }});

    window.addEventListener('resize', resize);
    resize();
  </script>
</body>
</html>
"""
    outpath.parent.mkdir(parents=True, exist_ok=True)
    outpath.write_text(html_text, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--points", required=True, help="CSV with columns: id,lat,lon")
    ap.add_argument("--snap", type=int, default=5, help="Snap radius in pixels")
    ap.add_argument("--roi", type=int, default=9, help="Odd integer ROI size")
    ap.add_argument("--out", default=None, help="Output PNG path")
    ap.add_argument("--interactive", action="store_true", help="Also write a hoverable HTML plot")
    ap.add_argument("--html-out", default=None, help="Output HTML path for --interactive")
    ap.add_argument("--show", action="store_true", help="Open the Matplotlib window after saving")
    ap.add_argument("--p_lo", type=float, default=25.0, help="Lower percentile")
    ap.add_argument("--p_hi", type=float, default=75.0, help="Upper percentile")
    ap.add_argument("--title", default=None, help="Optional plot title override")
    ap.add_argument("--subtitle", default=None, help="Optional second title line")
    args = ap.parse_args()

    if args.roi < 1 or args.roi % 2 == 0:
        raise ValueError("--roi must be an odd integer >= 1")
    if not (0.0 <= args.p_lo < args.p_hi <= 100.0):
        raise ValueError("--p_lo and --p_hi must satisfy 0 <= p_lo < p_hi <= 100")

    points = load_point_csv(args.points)
    h5_files = find_h5_files()

    print("\nH5 files available:")
    for h5 in h5_files:
        print(" -", h5.name)

    colors = rainbow_colors(len(points))
    n_plotted = 0
    plot_series: list[ReflectancePlotSeries] = []
    interactive_spectra: list[dict[str, object]] = []

    for point_index, point in enumerate(points):
        print(f"\n=== Point {point.id}: lat={point.lat}, lon={point.lon} ===")

        match = find_h5_for_point(point.lat, point.lon, h5_files)
        if match is None:
            print(f"SKIP Point {point.id}: not inside any H5 tile in data/raw")
            continue

        print("Matched H5:", match.h5_path.name)
        if match.site:
            print("Matched site/group:", match.site)
        print(
            f"lat/lon -> row/col (raw): ({point.lat}, {point.lon}) "
            f"-> (r={match.row}, c={match.col})"
        )

        row, col = snap_to_valid_pixel(
            str(match.h5_path),
            match.reflectance_path,
            match.row,
            match.col,
            radius=args.snap,
            band=0,
        )
        if row is None or col is None:
            print(f"SKIP Point {point.id}: no valid pixel within radius={args.snap}")
            continue

        if (row, col) != (match.row, match.col):
            print(f"Snapped to nearest valid pixel: (r={row}, c={col})")
        else:
            print("Pixel already valid; no snapping needed.")

        wl, med, lo, hi, bounds = read_roi_stats_spectrum(
            str(match.h5_path),
            match.reflectance_path,
            match.wavelength_path,
            row,
            col,
            roi=args.roi,
            p_lo=args.p_lo,
            p_hi=args.p_hi,
        )
        rmin, rmax, cmin, cmax = bounds
        print(f"ROI pixel window: rows {rmin}-{rmax}, cols {cmin}-{cmax}")

        wl = normalize_wavelengths_nm(wl)
        was_scaled = np.any(np.isfinite(med)) and float(np.nanmax(med)) > 2.0
        med = normalize_reflectance(med)
        lo = normalize_reflectance(lo)
        hi = normalize_reflectance(hi)
        if was_scaled:
            print("Applied scale factor: /10000.0")

        bad_mask = build_bad_band_mask(wl, include_narrow=True)
        med_invalid = build_invalid_value_mask(med, min_reflectance=0.0, max_reflectance=1.2)
        lo_invalid = build_invalid_value_mask(lo, min_reflectance=0.0, max_reflectance=1.2)
        hi_invalid = build_invalid_value_mask(hi, min_reflectance=0.0, max_reflectance=1.2)
        masked = bad_mask | med_invalid | lo_invalid | hi_invalid

        med_plot = med.copy()
        lo_plot = lo.copy()
        hi_plot = hi.copy()
        med_plot[masked] = np.nan
        lo_plot[masked] = np.nan
        hi_plot[masked] = np.nan

        good_plot = np.isfinite(wl) & np.isfinite(med_plot)
        if not np.any(good_plot):
            print(f"WARNING Point {point.id}: no valid points after cleaning; skipping curve.")
            continue

        color = colors[point_index]
        n_plotted += 1
        plot_series.append(
            ReflectancePlotSeries(
                label=point.id,
                wavelengths_nm=wl,
                reflectance=med_plot,
                color=color,
                p_low=lo_plot,
                p_high=hi_plot,
            )
        )
        interactive_spectra.append(
            {
                "id": point.id,
                "lat": point.lat,
                "lon": point.lon,
                "h5": match.h5_path.name,
                "row": int(row),
                "col": int(col),
                "wavelength_nm": _finite_float_list(wl),
                "reflectance": _finite_float_list(med_plot),
                "p_low": _finite_float_list(lo_plot),
                "p_high": _finite_float_list(hi_plot),
                "color": _rgba_to_css(color),
            }
        )

    if n_plotted == 0:
        raise RuntimeError("No valid spectra plotted. Check points, tiles, snap radius, or ROI location.")

    points_path = Path(args.points)
    title = args.title if args.title is not None else _figure_title()
    if args.subtitle:
        title = f"{title}\n{args.subtitle}"

    outpath = Path(args.out) if args.out else FIGURES / f"overlay_{Path(args.points).stem}_roi{args.roi}_snap{args.snap}.png"
    plot_reflectance_spectra(
        plot_series,
        outpath=outpath,
        title=title,
        footer=f"{_source_note(points_path, interactive_spectra)} {_roi_size_text(args.roi)}; snap={args.snap}.",
        show=args.show,
    )
    print("\nSaved:", outpath)

    if args.interactive:
        html_outpath = (
            Path(args.html_out)
            if args.html_out
            else outpath.with_name(outpath.stem + "_interactive.html")
        )
        _write_interactive_html(
            html_outpath,
            Path(args.points),
            interactive_spectra,
            args.roi,
            args.snap,
            args.p_lo,
            args.p_hi,
        )
        print("Saved interactive:", html_outpath)


if __name__ == "__main__":
    main()
