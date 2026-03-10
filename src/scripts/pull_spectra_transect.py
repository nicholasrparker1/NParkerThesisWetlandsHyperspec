import argparse
import csv
import subprocess
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--points", required=True, help="CSV with columns: id,lat,lon")
    ap.add_argument("--roi", type=int, default=9, help="ROI size in pixels (default 9)")
    ap.add_argument("--snap", type=int, default=40, help="Snap/search radius in pixels (default 40)")
    args = ap.parse_args()

    pts = []
    with open(args.points, "r", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            pts.append((str(r["id"]), float(r["lat"]), float(r["lon"])))

    for pid, lat, lon in pts:
        print(f"\n=== Point {pid}: lat={lat}, lon={lon} ===")

        cmd = [
            sys.executable,
            "-m",
            "src.scripts.pull_spectrum_latlon",
            "--lat", str(lat),
            "--lon", str(lon),
            "--roi", str(args.roi),
            "--snap", str(args.snap),
        ]

        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"FAILED Point {pid}: {e}")

    print("\nDone.")


if __name__ == "__main__":
    main()