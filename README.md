# Wetlands Hyperspectral Soil Evidence Quick Start

This repo extracts and screens NEON-style airborne hyperspectral reflectance at
soil and field point locations. The near-term goal is to build a defensible
evidence table that links measured soil properties, cleaned spectra, surface
cover usability, and wetland context. Longer term, these evidence layers can
support a continuous hydric soil likelihood framework rather than a direct
hydric/non-hydric image classifier.

See `docs/hydric_soil_likelihood_roadmap.md` for the research direction.

## 1. Get The Code

Open PowerShell where you want the project folder to live, then run:

```powershell
git clone https://github.com/nicholasrparker1/NParkerThesisWetlandsHyperspec.git
cd NParkerThesisWetlandsHyperspec
```

## 2. Install

From the repo folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 3. Add Data

Put hyperspectral reflectance files here:

```text
data/raw/
```

The files should be NEON-style `.h5` reflectance files.

Raw NEON H5 files are large and are not tracked in Git. Download them from NEON
and keep them local in `data/raw/`.

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

## 4. Check Setup

For a guided menu, run:

```powershell
.\.venv\Scripts\python.exe -m src.scripts.menu
```

The menu lists common workflows, asks for only the needed inputs, previews the
exact reproducible command, and then runs the same scripts documented below.

Or run the setup check directly:

```powershell
.\.venv\Scripts\python.exe -m src.scripts.check_setup --points data/processed/transect_points.csv
```

## 5. Plot Reflectance

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

## Evidence Table

After extracting soil spectra and screening cover, build a compact evidence
table for later modeling:

```powershell
.\.venv\Scripts\python.exe -m src.scripts.build_hydric_evidence_table --soil-spectral-table data/processed/soil_spectral_table.csv --wetland-context-table data/processed/NEON_Soil_Wetland_Context_Table.xlsx --out data/processed/hydric_evidence_table.csv
```

NWI wetland proximity is treated as evidence, not confirmation. The strict
"close by" flag means a soil point is inside or within 10 m of a mapped NWI
wetland polygon.

## No-Calibration Wetness Comparison

For bare-soil aerial data without ground calibration, use the comparison script
to generate two relative wetness products:

1. Baseline spectral proxies from SWIR/NIR contrast and continuum shape.
2. MARMIT-style physics proxies from a dry reference attenuated by water:
   `L`, wet fraction `epsilon`, and `phi = L * epsilon`.

These outputs are relative wetness indicators, not calibrated volumetric soil
moisture.

Example focused run:

```powershell
.\.venv\Scripts\python.exe -m src.scripts.compare_aerial_wetness_methods `
  --points data/processed/marmit_calibration_table_updated.csv `
  --dry-id 46 `
  --include-ids 46,44 `
  --roi 3 `
  --snap 40 `
  --plot-target-id 44 `
  --out-csv data/processed/aerial_wetness_method_comparison_smoke.csv `
  --out-scatter outputs/figures/aerial_wetness_method_comparison_smoke.png `
  --out-fit outputs/figures/marmit_mixed_fit_point_44.png
```

Important output columns:

```text
baseline_relative_wetness  standardized average of simple spectral proxies
marmit_L_um                fitted effective water-film thickness
marmit_epsilon             fitted wet surface fraction
marmit_phi_um              L * epsilon, a relative equivalent-water proxy
marmit_hit_L_lower_bound   fit landed on the lower search limit
marmit_hit_L_upper_bound   fit landed on the upper search limit
```

Boundary hits mean the physics fit is underconstrained or the dry reference is
not a good spectral analog for that target. Use those rows as diagnostics, not
as reliable retrievals.

