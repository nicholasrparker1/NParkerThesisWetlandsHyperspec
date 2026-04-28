from __future__ import annotations

import argparse

import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

from src.config import FIGURES
from src.workflow import load_point_csv, rainbow_colors


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raster", required=True)
    ap.add_argument("--points", required=True, help="CSV with columns: id,lat,lon")
    ap.add_argument("--roi", type=int, default=9, help="HSI ROI size in pixels")
    ap.add_argument("--hsi_m", type=float, default=1.0, help="HSI pixel size in meters")
    ap.add_argument("--out", default=None, help="Output PNG path")
    args = ap.parse_args()

    points = load_point_csv(args.points)
    out = args.out or str(FIGURES / f"roi_transect_roi{args.roi}px.png")

    with rasterio.open(args.raster) as src:
        if src.count >= 3:
            img = src.read([1, 2, 3])
            disp = np.moveaxis(img, 0, -1)
        else:
            disp = src.read(1)

        fig, ax = plt.subplots(figsize=(9, 9))
        ax.imshow(disp)
        ax.set_axis_off()

        camera_pixel_m = sum(src.res) / 2
        try:
            from matplotlib_scalebar.scalebar import ScaleBar

            ax.add_artist(
                ScaleBar(
                    dx=camera_pixel_m,
                    units="m",
                    location="lower right",
                    box_alpha=0.7,
                    length_fraction=0.25,
                )
            )
        except ModuleNotFoundError:
            print("matplotlib_scalebar is not installed; ROI map will be saved without a scale bar.")

        try:
            from pyproj import Transformer
        except ModuleNotFoundError as exc:
            raise RuntimeError("pyproj is required to map lat/lon points onto the raster.") from exc

        transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
        target_footprint_m = args.roi * args.hsi_m
        roi_px_camera = max(1, int(round(target_footprint_m / camera_pixel_m)))
        half = roi_px_camera // 2

        colors = rainbow_colors(len(points))
        legend_handles = []

        for point, color in zip(points, colors):
            x, y = transformer.transform(point.lon, point.lat)
            col, row = ~src.transform * (x, y)

            rect = Rectangle(
                (col - half, row - half),
                roi_px_camera,
                roi_px_camera,
                linewidth=2.5,
                edgecolor=color,
                facecolor="none",
            )
            ax.add_patch(rect)
            legend_handles.append(Line2D([0], [0], color=color, lw=3, label=f"Point {point.id}"))

        ax.set_title(
            f"HSI ROI boxes along transect ({args.roi}x{args.roi}, "
            f"about {target_footprint_m:.1f} m footprint)"
        )
        ax.legend(handles=legend_handles, loc="upper right", framealpha=0.9, title="Transect points")

        plt.savefig(out, dpi=300, bbox_inches="tight")
        plt.show()
        print("Saved:", out)


if __name__ == "__main__":
    main()
