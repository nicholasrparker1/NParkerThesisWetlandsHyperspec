from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


#these need to be changed based on the h5 file being inspected. 

DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
OUTPUTS = PROJECT_ROOT / "outputs"
FIGURES = OUTPUTS / "figures"
TABLES = OUTPUTS / "tables"

REFLECTANCE_PATH = "NOGP/Reflectance/Reflectance_Data"
WAVELENGTH_PATH = "NOGP/Reflectance/Metadata/Spectral_Data/Wavelength"

ATMOSPHERIC_WINDOWS_BROAD_NM = [
    (1340.0, 1450.0),
    (1800.0, 1950.0),
    (2400.0, float("inf")),
]

ATMOSPHERIC_WINDOWS_NARROW_NM = [
    (920.0, 960.0),
    (1110.0, 1145.0),
]

for p in [DATA_RAW, DATA_PROCESSED, FIGURES, TABLES]:
    p.mkdir(parents=True, exist_ok=True)

