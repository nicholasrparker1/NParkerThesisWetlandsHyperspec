// NEON WOOD 2025 airborne hyperspectral setup
//
// Citation template:
// NEON (National Ecological Observatory Network). Spectrometer orthorectified
// surface bidirectional reflectance - mosaic (DP3.30006.002), provisional data.
// Dataset accessed from Google Earth Engine on 2026-08-20. Use the DOI printed
// from the image metadata below in the final citation.

var SITE_IMAGE_ID = '2025_WOOD_7';

var reflectance = ee.ImageCollection(
  'projects/neon-prod-earthengine/assets/HSI_REFL/002'
);

var rgb = ee.ImageCollection(
  'projects/neon-prod-earthengine/assets/RGB/001'
);

var woodReflectance = reflectance
  .filter(ee.Filter.eq('system:index', SITE_IMAGE_ID))
  .first();

var woodRgb = rgb
  .filter(ee.Filter.eq('system:index', SITE_IMAGE_ID))
  .first();

// Confirm that both products exist and inspect acquisition dates, processing,
// scaling, wavelength, quality, and DOI metadata before analysis.
print('Selected reflectance image', woodReflectance);
print('Reflectance metadata', woodReflectance.toDictionary());
print('Reflectance band names', woodReflectance.bandNames());
print('Matching RGB image count', rgb.filter(
  ee.Filter.eq('system:index', SITE_IMAGE_ID)
).size());
print('Matching RGB image', woodRgb);

// NEON true-color approximation supplied by the viewer.
var reflectanceRgbVis = {
  min: 103,
  max: 1160,
  bands: ['B053', 'B035', 'B019'],
  gamma: 1
};

Map.addLayer(
  woodReflectance,
  reflectanceRgbVis,
  'WOOD 2025 hyperspectral true color'
);

// Add the high-resolution camera mosaic if an identically indexed product is
// available. This layer is for visual labeling and validation.
Map.addLayer(woodRgb, {}, 'WOOD 2025 RGB camera', false);
Map.centerObject(woodReflectance);

