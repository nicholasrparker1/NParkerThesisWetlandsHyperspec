# WOOD 2025 bare-soil screening pilot validation

## Purpose and design

The bare-soil screen identifies pixels where later soil-property retrieval is
potentially defensible; it is not itself a hydric-soil classifier. We used the
18 June 2025 NEON WOOD bidirectional surface-reflectance mosaic (1 m pixels) as
an analogue for the forthcoming ACES imagery.

Version 0 used NDVI < 0.25, MNDWI < 0, NIR reflectance > 0.04, and a minimum
connected region of 9 pixels. The validation sample contains 150 visually
reviewed pixels, balanced between 75 predicted bare-soil and 75 predicted
non-soil locations. Therefore, its metrics evaluate discrimination but do not
estimate landscape prevalence.

## Results

Manual review produced 26 soil, 46 vegetation, 10 road or built-surface, and 68
uncertain labels. Excluding uncertain points, the screen achieved 0.82 accuracy,
0.80 balanced accuracy, 0.69 bare-soil precision, 0.77 bare-soil recall, and
0.84 non-soil specificity.

The screen found 20 of 26 clearly labeled soil pixels and rejected all 46 clear
vegetation pixels. Nine of ten road or built-surface pixels were false
positives. Version 1 should therefore focus on separating exposed soil from
impervious surfaces, residue, and mixtures—not simply strengthen vegetation
rejection.

## Limitations and next step

The 45.3% uncertain rate captures genuine RGB interpretation ambiguity. These
labels have been inspected to diagnose errors, so this is a development/pilot
set rather than an untouched final test set. Version 1 may use it for feature
development, but final performance must use new, spatially separated labels,
preferably within the ACES footprint. Uncertain pixels should remain excluded
from soil-property retrieval.

Run the reproducible evaluation with:

```powershell
.\.venv\Scripts\python.exe scripts\neon\evaluate_wood_bare_soil_validation.py
```

Outputs are written to `outputs/tables/neon_wood_bare_soil/` and
`outputs/figures/neon_wood_bare_soil/`.
