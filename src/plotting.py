from __future__ import annotations


def plot_roi_box_on_raster(
    raster_path: str,
    lat: float,
    lon: float,
    roi_px: int = 9,
    hsi_pixel_m: float = 1.0,
    out_png: str | None = None,
):
    import matplotlib.pyplot as plt
    import numpy as np
    import rasterio
    from matplotlib.patches import Rectangle
    from matplotlib_scalebar.scalebar import ScaleBar
    from pyproj import Transformer

    with rasterio.open(raster_path) as src:
        if src.count >= 3:
            img = src.read([1, 2, 3])
            disp = np.moveaxis(img, 0, -1)
        else:
            disp = src.read(1)

        transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
        x, y = transformer.transform(lon, lat)
        col, row = ~src.transform * (x, y)

        camera_pixel_m = sum(src.res) / 2
        target_footprint_m = roi_px * hsi_pixel_m
        roi_px_camera = max(1, int(round(target_footprint_m / camera_pixel_m)))
        half = roi_px_camera // 2

        fig, ax = plt.subplots(figsize=(8, 8))
        ax.imshow(disp)
        ax.add_artist(
            ScaleBar(
                dx=camera_pixel_m,
                units="m",
                location="lower right",
                box_alpha=0.7,
                length_fraction=0.25,
            )
        )

        rect = Rectangle(
            (col - half, row - half),
            roi_px_camera,
            roi_px_camera,
            linewidth=2,
            edgecolor="red",
            facecolor="none",
        )
        ax.add_patch(rect)
        ax.set_axis_off()
        ax.set_title(
            f"{roi_px}x{roi_px} HSI ROI "
            f"(about {target_footprint_m:.1f} m x {target_footprint_m:.1f} m footprint)"
        )

        if out_png:
            plt.savefig(out_png, dpi=300, bbox_inches="tight")

        plt.show()
