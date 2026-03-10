def plot_roi_box_on_raster(
    raster_path: str,
    lat: float,
    lon: float,
    roi_px: int = 9,              # ROI size in HSI pixels
    hsi_pixel_m: float = 1.0,     # HSI resolution (m per HSI pixel). You said 1.0
    out_png: str | None = None,
):
    import numpy as np
    import matplotlib.pyplot as plt
    import rasterio
    from matplotlib.patches import Rectangle
    from pyproj import Transformer
    from matplotlib_scalebar.scalebar import ScaleBar

    with rasterio.open(raster_path) as src:
        # Display raster (RGB if available, else grayscale)
        if src.count >= 3:
            img = src.read([1, 2, 3])
            disp = np.moveaxis(img, 0, -1)
        else:
            disp = src.read(1)

        # Convert lat/lon -> raster CRS, then -> pixel coords
        transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
        x, y = transformer.transform(lon, lat)
        col, row = ~src.transform * (x, y)

        # Camera ortho pixel size (meters per pixel)
        cam_px_x, cam_px_y = src.res
        cam_px_m = (cam_px_x + cam_px_y) / 2

        # HSI footprint in meters (this is what your spectral ROI actually represents)
        target_footprint_m = roi_px * hsi_pixel_m  # 9 * 1.0 = 9 m

        # Convert that footprint to camera pixels for drawing the box on the ortho
        roi_px_camera = int(round(target_footprint_m / cam_px_m))
        roi_px_camera = max(1, roi_px_camera)  # safety
        half = roi_px_camera // 2

        fig, ax = plt.subplots(figsize=(8, 8))
        ax.imshow(disp)

        # Scale bar in meters using camera ortho resolution
        scalebar = ScaleBar(
            dx=cam_px_m,
            units="m",
            location="lower right",
            box_alpha=0.7,
            length_fraction=0.25,
        )
        ax.add_artist(scalebar)

        # Draw ROI box
        rect = Rectangle(
            (col - half, row - half),
            roi_px_camera,
            roi_px_camera,
            linewidth=2,
            edgecolor="red",
            facecolor="none",
        )
        ax.add_patch(rect)

        # Clean thesis-style visualization + correct footprint text (HSI footprint!)
        ax.set_axis_off()
        ax.set_title(
            f"{roi_px}×{roi_px} HSI ROI (~{target_footprint_m:.1f} m × {target_footprint_m:.1f} m footprint)"
        )

        if out_png:
            plt.savefig(out_png, dpi=300, bbox_inches="tight")

        plt.show()