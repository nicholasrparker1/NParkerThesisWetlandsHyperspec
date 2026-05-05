# Wetlands Hyperspectral Reflectance Quick Start

This repo plots reflectance spectra from NEON-style hyperspectral `.h5` files at
point locations from a CSV.

## 1. Install

From the repo folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 2. Add Data

Put hyperspectral reflectance files here:

```text
data/raw/
```

The files should be NEON-style `.h5` reflectance files.

Create a point CSV with these columns:

```text
id,lat,lon
```

Example:

```csv
id,lat,lon
1,43.1412490,-77.5027607
2,43.1412646,-77.5028096
3,43.1412883,-77.5028766
```

This repo already includes:

```text
data/processed/transect_points.csv
data/processed/reference_points.csv
```

## 3. Check Setup

```powershell
.\.venv\Scripts\python.exe -m src.scripts.check_setup --points data/processed/transect_points.csv
```

## 4. Plot Reflectance

Static PNG:

```powershell
.\.venv\Scripts\python.exe -m src.scripts.pull_spectra_overlay --points data/processed/transect_points.csv --roi 3 --snap 40 --out outputs/figures/transect_spectra_overlay.png
```

Interactive HTML with hover values:

```powershell
.\.venv\Scripts\python.exe -m src.scripts.pull_spectra_overlay --points data/processed/transect_points.csv --roi 3 --snap 40 --out outputs/figures/transect_spectra_overlay.png --interactive --html-out outputs/figures/transect_spectra_overlay_interactive.html
```

Open the interactive file in a browser:

```powershell
Start-Process outputs/figures/transect_spectra_overlay_interactive.html
```

Hover near a curve to see:

```text
point ID
wavelength
reflectance
ROI percentile values
matched H5 tile
```

## Useful Options

```text
--points       CSV with id,lat,lon
--roi          ROI box size in pixels; must be odd, such as 3, 5, or 9
--snap         search radius for the nearest valid pixel
--out          PNG output path
--interactive  also write a hoverable HTML plot
--html-out     HTML output path
--show         open the Matplotlib window after saving
```

## Notes

The scripts auto-detect the H5 site/group, reflectance cube, wavelength array,
map metadata, and matching H5 tile for each point. Raw `.h5` files and generated
outputs are intentionally not tracked in Git.
