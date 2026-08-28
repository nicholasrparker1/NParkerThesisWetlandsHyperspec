from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
ND = (
    ROOT
    / "outputs"
    / "tables"
    / "kssl_neon_linkage"
    / "north_dakota_pilot"
)

INPUT = ND / "nd_reference_lab_pedon_summary.csv"

OUT = ND / "nd_texture_controlled_property_results.csv"
MATCHES = ND / "nd_texture_nearest_neighbors.csv"


PROPERTIES = [
    "estimated_organic_carbon_pct",
    "total_nitrogen_pct",
    "total_sulfur_pct",
    "fe_dithionite_pct",
    "fe_oxalate_pct",
    "al_dithionite_pct",
    "al_oxalate_pct",
    "cec_nh4oac_cmol_kg",
    "water_retention_15bar_pct",
    "ph_water",
    "ph_cacl2",
]


def safe_slope(x, y):
    mask = x.notna() & y.notna()

    if mask.sum() < 3:
        return np.nan, np.nan

    x2 = x[mask].astype(float)
    y2 = y[mask].astype(float)

    if x2.std(ddof=0) == 0:
        return np.nan, np.nan

    slope, intercept = np.polyfit(x2, y2, 1)

    return slope, intercept


def main():

    df = pd.read_csv(INPUT)

    hydric = df[
        df["reference_group"] == "HYDRIC_REFERENCE"
    ].copy()

    nonhydric = df[
        df["reference_group"] == "NONHYDRIC_REFERENCE"
    ].copy()

    print("Texture-controlled North Dakota analysis")
    print("=" * 72)
    print(f"Hydric reference pedons: {len(hydric)}")
    print(f"Nonhydric reference pedons: {len(nonhydric)}")

    # ---------------------------------------------------------
    # 1. Nearest-neighbor matching on texture only.
    #
    # Standardize clay/sand/silt across the full reference set,
    # then find the nearest nonhydric pedon for every hydric pedon.
    #
    # Matching uses NO chemistry.
    # ---------------------------------------------------------

    texture_vars = ["clay_pct", "sand_pct", "silt_pct"]

    tex = df[texture_vars].apply(
        pd.to_numeric,
        errors="coerce",
    )

    means = tex.mean()
    stds = tex.std(ddof=0).replace(0, np.nan)

    z = (tex - means) / stds

    for col in texture_vars:
        df[f"z_{col}"] = z[col]

    hydric = df[
        df["reference_group"] == "HYDRIC_REFERENCE"
    ].copy()

    nonhydric = df[
        df["reference_group"] == "NONHYDRIC_REFERENCE"
    ].copy()

    match_rows = []

    for _, h in hydric.iterrows():

        candidates = nonhydric.copy()

        d2 = np.zeros(len(candidates))

        valid_dimensions = np.zeros(len(candidates))

        for var in texture_vars:

            hz = h[f"z_{var}"]
            nz = pd.to_numeric(
                candidates[f"z_{var}"],
                errors="coerce",
            )

            valid = nz.notna() & pd.notna(hz)

            d2 += np.where(
                valid,
                (nz - hz) ** 2,
                0,
            )

            valid_dimensions += valid.astype(int)

        candidates["texture_distance"] = np.where(
            valid_dimensions > 0,
            np.sqrt(d2),
            np.nan,
        )

        candidates = candidates.sort_values(
            "texture_distance"
        )

        best = candidates.iloc[0]

        row = {
            "hydric_pedon": h["user_pedon_id"],
            "nonhydric_match": best["user_pedon_id"],
            "texture_distance": best["texture_distance"],
            "hydric_clay_pct": h["clay_pct"],
            "nonhydric_clay_pct": best["clay_pct"],
            "hydric_sand_pct": h["sand_pct"],
            "nonhydric_sand_pct": best["sand_pct"],
            "hydric_silt_pct": h["silt_pct"],
            "nonhydric_silt_pct": best["silt_pct"],
        }

        for prop in PROPERTIES:

            hv = pd.to_numeric(
                pd.Series([h.get(prop)]),
                errors="coerce",
            ).iloc[0]

            nv = pd.to_numeric(
                pd.Series([best.get(prop)]),
                errors="coerce",
            ).iloc[0]

            row[f"hydric_{prop}"] = hv
            row[f"nonhydric_{prop}"] = nv

            row[f"delta_{prop}"] = (
                hv - nv
                if pd.notna(hv) and pd.notna(nv)
                else np.nan
            )

        match_rows.append(row)

    matches = pd.DataFrame(match_rows)
    matches.to_csv(MATCHES, index=False)

    # ---------------------------------------------------------
    # 2. Residualize each property against clay percentage.
    #
    # Fit the property~clay relationship using NONHYDRIC
    # references only. Then calculate how far each hydric pedon
    # lies above/below the nonhydric texture expectation.
    #
    # This is exploratory, not a causal model.
    # ---------------------------------------------------------

    results = []

    clay_non = pd.to_numeric(
        nonhydric["clay_pct"],
        errors="coerce",
    )

    for prop in PROPERTIES:

        y_non = pd.to_numeric(
            nonhydric[prop],
            errors="coerce",
        )

        slope, intercept = safe_slope(
            clay_non,
            y_non,
        )

        residuals = []

        if pd.notna(slope):

            for _, h in hydric.iterrows():

                clay = pd.to_numeric(
                    pd.Series([h["clay_pct"]]),
                    errors="coerce",
                ).iloc[0]

                observed = pd.to_numeric(
                    pd.Series([h[prop]]),
                    errors="coerce",
                ).iloc[0]

                if pd.notna(clay) and pd.notna(observed):

                    expected = intercept + slope * clay
                    residuals.append(observed - expected)

        residuals = pd.Series(
            residuals,
            dtype=float,
        )

        pair_delta_col = f"delta_{prop}"

        pair_deltas = (
            pd.to_numeric(
                matches[pair_delta_col],
                errors="coerce",
            ).dropna()
            if pair_delta_col in matches
            else pd.Series(dtype=float)
        )

        results.append(
            {
                "property": prop,
                "nonhydric_texture_slope_per_clay_pct":
                    slope,
                "n_hydric_residuals": len(residuals),
                "median_hydric_residual_vs_nonhydric_clay_model":
                    residuals.median()
                    if len(residuals)
                    else np.nan,
                "min_hydric_residual":
                    residuals.min()
                    if len(residuals)
                    else np.nan,
                "max_hydric_residual":
                    residuals.max()
                    if len(residuals)
                    else np.nan,
                "n_texture_pairs": len(pair_deltas),
                "median_matched_pair_delta_hydric_minus_nonhydric":
                    pair_deltas.median()
                    if len(pair_deltas)
                    else np.nan,
                "matched_pairs_positive_delta":
                    int((pair_deltas > 0).sum())
                    if len(pair_deltas)
                    else 0,
                "matched_pairs_negative_delta":
                    int((pair_deltas < 0).sum())
                    if len(pair_deltas)
                    else 0,
            }
        )

    results = pd.DataFrame(results)

    results.to_csv(OUT, index=False)

    # ---------------------------------------------------------
    # Console output
    # ---------------------------------------------------------

    print("\nTexture nearest neighbors:")
    print(
        matches[
            [
                "hydric_pedon",
                "nonhydric_match",
                "texture_distance",
                "hydric_clay_pct",
                "nonhydric_clay_pct",
                "hydric_sand_pct",
                "nonhydric_sand_pct",
            ]
        ].to_string(index=False)
    )

    print("\nTexture-controlled property results:")
    print(
        results[
            [
                "property",
                "median_hydric_residual_vs_nonhydric_clay_model",
                "median_matched_pair_delta_hydric_minus_nonhydric",
                "matched_pairs_positive_delta",
                "matched_pairs_negative_delta",
            ]
        ].to_string(index=False)
    )

    print("\nWrote:")
    print(MATCHES)
    print(OUT)


if __name__ == "__main__":
    main()