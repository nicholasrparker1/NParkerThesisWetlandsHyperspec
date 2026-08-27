# Hydric Soil Likelihood Roadmap

## Research Direction

The long-term objective is not to classify hydric soils directly from airborne
hyperspectral imagery. Hydric soils are an integrated field condition produced
by prolonged saturation, redox processes, organic matter accumulation, and other
soil-forming factors. They are not expected to have one universal spectral
signature.

The project is therefore moving toward an evidence-based framework:

1. Estimate measurable soil properties from hyperspectral reflectance.
2. Validate those estimates against field or laboratory measurements.
3. Combine validated property estimates with wetland and environmental context.
4. Produce a continuous hydric soil likelihood score with uncertainty, rather
   than a hard hydric/non-hydric classification.

## Near-Term Workflow

The immediate priority is to build a clean, auditable master dataset where each
row represents a sampled location with:

- field or laboratory soil measurements
- geographic coordinates
- matched NEON AOP reflectance observations
- cleaned reflectance bands
- surface-cover usability flags
- wetland-context attributes
- provenance columns for tile, ROI, snap distance, and processing choices

This dataset is the foundation for any later modeling.

## Evidence Layers

Potential evidence layers include:

- predicted soil organic matter
- predicted carbon
- predicted nitrogen
- moisture-related spectral features
- iron or redox-related laboratory variables, if available
- surface-cover confidence, especially bare-soil usability
- NWI wetland context and wetland proximity, with "close by" defined as
  inside or within 10 m of a mapped NWI wetland polygon
- topographic variables
- SAR, LiDAR, hydrology, or climate variables added later

Each layer should contribute evidence and uncertainty. No single layer should be
treated as a final hydric-soil decision.

## Modeling Philosophy

The preferred modeling sequence is hierarchical:

1. Screen points for spectral usability.
2. Estimate physically meaningful soil properties.
3. Validate property models across sites, not only within one location.
4. Combine predicted properties and context into hydric likelihood.

This keeps the intermediate variables interpretable and independently
testable.

## Current Code Roles

Core extraction and plotting:

- `src/scripts/check_setup.py`
- `src/scripts/pull_spectra_overlay.py`
- `src/scripts/pull_spectrum_latlon.py`

Soil screening and context:

- `src/scripts/classify_point_cover.py`
- `src/models/cover_classification.py`
- `src/scripts/build_wetland_context.py`
- `src/scripts/classify_wetland_context_cover.py`

Ground-truth and spectral tables:

- `src/scripts/prepare_neon_soil_chemistry_table.py`
- `src/scripts/build_soil_spectral_table.py`
- `src/scripts/build_hydric_evidence_table.py`

Property screening and provisional models:

- `src/scripts/analyze_soil_spectral_correlations.py`
- `src/scripts/build_moisture_training_table.py`
- `src/scripts/run_moisture_baseline.py`

Optional exploratory wetness diagnostics:

- `src/scripts/compare_aerial_wetness_methods.py`
- `src/models/marmit.py`
