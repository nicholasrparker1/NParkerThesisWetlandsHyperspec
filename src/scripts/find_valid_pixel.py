import h5py
import numpy as np
from src.config import DATA_RAW

CUBE = "ROCX/Reflectance/Reflectance_Data"

def main():
    h5_file = list(DATA_RAW.glob("*.h5"))[0]
    print("Using:", h5_file)

    with h5py.File(h5_file, "r") as f:
        cube = f[CUBE]  # (rows, cols, bands)
        fill = -9999

        # Sample band 0 with a stride to find any valid location quickly
        stride = 20
        band0 = cube[0::stride, 0::stride, 0]  # 2D sample

        valid = np.argwhere(band0 != fill)
        if valid.size == 0:
            print("No valid pixels found in sampled grid. Try lowering stride.")
            return

        rr_s, cc_s = valid[0]
        r = int(rr_s * stride)
        c = int(cc_s * stride)

        print(f"Found valid pixel (approx): r={r}, c={c}, band0={cube[r,c,0]}")

if __name__ == "__main__":
    main()
