from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
REGIONAL = ROOT / "outputs" / "tables" / "kssl_regional_expansion"
REGIONAL_FIGURES = ROOT / "outputs" / "figures" / "kssl_regional_expansion"
REGIONAL_NPZ = ROOT / "data" / "processed" / "kssl_great_plains_mir" / "kssl_nd_mt_sd_ne_mean_mir_spectra.npz"
REPORT = ROOT / "outputs" / "reports" / "kssl_product_qa.json"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    results: dict[str, object] = {}
    spectral = np.load(REGIONAL_NPZ)
    ids = spectral["smp_id"]
    wn = spectral["wavenumber_cm1"]
    absorbance = spectral["absorbance"]
    check(absorbance.shape == (len(ids), len(wn)), "Spectral matrix dimensions do not match axes")
    check(len(np.unique(ids)) == len(ids), "Regional sample IDs are not unique")
    check(np.isfinite(absorbance).all(), "Regional spectral matrix contains non-finite values")
    check(np.all(np.diff(wn) < 0), "Wavenumber axis must descend")
    check(np.isclose(wn[0], 4000) and np.isclose(wn[-1], 600), "Unexpected MIR axis endpoints")
    results["regional_spectral_matrix"] = {
        "samples": int(len(ids)),
        "bands": int(len(wn)),
        "wavenumber_min_cm-1": float(wn.min()),
        "wavenumber_max_cm-1": float(wn.max()),
        "all_finite": True,
    }

    cohort = pd.read_csv(REGIONAL / "nd_mt_sd_ne_surface_mir_cohort.csv")
    qc = pd.read_csv(REGIONAL / "regional_mir_sample_qc.csv")
    check(cohort["pedon_key"].is_unique, "Regional cohort contains repeated pedons")
    check(qc["smp_id"].is_unique, "Regional QC table contains repeated samples")
    check(set(qc["smp_id"]) == set(ids), "QC table and NPZ contain different sample IDs")
    check((qc["accepted_replicates"] >= 2).all(), "A retained sample has fewer than two accepted replicates")
    results["regional_cohort"] = {
        "candidate_pedons": int(len(cohort)),
        "usable_mir_samples": int(len(qc)),
        "states": sorted(qc["state"].unique().tolist()),
        "excluded_replicates": int(qc["excluded_replicates"].sum()),
    }

    metric_files = [
        REGIONAL / "regional_project_grouped_metrics.csv",
        REGIONAL / "regional_leave_one_state_out_metrics.csv",
    ]
    for path in metric_files:
        table = pd.read_csv(path)
        check(table["spearman_rho"].between(-1, 1).all(), f"Invalid Spearman rho in {path.name}")
        check(np.isfinite(table[["r2", "rmse", "mae", "spearman_rho"]]).all().all(), f"Non-finite metric in {path.name}")
    results["metric_tables"] = [path.name for path in metric_files]

    figure_results = {}
    for path in sorted(REGIONAL_FIGURES.glob("*.png")):
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            figure_results[path.name] = {"width_px": image.width, "height_px": image.height, "bytes": path.stat().st_size}
            check(image.width >= 2000 and image.height >= 1200, f"Figure resolution is unexpectedly low: {path.name}")
    check(len(figure_results) >= 3, "Expected regional figures are missing")
    results["figures"] = figure_results

    deck_results = {}
    for path in sorted((ROOT / "outputs" / "presentations").glob("*MEETING_READY*.pptx")):
        # Ignore the temporary lock file created while PowerPoint is open.
        if path.name.startswith("~$"):
            continue
        with ZipFile(path) as archive:
            check("[Content_Types].xml" in archive.namelist(), f"Invalid PPTX archive: {path.name}")
            slides = len([name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")])
        deck_results[path.name] = {"slides": slides, "bytes": path.stat().st_size}
    results["presentation_archives"] = deck_results

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    print(f"Saved: {REPORT}")


if __name__ == "__main__":
    main()

