# Hydric Soil Evidence Tool: Version 0 Specification

## Purpose

The tool will combine interpretable laboratory, spectral, and mapped context
into a continuous hydric-soil evidence product. It will not issue a regulatory
hydric-soil determination or treat SSURGO/NWI as field-confirmed truth.

## Unit of Analysis

One row represents one georeferenced surface-soil sample or one airborne image
pixel/region of interest. Subsurface layers may be retained for research but
must be explicitly flagged and excluded from surface-only retrieval models.

## Required Inputs

- stable sample or pixel identifier
- latitude and longitude with coordinate-reference provenance
- surface-cover usability flag
- provenance for source file, acquisition, extraction window, and processing

## Optional Evidence Inputs

- laboratory measurements: carbon, nitrogen, clay, iron, pH, water retention,
  CEC, and related properties
- laboratory MIR spectrum or MIR-derived property estimates
- airborne VNIR-SWIR reflectance and derived property estimates
- NWI intersection, wetland distance, and wetland class
- SSURGO hydric percentage/class
- topographic, hydrologic, SAR, LiDAR, or climate context

## Processing Stages

1. Validate identifiers, coordinates, units, and provenance.
2. Screen surface cover and spectral quality.
3. Estimate independently testable soil properties from usable spectra.
4. Attach mapped wetland and soil context without treating it as truth.
5. Calculate evidence components and uncertainty.
6. Return continuous evidence and confidence, plus all component values.

## Version 0 Outputs

- `hydric_evidence_score`: continuous 0-1 research score
- `evidence_confidence`: continuous 0-1 data-support score
- `evidence_category`: insufficient, low, moderate, or high evidence
- component columns for spectral, laboratory, NWI, and SSURGO evidence
- missing-evidence and quality-control flags
- model/version identifier and complete provenance

The evidence score and confidence must remain separate. A high score supported
by one weak layer must not be presented as high confidence.

## Current KSSL Reference Cohort

- 404 Montana-North Dakota georeferenced surface samples
- 398 samples with usable MIR spectra after replicate quality control
- 181 samples overlapping SSURGO hydric evidence
- 18 samples intersecting NWI polygons
- 14 samples supported by both mapped sources

These categories are weak reference evidence. They are suitable for exploratory
association tests, not for declaring hydric or non-hydric ground truth.

## Validation Requirements

- hold out complete sampling projects during model development
- report state/site geographic holdouts
- report class balance, missingness, and usable sample counts
- report rank agreement and calibration error separately
- prohibit random replicate-level train/test splitting
- retain an untouched field-confirmed validation set when available

## Current Scientific Status

MIR predicts several laboratory bridge properties well, including carbon, clay,
CEC, pH, and water retention. MIR association with mapped hydric evidence is
weaker and does not currently transfer reliably between Montana and North
Dakota. Version 0 must therefore expose evidence components and uncertainty;
it must not provide a universal MIR-only hydric classification.

## Next Implementation Milestone

Create a command-line scoring module that accepts the standardized evidence
table, validates its schema, computes transparent provisional components, and
writes a scored table plus a machine-readable run summary. Initial scoring will
be explicitly labeled exploratory until weights are calibrated with independent
field-confirmed hydric indicators.
