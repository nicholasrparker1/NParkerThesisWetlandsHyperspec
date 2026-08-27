# Airborne Bare-Soil Readiness Protocol

## Purpose

This protocol defines the work that can be completed before the ACES airborne
hyperspectral data arrive. The bare-soil screen is a quality-control step: it
determines where retrieval of soil properties is defensible. It does not
determine whether a soil is hydric.

## Bare-soil evidence

The initial screen uses sensor bands nearest 560, 665, 860, 1640, and 2200 nm.
It computes NDVI, NDWI, MNDWI, NDMI, visible brightness, and NIR-SWIR
brightness. Pixels are rejected when they appear to be:

- green vegetation (high NDVI)
- mixed vegetation (moderate NDVI)
- open water (water indices plus low NIR/SWIR reflectance)
- shadow or invalid/low-signal data

Remaining low-vegetation, non-water pixels are labeled `bare_soil_candidate`.
This is intentionally a candidate class rather than confirmed bare soil.

## Validation required after delivery

1. Create a stratified visual sample of at least 50 pixels per provisional
   class using the ACES RGB composite and, when available, higher-resolution
   imagery.
2. Manually label bare soil, vegetation, residue, water, shadow, built surface,
   and uncertain mixtures.
3. Report the confusion matrix, precision, recall, and sample counts. Bare-soil
   precision is the primary acceptance metric because contaminated spectra can
   bias property retrieval.
4. Tune thresholds using training locations only; reserve spatially separate
   areas for testing.
5. Retain a continuous soil-likelihood value and the reason for every rejected
   pixel.

## Important confounders

- dry crop residue can resemble bright soil
- wet soil can resemble water or shadow
- dark organic soil can resemble shadow
- senescent vegetation may have low NDVI
- roads and rooftops can resemble bare soil
- mixed pixels near field and wetland boundaries are unreliable

Use land-cover masks, spatial texture, and manual review to address these
confounders. No single spectral-index threshold is sufficient.

## ACES delivery checklist

Obtain and record:

- sensor and instrument model
- acquisition date and local time
- flight footprint and flight-line geometry
- altitude above ground
- pixel size and spectral sampling
- wavelength centers and band widths
- radiance versus surface-reflectance processing level
- atmospheric, BRDF, and topographic corrections
- bad-band and quality masks
- coordinate reference system and geolocation accuracy
- nodata/scaling conventions
- RGB imagery, if collected
- calibration panels or field spectra, if collected

## Analysis sequence when ACES arrives

1. Validate geometry, wavelengths, scaling, and quality metadata.
2. Remove invalid and atmospheric absorption bands.
3. Generate RGB, NDVI, water-index, brightness, and quality layers.
4. Produce the provisional bare-soil candidate mask.
5. Validate and tune the mask with spatially separated manual labels.
6. Extract spectra from homogeneous bare-soil neighborhoods rather than single
   boundary pixels.
7. Link spectra to field/KSSL samples only when positional, temporal, and
   surface-condition compatibility is defensible.
8. Predict soil properties first; combine them with NWI, SSURGO, terrain, and
   hydrology only afterward.

## Deliverables possible before ACES

- tested cover-feature calculations
- documented input schema and quality flags
- KSSL MIR property models and geographic validation
- GIS evidence table and version-0 evidence score
- predefined spatial holdout and evaluation strategy
- presentation-ready methods diagram and limitations statement

