"""Build a conservative pedon-level KSSL–NASIS–NRCS–SSURGO evidence bridge.

This script does NOT assign regulatory hydric/nonhydric status.

It combines:
1. NASIS-supported NRCS Field Indicator evaluations, and
2. independently matched SSURGO component hydric ratings.

The output separates concordant evidence, conflicting evidence, partial
negative evidence, and cases limited by missing morphology or linkage.
"""

from pathlib import Path
import re

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

BASE = ROOT / "outputs" / "tables" / "kssl_neon_linkage"

INDICATORS = BASE / "neon_kssl_hydric_indicator_pedon_summary.csv"
SSURGO = BASE / "neon_kssl_ssurgo_component_matches.csv"

OUT = BASE / "neon_kssl_hydric_evidence_bridge.csv"
SUMMARY = BASE / "neon_kssl_hydric_evidence_bridge_summary.csv"
REPORT = BASE / "neon_kssl_hydric_evidence_bridge_report.md"


def norm_text(series):
    return series.fillna("").astype(str).str.strip()


def resolve_site_code(current: object, project: object) -> tuple[str, str]:
    """Recover only site codes explicitly supported by project provenance."""
    existing = str(current).strip() if pd.notna(current) else ""
    if existing:
        return existing, "existing likely_neon_site_code"
    text = str(project).upper() if pd.notna(project) else ""
    parenthetical = re.search(r"\(([A-Z0-9]{4})\)", text)
    if parenthetical:
        return parenthetical.group(1), "four-character code in project name"
    aliases = {
        "WOODWORTH": "WOOD", "STUTSMAN": "WOOD",
        "LENOIR": "LENO", "TALLADEGA": "TALL", "TALLADAGA": "TALL",
        "GUANICA": "GUAN", "TREE HAVEN": "TREE", "STEIGERWALD": "STEI",
        "DELTA JUNCTION": "DEJU", "ONAQUI": "ONAQ", "KONZA": "KONZ",
        "NIWOT RIDGE": "NIWO", "JORNADA": "JORN", "CPER": "CPER",
        "BLANDY": "BLAN", "SERC": "SERC", "WIND RIVER": "WREF",
    }
    matches = {code for name, code in aliases.items() if name in text}
    if len(matches) == 1:
        return matches.pop(), "unique named-site alias in project provenance"
    return "", "unresolved from existing project provenance"


def main():

    indicators = pd.read_csv(INDICATORS, low_memory=False)
    ssurgo = pd.read_csv(SSURGO, low_memory=False)

    print(f"Indicator pedons: {len(indicators)}")
    print(f"SSURGO linkage rows: {len(ssurgo)}")

    # Keep only fields required for the independent SSURGO evidence layer.
    ssurgo_cols = [
        "lims_pedon_id",
        "user_pedon_id",
        "likely_neon_site_code",
        "submit_proj_name",
        "areasymbol",
        "mukey",
        "musym",
        "muname",
        "nasis_taxon_name",
        "nasis_taxonomy",
        "match_confidence",
        "match_evidence",
        "selected_cokey",
        "selected_compname",
        "selected_comppct_r",
        "selected_majcompflag",
        "selected_drainagecl",
        "selected_hydricrating",
        "selected_hydric_criteria",
    ]

    available = [c for c in ssurgo_cols if c in ssurgo.columns]
    ssurgo = ssurgo[available].copy()

    bridge = indicators.merge(
        ssurgo,
        on=["lims_pedon_id", "user_pedon_id"],
        how="left",
        validate="one_to_one",
    )

    resolved = bridge.apply(
        lambda row: resolve_site_code(
            row.get("likely_neon_site_code", ""), row.get("submit_proj_name", "")
        ),
        axis=1,
    )
    bridge["likely_neon_site_code"] = [value[0] for value in resolved]
    bridge["site_code_resolution"] = [value[1] for value in resolved]

    bridge["match_confidence"] = norm_text(bridge["match_confidence"]).str.upper()
    bridge["ssurgo_hydric_rating"] = (
        norm_text(bridge["selected_hydricrating"]).str.lower()
    )

    # EXACT and HIGH are the primary independent SSURGO validation cohort.
    bridge["high_confidence_ssurgo_match"] = bridge["match_confidence"].isin(
        ["EXACT", "HIGH"]
    )

    bridge["ssurgo_hydric_yes"] = (
        bridge["high_confidence_ssurgo_match"]
        & bridge["ssurgo_hydric_rating"].eq("yes")
    )

    bridge["ssurgo_hydric_no"] = (
        bridge["high_confidence_ssurgo_match"]
        & bridge["ssurgo_hydric_rating"].eq("no")
    )

    bridge["field_indicator_present"] = (
        bridge["has_at_least_one_approved_indicator_present"]
        .fillna(False)
        .astype(bool)
    )

    for col in [
        "number_applicable_priority_indicators",
        "number_not_demonstrated",
        "number_insufficient_information",
    ]:
        bridge[col] = pd.to_numeric(bridge[col], errors="coerce").fillna(0)

    # Whether NASIS contained enough information to explicitly evaluate at
    # least one applicable priority indicator as NOT demonstrated.
    bridge["at_least_one_rule_not_demonstrated"] = (
        bridge["number_not_demonstrated"] > 0
    )

    # Stronger condition: all applicable priority indicators were evaluable
    # rather than being limited by missing morphology.
    bridge["complete_priority_indicator_evaluation"] = (
        (bridge["number_applicable_priority_indicators"] > 0)
        & (bridge["number_insufficient_information"] == 0)
    )

    conditions = [

        # Cross-source positive evidence.
        bridge["field_indicator_present"] & bridge["ssurgo_hydric_yes"],

        # Important scientific disagreements; preserve rather than relabel.
        bridge["field_indicator_present"] & bridge["ssurgo_hydric_no"],

        # NRCS morphology supports hydric conditions, but SSURGO is unresolved.
        bridge["field_indicator_present"]
        & ~bridge["ssurgo_hydric_yes"]
        & ~bridge["ssurgo_hydric_no"],

        # SSURGO component-scale hydric support without demonstrated morphology.
        ~bridge["field_indicator_present"]
        & bridge["ssurgo_hydric_yes"],

        # SSURGO component-scale nonhydric support without a positive indicator.
        ~bridge["field_indicator_present"]
        & bridge["ssurgo_hydric_no"],
    ]

    labels = [
        "STRONG_HYDRIC_SUPPORT",
        "CONFLICTING_EVIDENCE",
        "MORPHOLOGY_HYDRIC_SUPPORT",
        "SSURGO_HYDRIC_SUPPORT",
        "SSURGO_NONHYDRIC_SUPPORT",
    ]

    bridge["evidence_class"] = np.select(
        conditions,
        labels,
        default="INSUFFICIENT_OR_UNRESOLVED",
    )

    bridge["conflict_flag"] = bridge["evidence_class"].eq(
        "CONFLICTING_EVIDENCE"
    )

    bridge.to_csv(OUT, index=False)

    summary = (
        bridge.groupby("evidence_class", dropna=False)
        .agg(
            pedons=("user_pedon_id", "size"),
            unique_sites=("likely_neon_site_code", "nunique"),
            indicator_positive=("field_indicator_present", "sum"),
            high_conf_ssurgo=("high_confidence_ssurgo_match", "sum"),
            ssurgo_hydric_yes=("ssurgo_hydric_yes", "sum"),
            ssurgo_hydric_no=("ssurgo_hydric_no", "sum"),
            at_least_one_rule_not_demonstrated=(
                "at_least_one_rule_not_demonstrated",
                "sum",
            ),
            complete_indicator_evaluation=(
                "complete_priority_indicator_evaluation",
                "sum",
            ),
        )
        .reset_index()
        .sort_values("pedons", ascending=False)
    )

    summary.to_csv(SUMMARY, index=False)

    # Cross-tab is central for understanding independence/agreement.
    bridge["indicator_state"] = np.where(
        bridge["field_indicator_present"],
        "INDICATOR_PRESENT",
        np.where(
            bridge["complete_priority_indicator_evaluation"],
            "NO_INDICATOR_COMPLETE_EVAL",
            np.where(
            bridge["at_least_one_rule_not_demonstrated"],
                "NO_INDICATOR_PARTIAL_EVAL",
                "NO_INDICATOR_INSUFFICIENT",
            ),
        ),
    )

    bridge["ssurgo_state"] = np.select(
        [
            bridge["ssurgo_hydric_yes"],
            bridge["ssurgo_hydric_no"],
            bridge["high_confidence_ssurgo_match"],
        ],
        [
            "HYDRIC_YES",
            "HYDRIC_NO",
            "HIGH_CONF_RATING_OTHER",
        ],
        default="LINKAGE_UNRESOLVED",
    )

    cross = pd.crosstab(
        bridge["indicator_state"],
        bridge["ssurgo_state"],
        margins=True,
    )

    conflicts = bridge[bridge["conflict_flag"]]

    report = f"""# KSSL–NASIS–NRCS–SSURGO Hydric Evidence Bridge

## Purpose

Construct a pedon-level evidence framework joining independently derived
NASIS/NRCS field-indicator evidence with SSURGO component hydric ratings.

This is not a regulatory hydric-soil classification and does not treat absence
of a detected field indicator as proof of nonhydric status.

## Population

- Total pedons: {len(bridge)}
- High-confidence SSURGO matches: {int(bridge.high_confidence_ssurgo_match.sum())}
- SSURGO hydric Yes: {int(bridge.ssurgo_hydric_yes.sum())}
- SSURGO hydric No: {int(bridge.ssurgo_hydric_no.sum())}
- NRCS indicator-positive pedons: {int(bridge.field_indicator_present.sum())}

## Evidence classes

{summary.to_string(index=False)}

## NRCS morphology × SSURGO evidence

{cross.to_string()}

## Site-code provenance

- Resolved site codes: {(bridge.likely_neon_site_code != '').sum()}
- Unresolved site codes: {(bridge.likely_neon_site_code == '').sum()}

## Conflicts

NRCS field-indicator positive but high-confidence SSURGO hydric=No:

- Conflict pedons: {len(conflicts)}

These records are retained as a separate scientific cohort and must not be
silently corrected, discarded, or relabeled.

## Interpretation

SSURGO component ratings provide an independent landscape/component context.
NASIS morphology supports pedon-scale evaluation of official NRCS Field
Indicators. Their agreement can define high-confidence reference cohorts;
their disagreement is itself scientifically informative.

The next stage should determine whether KSSL laboratory chemistry, physical
properties, and MIR spectra distinguish these evidence cohorts while avoiding
circular use of variables involved in constructing the reference evidence.
"""

    REPORT.write_text(report, encoding="utf-8")

    print("\nEvidence classes:")
    print(summary.to_string(index=False))

    print("\nMorphology x SSURGO cross-tab:")
    print(cross)

    print("\nConflicts:")
    print(len(conflicts))

    print(f"\nWrote: {OUT}")
    print(f"Wrote: {SUMMARY}")
    print(f"Wrote: {REPORT}")


if __name__ == "__main__":
    main()
