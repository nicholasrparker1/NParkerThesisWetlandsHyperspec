from pathlib import Path
import csv
import numpy as np
import matplotlib.pyplot as plt
from src.preprocess import clean_spectrum, spectrum_for_plot


from src.io_hyperspectral import (
    discover_neon_h5_paths,
    get_wavelengths_from_file,
    get_map_info_and_epsg_from_file,
    extract_spectrum_from_latlon,
)

# ============================================================
# USER INPUTS
# Change only this section
# ============================================================

FILE_PATH = Path("data/raw/NEON_D01_ROCX_DP1_L001-1_20250905_bidirectional_reflectance.h5")



POINTS = [
    {"id": "TestValid", "lat": 43.16743833650844, "lon": -77.50206758200544},
]

ROI_SIZE = 3          # 1 = single pixel, 3 = 3x3, 5 = 5x5
SNAP_RADIUS = 20      # search radius in pixels if target pixel is invalid
REDUCTION = "median"  # "median" or "mean"

OUTPUT_PLOT = Path("outputs/figures/extracted_spectra.png")
OUTPUT_CSV = Path("outputs/tables/extracted_spectra.csv")


# ============================================================
# Main
# Do not change below for normal use
# ============================================================

def validate_inputs():
    if ROI_SIZE < 1 or ROI_SIZE % 2 == 0:
        raise ValueError("ROI_SIZE must be an odd integer: 1, 3, 5, ...")

    if REDUCTION not in {"median", "mean"}:
        raise ValueError("REDUCTION must be 'median' or 'mean'.")

    if not FILE_PATH.exists():
        raise FileNotFoundError(f"Input file not found: {FILE_PATH}")

    for p in POINTS:
        if "id" not in p:
            raise ValueError(f"Each point must have an 'id': {p}")

        has_latlon = ("lat" in p and "lon" in p)
        has_xy = ("x" in p and "y" in p)

        if not (has_latlon or has_xy):
            raise ValueError(
                f"Point {p['id']} must have either lat/lon or x/y coordinates."
            )


def main():
    validate_inputs()

    print("Input file:", FILE_PATH)
    print("Number of points:", len(POINTS))
    print("ROI size:", ROI_SIZE)
    print("Snap radius:", SNAP_RADIUS)
    print("Reduction:", REDUCTION)
    print("Output plot:", OUTPUT_PLOT)
    print("Output CSV:", OUTPUT_CSV)

    paths = discover_neon_h5_paths(str(FILE_PATH))
    wavelengths = get_wavelengths_from_file(str(FILE_PATH))
    map_info, epsg_code = get_map_info_and_epsg_from_file(str(FILE_PATH))

    print("\nDiscovered file metadata:")
    print("Site:", paths["site"])
    print("Reflectance path:", paths["reflectance_path"])
    print("Wavelength path:", paths["wavelength_path"])
    print("Map info path:", paths["map_info_path"])
    print("EPSG path:", paths["epsg_path"])
    print("Bands:", len(wavelengths))
    print("EPSG code:", epsg_code)
    print("Map origin x0:", map_info["x0"])
    print("Map origin y0:", map_info["y0"])

    extracted = []

    print("\nExtraction results:")
    for p in POINTS:
        if "lat" in p and "lon" in p:
            result = extract_spectrum_from_latlon(
                str(FILE_PATH),
                p["lat"],
                p["lon"],
                roi_size=ROI_SIZE,
                snap_radius=SNAP_RADIUS,
            )

            if not result["inside"]:
                print(
                    f"{p['id']}: row={result['row']}, col={result['col']}, "
                    f"inside=False"
                )
                continue

            extracted.append(
                {
                    "id": p["id"],
                    "lat": p["lat"],
                    "lon": p["lon"],
                    "used_row": result["used_row"],
                    "used_col": result["used_col"],
                    "bounds": result["bounds"],
                    "wavelengths": result["wavelengths"],
                    "spectrum": result["spectrum"],
                }
            )

            print(
                f"{p['id']}: used_row={result['used_row']}, "
                f"used_col={result['used_col']}, "
                f"bounds={result['bounds']}, "
                f"bands={len(result['wavelengths'])}, "
                f"first5={result['spectrum'][:5]}"
            )
        else:
            print(f"{p['id']}: projected x/y mode not connected yet")

    print(f"\nStored extracted spectra: {len(extracted)}")

    if extracted:
        OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

        with open(OUTPUT_CSV, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "lat", "lon", "used_row", "used_col", "wavelength_nm", "reflectance"])

            for item in extracted:
                w = np.asarray(item["wavelengths"])
                s = np.asarray(item["spectrum"])

                for wi, si in zip(w, s):
                    writer.writerow([
                        item["id"],
                        item["lat"],
                        item["lon"],
                        item["used_row"],
                        item["used_col"],
                        float(wi),
                        float(si) if np.isfinite(si) else "",
                    ])

        print(f"Saved CSV: {OUTPUT_CSV}")

        OUTPUT_PLOT.parent.mkdir(parents=True, exist_ok=True)

        plt.figure(figsize=(10, 5))
        for item in extracted:
            w = np.asarray(item["wavelengths"]).astype(float)
            s = np.asarray(item["spectrum"]).astype(float)

            wl_plot, spec_plot, _ = spectrum_for_plot(
                w,
                s,
                include_narrow_bad_bands=True,
                max_reflectance=1.2,
            )

            plt.plot(wl_plot, spec_plot, linewidth=2, label=item["id"])

        for a, b in [(920, 960), (1110, 1145), (1340, 1450), (1800, 1950)]:
            plt.axvspan(a, b, alpha=0.12)

        plt.xlabel("Wavelength (nm)")
        plt.ylabel("Reflectance")
        plt.title(f"Extracted spectra (ROI={ROI_SIZE}) | Atmospheric bands masked")
        plt.grid(True, linestyle="--", alpha=0.3)
        plt.legend()
        plt.tight_layout()
        plt.savefig(OUTPUT_PLOT, dpi=300)
        plt.close()

        print(f"Saved plot: {OUTPUT_PLOT}")

if __name__ == "__main__":
    main()