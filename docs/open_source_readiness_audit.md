# Open Source Readiness Audit

This repo is already pointed at:

`https://github.com/nicholasrparker1/NParkerThesisWetlandsHyperspec.git`

The strongest public-facing story is:

1. Learn how NEON hyperspectral HDF5 reflectance files are structured.
2. Auto-discover reflectance, wavelength, map metadata, and projection paths.
3. Match latitude/longitude point data to the correct H5 tile.
4. Extract single-pixel or ROI median spectra.
5. Mask invalid reflectance and atmospheric absorption regions.
6. Plot spectra and inspect ROI variability.
7. Screen point spectra for water, vegetation, mixed cover, and bare-soil usability.
8. Optionally connect spectra to soil chemistry, moisture, wetland context, and hydric-soil evidence.

## Public Entry Points

These should be the front-door workflows in the README:

- `python -m src.scripts.menu`
- `python -m src.scripts.check_setup`
- `python -m src.scripts.pull_spectrum_latlon`
- `python -m src.scripts.pull_spectra_overlay`
- `python -m src.scripts.classify_point_cover`

These are useful but should be presented as thesis or advanced workflows:

- `python -m src.scripts.prepare_neon_soil_chemistry_table`
- `python -m src.scripts.build_soil_spectral_table`
- `python -m src.scripts.build_wetland_context`
- `python -m src.scripts.build_hydric_evidence_table`
- `python -m src.scripts.analyze_soil_spectral_correlations`
- `python -m src.scripts.build_moisture_training_table`
- `python -m src.scripts.run_moisture_baseline`
- `python -m src.scripts.compare_aerial_wetness_methods`

The top-level `scripts/` directory is best framed as thesis support tooling for
NEON tile planning and download auditing, not the beginner learning path.

## Code Organization

The current core structure is good for open source:

- `src/io_hyperspectral.py` contains NEON H5 discovery, reflectance scaling, ROI reading, snapping, and coordinate conversion.
- `src/preprocess.py` contains atmospheric band masks and invalid reflectance masks.
- `src/workflow.py` contains point CSV loading and H5 tile matching.
- `src/spectral_workflow.py` contains reusable clean ROI extraction.
- `src/spectral_plotting.py` contains shared static plotting.
- `src/models/cover_classification.py` contains the cover usability classifier.

Suggested public framing:

- `src/` is the reusable package.
- `src/scripts/` contains reproducible command-line workflows.
- `scripts/` contains thesis project support utilities.
- `docs/` contains workflow and research notes.
- `data/processed/transect_points.csv` and `data/processed/reference_points.csv` are small example point files.

## GitHub Risks To Clean Up

- The worktree currently has many deleted legacy files and many untracked generated tables. Commit cleanup deliberately so the public repo does not look half-migrated.
- Raw H5, GeoPackage, TIFF, downloaded NEON soil-periodic files, and generated outputs should stay untracked.
- Decide whether tracked generated artifacts such as `data/processed/moisture_training_data.npz`, `data/processed/moisture_training_summary.csv`, and `data/processed/marmit_calibration_table.csv` are still useful as examples. If not, remove them from tracking in a cleanup commit.
- Keep only small, non-sensitive sample CSVs in `data/processed/` for public tutorials.
- The README references thesis-specific data names. That is fine, but it should clearly separate "try this with your own NEON H5 + point CSV" from "thesis replication workflows."
- Add a license before sharing publicly.
- Add a citation note for NEON data products and a short disclaimer that derived screening thresholds are conservative research utilities, not official land-cover classifications.

## Recommended Public README Shape

1. What this repo teaches.
2. What data users need from NEON.
3. Install commands.
4. Minimal point CSV example.
5. Run `check_setup`.
6. Extract one spectrum.
7. Plot several spectra.
8. Screen cover usability.
9. Optional thesis workflows.
10. Data policy: raw data and generated outputs are not tracked.
11. Citation, license, and contact.

## Verification

Current code compiled successfully with:

`python -m compileall src scripts`
