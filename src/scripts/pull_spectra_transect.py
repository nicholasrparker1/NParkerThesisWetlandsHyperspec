import argparse
import subprocess
import sys

from src.workflow import load_point_csv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--points", required=True, help="CSV with columns: id,lat,lon")
    ap.add_argument("--roi", type=int, default=9, help="ROI size in pixels (default 9)")
    ap.add_argument("--snap", type=int, default=40, help="Snap/search radius in pixels (default 40)")
    args = ap.parse_args()

    points = load_point_csv(args.points)

    for point in points:
        print(f"\n=== Point {point.id}: lat={point.lat}, lon={point.lon} ===")

        cmd = [
            sys.executable,
            "-m",
            "src.scripts.pull_spectrum_latlon",
            "--lat", str(point.lat),
            "--lon", str(point.lon),
            "--roi", str(args.roi),
            "--snap", str(args.snap),
        ]

        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"FAILED Point {point.id}: {e}")

    print("\nDone.")


if __name__ == "__main__":
    main()
