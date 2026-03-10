from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

REFLECTANCE_PATH = "ROCX/Reflectance/Reflectance_Data" 
WAVELENGTH_PATH = "ROCX/Reflectance/Metadata/Spectral_Data/Wavelength"
#these need to be changed based on the h5 file being inspected. 

DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
OUTPUTS = PROJECT_ROOT / "outputs"
FIGURES = OUTPUTS / "figures"
TABLES = OUTPUTS / "tables"

for p in [DATA_RAW, DATA_PROCESSED, FIGURES, TABLES]:
    p.mkdir(parents=True, exist_ok=True)

