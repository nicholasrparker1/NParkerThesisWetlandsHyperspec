# NParkerThesisWetlandsHyperspec

Python workflow for extracting, cleaning, plotting, and modeling spectra from
NEON-style airborne hyperspectral HDF5 reflectance files.

## Quick Start

1. Put one or more hyperspectral `.h5` files in `data/raw/`.
2. Put point CSVs in `data/processed/` or `data/field/`.
3. Use CSV columns named `id`, `lat`, and `lon`.
4. Install dependencies with `pip install -r requirements.txt`.
5. Run the setup check.
6. Run a workflow script.

The code auto-discovers the H5 site/group name, reflectance cube path,
wavelength path, map metadata path, coordinate grid, and matching H5 tile for
each point. A new user should not need to edit `src/config.py` for normal H5
path changes.

## Common Commands

Check the local setup:

```powershell
python -m src.scripts.check_setup --points data/processed/transect_points.csv
```

Overlay spectra for points in CSV order:

```powershell
python -m src.scripts.pull_spectra_overlay --points data/processed/transect_points.csv --roi 9 --snap 40
```

Plot one lat/lon spectrum:

```powershell
python -m src.scripts.pull_spectrum_latlon --lat 43.14125 --lon -77.50276 --roi 9 --snap 40
```

Map ROI boxes over an orthophoto/raster using the same CSV order and rainbow
color order as the spectral overlay:

```powershell
python -m src.scripts.roi_transect --raster path/to/ortho.tif --points data/processed/transect_points.csv --roi 9
```

Build moisture training data:

```powershell
python -m src.scripts.build_moisture_training_table --csv data/field/moisture_points.csv --roi 5 --snap 40
```

## Project Layout

- `src/workflow.py`: shared H5 discovery, point loading, tile matching, color order, and normalization helpers.
- `src/io_hyperspectral.py`: low-level HDF5, reflectance, and coordinate utilities.
- `src/preprocess.py`: bad-band and invalid-reflectance masking.
- `src/scripts/`: active command-line workflows.
- `src/models/`: moisture baseline and simplified MARMIT-style modeling code.
- `data/raw/`: local raw `.h5` files, not tracked.
- `data/processed/`: point lists and intermediate data products.
- `outputs/`: generated figures, tables, and H5 reports.
- `legacy/`: older duplicate or brittle one-off scripts kept for reference.

## Notes

If multiple H5 files are present, point-based scripts test each file and use the
tile that contains each point. Points are plotted in CSV row order. The rainbow
color mapping is shared by spectrum overlays and ROI transect maps.
