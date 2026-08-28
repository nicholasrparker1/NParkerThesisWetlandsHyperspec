from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

BASE = (
    ROOT
    / "outputs"
    / "tables"
    / "kssl_neon_linkage"
)

OUT = BASE / "osbs_validation"
OUT.mkdir(parents=True, exist_ok=True)

BRIDGE = BASE / "neon_kssl_hydric_evidence_bridge.csv"
MASTER = BASE / "neon_kssl_master_pedon_horizon_table.csv"
SSURGO = BASE / "neon_kssl_ssurgo_component_matches.csv"


def main():

    bridge = pd.read_csv(BRIDGE, low_memory=False)
    master = pd.read_csv(MASTER, low_memory=False)
    ssurgo = pd.read_csv(SSURGO, low_memory=False)

    # ---------------------------------------------------------
    # Freeze OSBS-region validation cohort:
    # FL107 pedons only.
    #
    # This cohort was selected BEFORE examining validation MIR
    # spectra, based on geography and ground-reference quality.
    # ---------------------------------------------------------

    mask = (
        bridge["user_pedon_id"]
        .fillna("")
        .astype(str)
        .str.contains("FL107", case=False)
    )

    osbs = bridge[mask].copy()

    print("OSBS / FL107 independent validation cohort")
    print("=" * 76)

    print("Total FL107 pedons:", len(osbs))

    # ---------------------------------------------------------
    # Positive references
    # ---------------------------------------------------------

    positive = osbs[
        (osbs["match_confidence"] == "EXACT")
        & (osbs["selected_hydricrating"] == "Yes")
        & osbs["selected_drainagecl"].isin(
            [
                "Poorly drained",
                "Very poorly drained",
            ]
        )
    ].copy()

    # ---------------------------------------------------------
    # Negative references
    #
    # Keep conservative:
    # exact SSURGO nonhydric +
    # moderately well / well / excessively drained.
    # ---------------------------------------------------------

    negative = osbs[
        (osbs["match_confidence"] == "EXACT")
        & (osbs["selected_hydricrating"] == "No")
        & osbs["selected_drainagecl"].isin(
            [
                "Moderately well drained",
                "Well drained",
                "Somewhat excessively drained",
                "Excessively drained",
            ]
        )
    ].copy()

    print("\nHydric reference candidates:")
    print(
        positive[
            [
                "user_pedon_id",
                "nasis_taxon_name",
                "nasis_taxonomy",
                "selected_compname",
                "selected_drainagecl",
                "selected_hydricrating",
                "evidence_class",
            ]
        ].to_string(index=False)
    )

    print("\nNonhydric reference candidates:")
    print(
        negative[
            [
                "user_pedon_id",
                "nasis_taxon_name",
                "nasis_taxonomy",
                "selected_compname",
                "selected_drainagecl",
                "selected_hydricrating",
                "evidence_class",
            ]
        ].to_string(index=False)
    )

    # ---------------------------------------------------------
    # Add reference labels.
    # ---------------------------------------------------------

    positive["validation_group"] = "HYDRIC_VALIDATION"
    negative["validation_group"] = "NONHYDRIC_VALIDATION"

    refs = pd.concat(
        [positive, negative],
        ignore_index=True,
    )

    refs.to_csv(
        OUT / "osbs_reference_pedons.csv",
        index=False,
    )

    # ---------------------------------------------------------
    # Pull corresponding KSSL horizons.
    # Still no spectral values.
    # ---------------------------------------------------------

    ids = set(refs["user_pedon_id"])

    horizons = master[
        master["user_pedon_id"].isin(ids)
    ].copy()

    group_map = dict(
        zip(
            refs["user_pedon_id"],
            refs["validation_group"],
        )
    )

    horizons["validation_group"] = (
        horizons["user_pedon_id"]
        .map(group_map)
    )

    horizons.to_csv(
        OUT / "osbs_reference_horizons.csv",
        index=False,
    )

    # ---------------------------------------------------------
    # One shallowest MINERAL horizon within upper 30 cm
    # per pedon.
    #
    # This mirrors the corrected ND design.
    # ---------------------------------------------------------

    horizons["top_depth_cm"] = pd.to_numeric(
        horizons["top_depth_cm"],
        errors="coerce",
    )

    horizons["bottom_depth_cm"] = pd.to_numeric(
        horizons["bottom_depth_cm"],
        errors="coerce",
    )

    mineral = horizons[
        (horizons["top_depth_cm"] < 30)
        & ~horizons[
            "horizon_designation"
        ]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.startswith("O")
    ].copy()

    mineral = mineral.sort_values(
        [
            "user_pedon_id",
            "top_depth_cm",
            "bottom_depth_cm",
            "smp_id",
        ]
    )

    mineral = (
        mineral
        .drop_duplicates(
            "user_pedon_id",
            keep="first",
        )
    )

    mineral.to_csv(
        OUT / "osbs_selected_mineral_samples.csv",
        index=False,
    )

    print("\nFinal reference counts:")
    print(
        refs["validation_group"]
        .value_counts()
        .to_string()
    )

    print("\nSelected mineral samples:")
    cols = [
        "user_pedon_id",
        "validation_group",
        "smp_id",
        "horizon_designation",
        "top_depth_cm",
        "bottom_depth_cm",
        "taxon_name",
        "clay_pct",
        "sand_pct",
        "silt_pct",
        "mir_master_count",
        "mir_scan_count",
    ]

    cols = [
        c for c in cols
        if c in mineral.columns
    ]

    print(
        mineral[cols]
        .to_string(index=False)
    )

    print("\nMIR availability only:")
    if "mir_master_count" in mineral.columns:
        print(
            mineral.groupby(
                "validation_group"
            )["mir_master_count"]
            .apply(
                lambda x:
                (pd.to_numeric(x, errors="coerce") > 0)
                .sum()
            )
            .to_string()
        )

    print(
        "\nNO MIR spectral values were inspected."
    )

    print("\nWrote:")
    print(OUT / "osbs_reference_pedons.csv")
    print(OUT / "osbs_reference_horizons.csv")
    print(OUT / "osbs_selected_mineral_samples.csv")


if __name__ == "__main__":
    main()