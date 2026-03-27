from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from src.models.moisture_baseline import (
    extract_simple_features,
    fit_baseline_model,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", type=str, default="data/processed/moisture_training_data.npz")
    ap.add_argument("--outfig", type=str, default="outputs/moisture_baseline_fit.png")
    args = ap.parse_args()

    npz_path = Path(args.npz)
    if not npz_path.exists():
        raise FileNotFoundError(f"NPZ not found: {npz_path}")

    data = np.load(npz_path)
    wavelengths_nm = data["wavelengths_nm"]
    X_spectra = data["X_spectra"]
    y_moisture = data["y_moisture"]

    if len(y_moisture) < 2:
        raise RuntimeError("Need at least 2 samples to run the prototype baseline fit.")

    X_feat, feat_names = extract_simple_features(wavelengths_nm, X_spectra)
    result = fit_baseline_model(X_feat, y_moisture, feat_names)

    y_pred = result.fitted_model.predict(X_feat).ravel()

    print("\n=== Prototype moisture baseline ===")
    print("Samples:", len(y_moisture))
    print("Features:", result.feature_names)
    print("Intercept:", result.intercept)
    print("Coefficients:")
    for name, coef in zip(result.feature_names, result.coefficients):
        print(f"  {name}: {coef:.6f}")

    print("\nMeasured vs fitted:")
    for i, (yt, yp) in enumerate(zip(y_moisture, y_pred), start=1):
        print(f"  sample {i}: measured={yt:.6f}, fitted={yp:.6f}")

    plt.figure(figsize=(5.2, 5.2))
    plt.scatter(y_moisture, y_pred, s=80)
    mn = float(min(np.min(y_moisture), np.min(y_pred)))
    mx = float(max(np.max(y_moisture), np.max(y_pred)))
    plt.plot([mn, mx], [mn, mx], linestyle="--")
    plt.xlabel("Measured moisture")
    plt.ylabel("Fitted moisture")
    plt.title("Prototype moisture fit (2-point test)")
    plt.grid(True, linestyle="--", alpha=0.3)
    plt.tight_layout()

    outfig = Path(args.outfig)
    outfig.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(outfig, dpi=300)
    plt.show()

    print("\nSaved figure:", outfig)
    print("\nNOTE: This is only a workflow test with 2 points, not a real validated model.")


if __name__ == "__main__":
    main()