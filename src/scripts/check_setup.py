from __future__ import annotations

import argparse
import importlib
from pathlib import Path

from src.config import DATA_RAW, FIGURES, OUTPUTS, TABLES
from src.workflow import find_h5_files, find_h5_for_point, load_point_csv
from src.io_hyperspectral import discover_neon_h5_paths


PACKAGE_CHECKS = [
    ("numpy", "numpy", True),
    ("pandas", "pandas", True),
    ("matplotlib", "matplotlib", True),
    ("h5py", "h5py", True),
    ("pyproj", "pyproj", True),
    ("rasterio", "rasterio", True),
    ("scikit-learn", "sklearn", False),
    ("openpyxl", "openpyxl", False),
    ("contextily", "contextily", False),
    ("matplotlib-scalebar", "matplotlib_scalebar", False),
]


def check_packages() -> tuple[bool, list[str]]:
    ok = True
    lines = []

    for label, module_name, required in PACKAGE_CHECKS:
        try:
            importlib.import_module(module_name)
            lines.append(f"OK   package: {label}")
        except ModuleNotFoundError:
            level = "MISS required" if required else "MISS optional"
            lines.append(f"{level}: {label}")
            if required:
                ok = False

    return ok, lines


def check_directories() -> list[str]:
    lines = []
    for path in [DATA_RAW, OUTPUTS, FIGURES, TABLES]:
        path.mkdir(parents=True, exist_ok=True)
        lines.append(f"OK   directory: {path}")
    return lines


def check_h5_files() -> tuple[bool, list, list[str]]:
    lines = []
    try:
        h5_files = find_h5_files()
    except FileNotFoundError as exc:
        return False, [], [f"MISS required: {exc}"]

    lines.append(f"OK   H5 files found: {len(h5_files)}")
    for h5_path in h5_files:
        try:
            paths = discover_neon_h5_paths(str(h5_path))
            lines.append(
                f"OK   H5 paths: {h5_path.name} "
                f"(site={paths.get('site')}, reflectance={paths['reflectance_path']})"
            )
        except Exception as exc:
            lines.append(f"FAIL H5 discovery: {h5_path.name}: {exc}")
            return False, h5_files, lines

    return True, h5_files, lines


def check_points(points_path: Path, h5_files: list) -> tuple[bool, list[str]]:
    lines = []
    try:
        points = load_point_csv(points_path)
    except Exception as exc:
        return False, [f"FAIL points CSV: {points_path}: {exc}"]

    lines.append(f"OK   points CSV: {points_path} ({len(points)} points)")

    all_inside = True
    for point in points:
        match = find_h5_for_point(point.lat, point.lon, h5_files)
        if match is None:
            all_inside = False
            lines.append(f"FAIL point {point.id}: not inside any H5 tile")
        else:
            lines.append(
                f"OK   point {point.id}: {match.h5_path.name} "
                f"row={match.row} col={match.col}"
            )

    return all_inside, lines


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--points",
        default="data/processed/transect_points.csv",
        help="Point CSV to validate; must have id,lat,lon columns",
    )
    ap.add_argument(
        "--skip-points",
        action="store_true",
        help="Only check packages, folders, and H5 discovery",
    )
    args = ap.parse_args()

    overall_ok = True

    print("\n=== Package Check ===")
    ok, lines = check_packages()
    overall_ok &= ok
    print("\n".join(lines))

    print("\n=== Directory Check ===")
    print("\n".join(check_directories()))

    print("\n=== H5 Check ===")
    ok, h5_files, lines = check_h5_files()
    overall_ok &= ok
    print("\n".join(lines))

    if not args.skip_points:
        print("\n=== Point Check ===")
        ok, lines = check_points(Path(args.points), h5_files)
        overall_ok &= ok
        print("\n".join(lines))

    if overall_ok:
        print("\nSETUP CHECK PASSED")
    else:
        raise SystemExit("\nSETUP CHECK FAILED")


if __name__ == "__main__":
    main()
