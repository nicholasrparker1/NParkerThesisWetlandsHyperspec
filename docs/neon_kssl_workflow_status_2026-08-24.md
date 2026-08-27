# NEON–KSSL workflow status — 24 August 2026

## Research objective

Develop a reproducible workflow that (1) identifies confidently exposed soil
in airborne hyperspectral imagery and then (2) evaluates whether exposed-soil
spectra can be related to KSSL laboratory soil measurements and hydric-soil
evidence. The exposed-soil model is a screening mask, not a hydric-soil
classifier and not a regulatory wetland delineation.

## Chronological progress

1. **KSSL database audit.** Traced projects, pedons, horizons, laboratory
   properties, coordinates, and MIR records; documented coverage and methods.
2. **Laboratory-property exploration.** Evaluated property completeness,
   depth patterns, correlations, and multivariate gradients. Chemistry is
   informative but does not constitute a direct hydric label.
3. **MT–ND spatial evidence.** Connected surface KSSL samples to SSURGO hydric
   class and NWI polygons. These sources provide contextual evidence with
   different meanings and spatial scales.
4. **KSSL MIR preparation.** Quality-screened replicate scans and averaged
   technical replicates to one laboratory MIR spectrum per sample.
5. **WOOD 2025 exposed-soil pilot.** Used 1 m NEON bidirectional surface
   reflectance to create balanced candidate/noncandidate review points and
   manually labeled soil, vegetation, built/road, and uncertain observations.
6. **Pilot-model assessment.** Compared the initial NDVI/MNDWI rule with a
   full-spectrum model under spatially grouped validation. The spectrum is
   promising for exposed-soil screening, particularly in the VNIR, but the
   2025 result is development evidence rather than an independent test.
7. **WOOD 2023 temporal holdout prepared.** Exported an independent 2023 RGB
   image and 150 balanced validation locations. No 2023 labels have yet been
   used to tune the method.

## Verified WOOD 2023 inputs

- RGB image: `data/raw/NEON/WOOD_2023/WOOD_2023_RGB_validation_image.tif`
- Holdout table:
  `data/raw/NEON/WOOD_2023/WOOD_2023_temporal_holdout_points.csv`
- Image integrity: 9,997 × 10,030 pixels, 3 bands, 1 m pixels, EPSG:32614.
- Table integrity: 150 locations, complete coordinates and indices, with 75
  predicted candidates and 75 predicted noncandidates.
- Preliminary meeting subset:
  `outputs/tables/neon_wood_bare_soil/WOOD_2023_preliminary_blind_label_subset_40.csv`
  (20 locations from each prediction stratum; deterministic seed 2023).

## Current evidence

- The 2025 labeling set contains 150 reviewed pixels, but only 82 received
  clear soil/nonsoil labels; 68 were uncertain. Performance must therefore be
  reported together with labelability/coverage.
- The original index rule achieved approximately 0.80 balanced accuracy on
  the clear 2025 labels and confused roads/built surfaces with soil.
- A full-spectrum, spatially grouped model achieved approximately 0.94 mean
  balanced accuracy on the clear 2025 labels. This is encouraging but may be
  optimistic because the sample is small and selected.
- VNIR-only discrimination was at least as stable as the full spectrum in the
  pilot. This supports exposed-cover discrimination; it does not yet show
  sensitivity to hydric soil chemistry.
- NEON water-vapor absorption/fill bands must be removed before modeling.
  These are invalid measurements, not soil absorption features.

## Independent-test protocol

1. Hide `predicted_bare_soil` while reviewing 2023 locations.
2. Use the same labels as 2025: `soil`, `vegetation`, `road_built`, or
   `uncertain`, with confidence and short notes where useful.
3. Use the 40-point subset only for a preliminary meeting result.
4. Complete all 150 points before reporting the temporal holdout as final.
5. Do not tune thresholds, bands, or model settings using the 2023 labels.
6. Score soil versus vegetation/road; report uncertain as abstention.
7. Report balanced accuracy, soil precision, soil recall, confusion matrix,
   road false-positive rate, and retained/abstained fractions.

Provisional project decision gates—not regulatory or literature standards—are
balanced accuracy >= 0.85, soil precision >= 0.80, soil recall >= 0.80, and
road/built false-positive rate <= 0.20. Failure should trigger diagnosis and a
predeclared second model version, not post-hoc editing of the holdout result.

## Critical limitations

- The balanced 75/75 design evaluates discrimination but cannot estimate the
  prevalence of bare soil across the landscape.
- A visually assigned 1 m pixel can still be mixed or ambiguous.
- RGB interpretation is imperfect; confidence and abstention are necessary.
- KSSL MIR and airborne VNIR–SWIR occupy different spectral domains. They
  should be linked through common samples/properties and mechanisms, not by
  treating their wavelengths as directly interchangeable.
- SSURGO and NWI are contextual evidence layers, not pixel-scale ground truth.
- The KSSL–NEON sample crosswalk and coordinate precision must be established
  before claiming direct laboratory-to-airborne calibration.

## Next decision sequence

1. Obtain a preliminary blind score from 40 WOOD 2023 points for the meeting.
2. Complete and lock the 150-point temporal holdout.
3. If the holdout passes, freeze and package the exposed-soil mask.
4. Extract full valid NEON spectra only for confident exposed-soil pixels.
5. Resolve KSSL–NEON pedon/sample correspondence and spatial proximity.
6. Test prediction of shared soil properties before testing hydric evidence.
7. Expand to additional sites/states only after the WOOD workflow transfers.

