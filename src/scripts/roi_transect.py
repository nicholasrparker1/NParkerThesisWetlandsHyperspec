import argparse
import csv

import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.patches import Rectangle
from matplotlib_scalebar.scalebar import ScaleBar
from matplotlib.lines import Line2D
from pyproj import Transformer

from src.config import FIGURES


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raster", required=True)
    ap.add_argument("--points", required=True, help="CSV with columns: id,lat,lon")
    ap.add_argument("--roi", type=int, default=9, help="HSI ROI size in pixels (default 9)")
    ap.add_argument("--hsi_m", type=float, default=1.0, help="HSI pixel size in meters (default 1.0)")
    ap.add_argument("--out", default=None, help="Output PNG path")
    args = ap.parse_args()

    pts = []
    with open(args.points, "r", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            pts.append((str(r["id"]), float(r["lat"]), float(r["lon"])))

    out = args.out
    if out is None:
        out = str(FIGURES / f"roi_transect_roi{args.roi}px.png")

    with rasterio.open(args.raster) as src:
        # display raster
        if src.count >= 3:
            img = src.read([1, 2, 3])
            disp = np.moveaxis(img, 0, -1)
        else:
            disp = src.read(1)

        fig, ax = plt.subplots(figsize=(9, 9))
        ax.imshow(disp)
        ax.set_axis_off()

        # scalebar from camera ortho resolution
        cam_px_m = sum(src.res) / 2
        ax.add_artist(
            ScaleBar(
                dx=cam_px_m,
                units="m",
                location="lower right",
                box_alpha=0.7,
                length_fraction=0.25,
            )
        )

        # convert lat/lon -> raster CRS -> pixel coords
        transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)

        # convert HSI footprint meters -> camera pixels
        target_footprint_m = args.roi * args.hsi_m
        roi_px_camera = int(round(target_footprint_m / cam_px_m))
        roi_px_camera = max(1, roi_px_camera)
        half = roi_px_camera // 2

        # Rainbow-style colors progressing by point order
        n = len(pts)
        colors = plt.cm.gist_rainbow(np.linspace(0, 1, n, endpoint=False))

        legend_handles = []

        for i, (pid, lat, lon) in enumerate(pts):
            color = colors[i]

            x, y = transformer.transform(lon, lat)
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

            legend_handles.append(
                Line2D([0], [0], color=color, lw=3, label=f"Point {pid}")
            )

        ax.set_title(
            f"HSI ROI boxes along transect ({args.roi}×{args.roi}, ~{target_footprint_m:.1f} m footprint)"
        )

        ax.legend(
            handles=legend_handles,
            loc="upper right",
            framealpha=0.9,
            title="Transect points",
        )

        plt.savefig(out, dpi=300, bbox_inches="tight")
        plt.show()
        print("Saved:", out)


if __name__ == "__main__":
    main()