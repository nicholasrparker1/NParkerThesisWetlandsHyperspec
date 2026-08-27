from __future__ import annotations

import csv
import importlib
import sys
from pathlib import Path
from typing import Callable

from src.config import DATA_PROCESSED, DATA_RAW, FIGURES, PROJECT_ROOT


DEFAULT_ALPHA_CSV = DATA_PROCESSED / "water_absorption_coeff_segelstein_400_2500nm_per_um.csv"


def _rel(path: str | Path) -> str:
    path = Path(path)
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _prompt(text: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default not in (None, "") else ""
    value = input(f"{text}{suffix}: ").strip()
    return default if value == "" and default is not None else value


def _confirm(text: str, default: bool = True) -> bool:
    suffix = "Y/n" if default else "y/N"
    value = input(f"{text} [{suffix}]: ").strip().lower()
    if value == "":
        return default
    return value in {"y", "yes"}


def _ask_int(
    text: str,
    default: int,
    *,
    odd: bool = False,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    while True:
        raw = _prompt(text, str(default))
        try:
            value = int(raw)
        except ValueError:
            print("Please enter a whole number.")
            continue
        if minimum is not None and value < minimum:
            print(f"Please enter a value >= {minimum}.")
            continue
        if maximum is not None and value > maximum:
            print(f"Please enter a value <= {maximum}.")
            continue
        if odd and value % 2 == 0:
            print("Please enter an odd number so the ROI has a center pixel.")
            continue
        return value


def _ask_float(text: str, default: float | None = None) -> float:
    while True:
        raw = _prompt(text, None if default is None else str(default))
        try:
            return float(raw)
        except ValueError:
            print("Please enter a number.")


def _candidate_files(patterns: tuple[str, ...], roots: tuple[Path, ...]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if root.exists():
            for pattern in patterns:
                files.extend(sorted(root.glob(pattern)))
    return sorted(dict.fromkeys(files), key=lambda path: _rel(path).lower())


def _choose_file(label: str, candidates: list[Path], default: Path | None = None) -> Path:
    if default is not None and default not in candidates and default.exists():
        candidates = [default, *candidates]

    print(f"\n{label}")
    if candidates:
        for i, path in enumerate(candidates, start=1):
            marker = " (default)" if default is not None and path == default else ""
            print(f"{i}. {_rel(path)}{marker}")
        print(f"{len(candidates) + 1}. Enter another path")

        raw = _prompt("Choose", "1" if default is None else str(candidates.index(default) + 1 if default in candidates else 1))
        if raw.isdigit():
            choice = int(raw)
            if 1 <= choice <= len(candidates):
                return candidates[choice - 1]
    else:
        print("No matching files found in the usual folders.")

    return Path(_prompt("Path"))


def _point_csvs() -> list[Path]:
    return _candidate_files(("*.csv",), (DATA_PROCESSED, PROJECT_ROOT / "data" / "field"))


def _soil_tables() -> list[Path]:
    return _candidate_files(("*.xlsx", "*.csv"), (PROJECT_ROOT / "data" / "field", DATA_PROCESSED))


def _npz_files() -> list[Path]:
    return _candidate_files(("*.npz",), (DATA_PROCESSED,))


def _wetland_context_tables() -> list[Path]:
    return _candidate_files(("*Wetland_Context*.xlsx", "*Wetland_Context*.csv"), (DATA_PROCESSED,))


def _read_point_ids(points_path: Path) -> list[str]:
    try:
        with open(points_path, "r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if "id" not in (reader.fieldnames or []):
                return []
            return [str(row["id"]).strip() for row in reader if str(row.get("id", "")).strip()]
    except OSError:
        return []


def _choose_point_id(points_path: Path, label: str, default: str | None = None) -> str:
    ids = _read_point_ids(points_path)
    if ids:
        preview = ", ".join(ids[:16])
        if len(ids) > 16:
            preview += ", ..."
        print(f"Available IDs in {_rel(points_path)}: {preview}")
    return _prompt(label, default)


def _run_module(module_name: str, args: list[str]) -> None:
    command = ["python", "-m", module_name, *args]
    print("\nCommand:")
    print(" ".join(command))
    if not _confirm("Run this now?", True):
        return

    module = importlib.import_module(module_name)
    old_argv = sys.argv[:]
    try:
        sys.argv = [module_name, *args]
        module.main()
    finally:
        sys.argv = old_argv


def _check_data_hint() -> None:
    h5_count = len(list(DATA_RAW.glob("*.h5"))) if DATA_RAW.exists() else 0
    print(f"\nH5 files in {_rel(DATA_RAW)}: {h5_count}")
    if h5_count == 0:
        print("Add NEON-style .h5 reflectance files before running extraction workflows.")


def check_setup() -> None:
    _check_data_hint()
    points = _choose_file(
        "Point CSV for setup validation",
        _point_csvs(),
        DATA_PROCESSED / "transect_points.csv",
    )
    args = ["--points", _rel(points)]
    if not _confirm("Validate point coverage too?", True):
        args.append("--skip-points")
    _run_module("src.scripts.check_setup", args)


def plot_overlay() -> None:
    _check_data_hint()
    points = _choose_file("Point CSV to plot", _point_csvs(), DATA_PROCESSED / "transect_points.csv")
    roi = _ask_int("ROI size in pixels", 3, odd=True, minimum=1)
    snap = _ask_int("Snap radius in pixels", 40, minimum=0)
    interactive = _confirm("Also create hoverable HTML?", True)
    show = _confirm("Open a Matplotlib window after saving?", False)

    stem = Path(points).stem
    out = FIGURES / f"overlay_{stem}_roi{roi}_snap{snap}.png"
    args = ["--points", _rel(points), "--roi", str(roi), "--snap", str(snap), "--out", _rel(out)]
    if interactive:
        args.extend(["--interactive", "--html-out", _rel(out.with_name(out.stem + "_interactive.html"))])
    if show:
        args.append("--show")
    _run_module("src.scripts.pull_spectra_overlay", args)


def plot_one_point() -> None:
    _check_data_hint()
    lat = _ask_float("Latitude")
    lon = _ask_float("Longitude")
    roi = _ask_int("ROI size in pixels", 3, odd=True, minimum=1)
    snap = _ask_int("Snap radius in pixels", 40, minimum=0)
    show = _confirm("Open a Matplotlib window after saving?", False)
    out = FIGURES / f"spectrum_roi{roi}_lat{lat:.5f}_lon{lon:.5f}_snap{snap}.png"
    args = [
        "--lat",
        str(lat),
        "--lon",
        str(lon),
        "--roi",
        str(roi),
        "--snap",
        str(snap),
        "--out",
        _rel(out),
    ]
    if show:
        args.append("--show")
    _run_module("src.scripts.pull_spectrum_latlon", args)


def build_soil_table() -> None:
    _check_data_hint()
    soil = _choose_file("Soil workbook/table", _soil_tables(), PROJECT_ROOT / "data" / "field" / "NEON_Master_Soil_Table.xlsx")
    roi = _ask_int("ROI size in pixels; 3 is the current conservative max", 3, odd=True, minimum=1, maximum=3)
    snap = _ask_int("Snap radius in pixels", 40, minimum=0)
    first_n = _prompt("Limit to first N rows for a smoke test; blank means all", "")
    out = DATA_PROCESSED / "soil_spectral_table.csv"
    args = ["--soil-xlsx", _rel(soil), "--roi", str(roi), "--snap", str(snap), "--out", _rel(out)]
    if first_n:
        args.extend(["--first-n", first_n])
    _run_module("src.scripts.build_soil_spectral_table", args)


def screen_point_cover() -> None:
    _check_data_hint()
    points = _choose_file("Point CSV to screen for soil/vegetation/water cover", _point_csvs(), DATA_PROCESSED / "transect_points.csv")
    roi = _ask_int("ROI size in pixels", 3, odd=True, minimum=1)
    snap = _ask_int("Snap radius in pixels", 40, minimum=0)
    include_ids = _prompt("Optional comma-separated IDs to process; blank means all", "")
    out = DATA_PROCESSED / f"point_cover_classification_{Path(points).stem}.csv"
    args = ["--points", _rel(points), "--roi", str(roi), "--snap", str(snap), "--out", _rel(out)]
    if include_ids:
        args.extend(["--include-ids", include_ids])
    _run_module("src.scripts.classify_point_cover", args)


def analyze_soil_correlations() -> None:
    table = _choose_file(
        "Soil spectral table to analyze",
        _candidate_files(("soil_spectral_table*.csv", "*.csv"), (DATA_PROCESSED,)),
        DATA_PROCESSED / "soil_spectral_table.csv",
    )
    top_n = _ask_int("Top bands per soil target for scatterplots", 3, minimum=1)
    args = ["--table", _rel(table), "--top-n", str(top_n)]
    _run_module("src.scripts.analyze_soil_spectral_correlations", args)


def build_hydric_evidence_table() -> None:
    soil_table = _choose_file(
        "Soil spectral table",
        _candidate_files(("soil_spectral_table*.csv", "*.csv"), (DATA_PROCESSED,)),
        DATA_PROCESSED / "soil_spectral_table.csv",
    )
    cover_table = _choose_file(
        "Optional cover classification table",
        _candidate_files(("point_cover_classification*.csv",), (DATA_PROCESSED,)),
        DATA_PROCESSED / f"point_cover_classification_{Path(soil_table).stem}.csv",
    )
    use_cover = cover_table.exists() and _confirm("Merge this cover classification table?", True)
    wetland_table = _choose_file(
        "Optional NWI wetland context table",
        _wetland_context_tables(),
        DATA_PROCESSED / "NEON_Soil_Wetland_Context_Table.xlsx",
    )
    use_wetland = wetland_table.exists() and _confirm("Merge this NWI wetland context table?", True)
    args = [
        "--soil-spectral-table",
        _rel(soil_table),
        "--out",
        _rel(DATA_PROCESSED / "hydric_evidence_table.csv"),
    ]
    if use_cover:
        args.extend(["--cover-table", _rel(cover_table)])
    if use_wetland:
        args.extend(["--wetland-context-table", _rel(wetland_table)])
    _run_module("src.scripts.build_hydric_evidence_table", args)


def build_wetland_context() -> None:
    soil = _choose_file(
        "NEON soil master table for NWI wetland context",
        _soil_tables(),
        PROJECT_ROOT / "data" / "field" / "NEON_Master_Soil_Table.xlsx",
    )
    nwi_dir = _prompt("Directory containing NWI GeoPackage files", _rel(PROJECT_ROOT / "data" / "raw" / "nwi"))
    out = DATA_PROCESSED / "NEON_Soil_Wetland_Context_Table.xlsx"
    args = [
        "--soil-xlsx",
        _rel(soil),
        "--nwi-dir",
        nwi_dir,
        "--out",
        _rel(out),
    ]
    _run_module("src.scripts.build_wetland_context", args)


def build_moisture_training() -> None:
    _check_data_hint()
    points = _choose_file("Moisture point CSV", _point_csvs(), PROJECT_ROOT / "data" / "field" / "moisture_points.csv")
    roi = _ask_int("ROI size in pixels", 3, odd=True, minimum=1)
    snap = _ask_int("Snap radius in pixels", 40, minimum=0)
    args = [
        "--csv",
        _rel(points),
        "--roi",
        str(roi),
        "--snap",
        str(snap),
        "--out_npz",
        _rel(DATA_PROCESSED / "moisture_training_data.npz"),
        "--out_csv",
        _rel(DATA_PROCESSED / "moisture_training_summary.csv"),
    ]
    _run_module("src.scripts.build_moisture_training_table", args)


def run_moisture_baseline() -> None:
    npz = _choose_file("Moisture training NPZ", _npz_files(), DATA_PROCESSED / "moisture_training_data.npz")
    args = [
        "--npz",
        _rel(npz),
        "--outfig",
        _rel(FIGURES / "moisture_baseline_fit.png"),
    ]
    _run_module("src.scripts.run_moisture_baseline", args)


def compare_wetness() -> None:
    _check_data_hint()
    points = _choose_file("Point CSV for wetness comparison", _point_csvs(), DATA_PROCESSED / "marmit_calibration_table_updated.csv")
    dry_id = _choose_point_id(points, "Dry reference point ID")
    include_ids = _prompt("Optional comma-separated IDs to process; blank means all", "")
    plot_target_id = _prompt("Optional point ID for detailed fit figure", "")
    roi = _ask_int("ROI size in pixels", 3, odd=True, minimum=1)
    snap = _ask_int("Snap radius in pixels", 40, minimum=0)

    args = [
        "--points",
        _rel(points),
        "--dry-id",
        dry_id,
        "--alpha-csv",
        _rel(DEFAULT_ALPHA_CSV),
        "--roi",
        str(roi),
        "--snap",
        str(snap),
    ]
    if include_ids:
        args.extend(["--include-ids", include_ids])
    if plot_target_id:
        args.extend(["--plot-target-id", plot_target_id])
    _run_module("src.scripts.compare_aerial_wetness_methods", args)


def _menu() -> list[tuple[str, Callable[[], None]]]:
    return [
        ("Check setup", check_setup),
        ("Plot publication-style spectra from a point CSV", plot_overlay),
        ("Plot one lat/lon spectrum as a single curve", plot_one_point),
        ("Screen point cover for soil usability", screen_point_cover),
        ("Build soil spectral table", build_soil_table),
        ("Build NWI wetland context table", build_wetland_context),
        ("Build hydric evidence table", build_hydric_evidence_table),
        ("Analyze soil chemistry correlations", analyze_soil_correlations),
        ("Build moisture training table", build_moisture_training),
        ("Run baseline moisture model", run_moisture_baseline),
        ("Optional: compare exploratory wetness methods", compare_wetness),
    ]


def main() -> None:
    print("\nWetlands Hyperspectral Workflow")
    print("Lean launcher for common tasks. Existing scripts remain the source of record.")

    while True:
        print("\nWhat would you like to do?")
        entries = _menu()
        for i, (label, _) in enumerate(entries, start=1):
            print(f"{i}. {label}")
        print(f"{len(entries) + 1}. Exit")

        choice = _prompt("Choose", "1")
        if not choice.isdigit():
            print("Please enter a menu number.")
            continue
        index = int(choice)
        if index == len(entries) + 1:
            print("Done.")
            return
        if not 1 <= index <= len(entries):
            print("Please choose one of the listed options.")
            continue

        try:
            entries[index - 1][1]()
        except KeyboardInterrupt:
            print("\nCanceled.")
        except SystemExit as exc:
            if exc.code not in (0, None):
                print(exc)
        except Exception as exc:
            print(f"\nWorkflow failed: {exc}")


if __name__ == "__main__":
    main()
