import argparse
from pathlib import Path

from src.plotting import plot_roi_box_on_raster
from src.config import FIGURES  # you already use FIGURES in your other script

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raster", required=True, help="Path to ortho/rgb GeoTIFF (e.g., camera.ort.tif)")
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--roi", type=int, default=9, help="ROI size in pixels (default 9)")
    ap.add_argument("--out", default=None, help="Optional output PNG path")
    args = ap.parse_args()

    out = args.out
    if out is None:
        out = str(FIGURES / f"roi_box_lat{args.lat:.5f}_lon{args.lon:.5f}_roi{args.roi}px.png")

    plot_roi_box_on_raster(
        raster_path=args.raster,
        lat=args.lat,
        lon=args.lon,
        roi_px=args.roi,
        out_png=out,
    )
    print("Saved:", out)

if __name__ == "__main__":
    main()