"""Build a conservative pedon-level KSSL–NASIS–NRCS–SSURGO evidence bridge.

This script does NOT assign regulatory hydric/nonhydric status.

It combines:
1. NASIS-supported NRCS Field Indicator evaluations, and
2. independently matched SSURGO component hydric ratings.

The output separates concordant evidence, conflicting evidence, partial
negative evidence, and cases limited by missing morphology or linkage.
"""

from pathlib import Path

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
    bridge["has_explicit_negative_morphology_evidence"] = (
        bridge["number_not_demonstrated"] > 0
    )

    # Stronger condition: all applicable priority indicators were evaluable
    # rather than being limited by missing morphology.
    bridge["complete_priority_indicator_evaluation"] = (
        (bridge["number_applicable_priority_indicators"] > 0)
        & (bridge["number_insufficient_information"] == 0)
    )

    conditions = [

        # Strongest cross-source positive evidence.
        bridge["field_indicator_present"] & bridge["ssurgo_hydric_yes"],

        # Important scientific disagreements; preserve rather than relabel.
        bridge["field_indicator_present"] & bridge["ssurgo_hydric_no"],

        # NRCS morphology supports hydric conditions, but SSURGO cannot
        # independently resolve the pedon.
        bridge["field_indicator_present"]
        & ~bridge["ssurgo_hydric_yes"]
        & ~bridge["ssurgo_hydric_no"],

        # Strongest available negative reference cohort.
        ~bridge["field_indicator_present"]
        & bridge["ssurgo_hydric_no"]
        & bridge["complete_priority_indicator_evaluation"],

        # SSURGO says nonhydric and NASIS explicitly fails >=1 indicator,
        # but other indicators remain unevaluable.
        ~bridge["field_indicator_present"]
        & bridge["ssurgo_hydric_no"]
        & bridge["has_explicit_negative_morphology_evidence"],

        # SSURGO says nonhydric but NASIS morphology is too incomplete to
        # provide meaningful corroboration.
        ~bridge["field_indicator_present"]
        & bridge["ssurgo_hydric_no"],

        # SSURGO positive without a demonstrated field indicator.
        ~bridge["field_indicator_present"]
        & bridge["ssurgo_hydric_yes"],

        # Remaining medium/ambiguous/unmatched cases.
        ~bridge["high_confidence_ssurgo_match"],
    ]

    labels = [
        "CONCORDANT_POSITIVE",
        "MORPH_POSITIVE_SSURGO_NEGATIVE_CONFLICT",
        "MORPH_POSITIVE_SSURGO_UNRESOLVED",
        "CONCORDANT_STRONG_NEGATIVE",
        "PARTIAL_NEGATIVE_SUPPORT",
        "SSURGO_NEGATIVE_MORPH_INSUFFICIENT",
        "SSURGO_POSITIVE_MORPH_NOT_DEMONSTRATED",
        "LINKAGE_UNRESOLVED",
    ]

    bridge["evidence_class"] = np.select(
        conditions,
        labels,
        default="OTHER",
    )

    # A modeling-use flag. This does NOT mean regulatory truth.
    bridge["core_reference_cohort"] = bridge["evidence_class"].isin(
        [
            "CONCORDANT_POSITIVE",
            "CONCORDANT_STRONG_NEGATIVE",
        ]
    )

    bridge["conflict_flag"] = bridge["evidence_class"].eq(
        "MORPH_POSITIVE_SSURGO_NEGATIVE_CONFLICT"
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
            explicit_negative_morphology=(
                "has_explicit_negative_morphology_evidence",
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
                bridge["has_explicit_negative_morphology_evidence"],
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

    core = bridge[bridge["core_reference_cohort"]]
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

## Core reference cohort

The preliminary core cohort requires cross-source corroboration rather than
using either source alone.

- Concordant positive pedons:
  {(core.evidence_class == "CONCORDANT_POSITIVE").sum()}
- Concordant strong negative pedons:
  {(core.evidence_class == "CONCORDANT_STRONG_NEGATIVE").sum()}
- Total core reference pedons: {len(core)}

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

    print("\nCore reference cohort:")
    print(
        core["evidence_class"]
        .value_counts()
        .to_string()
    )

    print("\nConflicts:")
    print(len(conflicts))

    print(f"\nWrote: {OUT}")
    print(f"Wrote: {SUMMARY}")
    print(f"Wrote: {REPORT}")


if __name__ == "__main__":
    main()