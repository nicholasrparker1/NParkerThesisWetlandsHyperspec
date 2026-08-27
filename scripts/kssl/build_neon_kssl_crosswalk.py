"""Build read-only-derived NEON/KSSL linkage tables from reconnaissance exports."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "outputs" / "tables" / "kssl_neon_audit"
LINK = ROOT / "outputs" / "tables" / "kssl_neon_linkage"
LAYERS = ROOT / "data" / "processed" / "kssl_layer_analysis_table.csv"


def joined(values: pd.Series) -> str:
    clean = sorted({str(v).strip() for v in values.dropna() if str(v).strip()})
    return " | ".join(clean)


def site_code(project_name: object) -> str:
    text = str(project_name or "").upper()
    tokens = re.findall(r"(?<![A-Z0-9])[A-Z0-9]{4}(?![A-Z0-9])", text)
    tokens = [t for t in tokens if t not in {"SITE", "NEON", "CORE", "TOWER"}]
    return tokens[-1] if tokens else ""


def present(series: pd.Series) -> int:
    return int(series.notna().sum())


def main() -> None:
    LINK.mkdir(parents=True, exist_ok=True)
    inventory = pd.read_csv(AUDIT / "neon_layer_sample_inventory.csv", low_memory=False)
    identifiers = pd.read_csv(LINK / "pedon_site_project_identifiers.csv", low_memory=False)
    taxonomy = pd.read_csv(LINK / "taxonomy_history_full.csv", low_memory=False)
    areas = pd.read_csv(LINK / "site_area_identifiers.csv", low_memory=False)
    layer_data = pd.read_csv(LAYERS, low_memory=False)

    neon_layer_ids = set(inventory["lay_id"].dropna().astype(int))
    layer_data = layer_data[layer_data["lay_id"].isin(neon_layer_ids)].copy()
    inventory = inventory.drop_duplicates("lay_id").copy()

    # Select the highest taxonomy-history key only as a deterministic latest-record
    # proxy. Every historical value and record ID remains in separate columns.
    taxonomy = taxonomy.sort_values(
        ["lims_pedon_id", "taxonomic_classification_date_id", "lims_pedon_tax_hist_id"],
        na_position="first",
    )
    current_tax = taxonomy.groupby("lims_pedon_id", as_index=False).tail(1).copy()
    current_cols = [
        "taxon_name", "taxon_kind", "series_status", "taxonomic_classification_name",
        "taxonomic_order", "taxonomic_suborder", "taxonomic_great_group",
        "taxonomic_subgroup", "taxonomic_family_particle_size",
        "taxonomic_family_part_size_mod", "taxonomic_family_c_e_act_class",
        "taxonomic_family_reaction", "taxonomic_family_temp_class",
        "taxonomic_family_haht_mat_class", "taxonomic_moisture_subclass",
        "taxonomic_temp_regime", "taxonomic_classification_type",
        "taxonomic_classification_date_id", "lims_pedon_tax_hist_id",
    ]
    current_tax = current_tax[["lims_pedon_id", *current_cols]].rename(
        columns={c: f"current_{c}" for c in current_cols}
    )
    tax_history = taxonomy.groupby("lims_pedon_id", as_index=False).agg(
        taxonomy_history_record_count=("lims_pedon_tax_hist_id", "size"),
        taxonomy_history_record_ids=("lims_pedon_tax_hist_id", joined),
        historical_classification_types=("taxonomic_classification_type", joined),
        historical_taxon_names=("taxon_name", joined),
        historical_classification_names=("taxonomic_classification_name", joined),
        historical_orders=("taxonomic_order", joined),
        historical_suborders=("taxonomic_suborder", joined),
        historical_great_groups=("taxonomic_great_group", joined),
        historical_subgroups=("taxonomic_subgroup", joined),
    )

    area_rollup = areas.groupby("lims_pedon_id", as_index=False).agg(
        area_record_count=("area_id", "size"),
        area_ids=("area_id", joined),
        area_types=("area_type", joined),
        area_codes=("area_code", joined),
        soil_survey_area_symbols=(
            "area_code",
            lambda x: joined(x[areas.loc[x.index, "area_type"].astype(str).str.lower().eq("ssa")]),
        ),
        soil_survey_area_names=(
            "area_name",
            lambda x: joined(x[areas.loc[x.index, "area_type"].astype(str).str.lower().eq("ssa")]),
        ),
    )

    chemistry = {
        "organic_carbon": "estimated_organic_carbon_pct",
        "total_carbon": "total_carbon_pct",
        "fe_dithionite": "fe_dithionite_pct",
        "fe_oxalate": "fe_oxalate_pct",
        "clay": "clay_pct",
        "sand": "sand_pct",
        "silt": "silt_pct",
        "ph_water": "ph_water",
        "ph_cacl2": "ph_cacl2",
        "cec_nh4oac": "cec_nh4oac_cmol_kg",
        "water_retention_15bar": "water_retention_15bar_pct",
        "water_retention_third_bar": "water_retention_third_bar_pct",
    }

    rows = []
    for pedon_id, group in layer_data.groupby("lims_pedon_id", sort=True):
        ordered = group.sort_values(["top_depth_cm", "bottom_depth_cm", "lay_rpt_seq_num", "lay_id"])
        surface = ordered.iloc[0]
        row = {
            "lims_pedon_id": int(pedon_id),
            "horizon_count": int(group["lay_id"].nunique()),
            "maximum_profile_depth_cm": group["bottom_depth_cm"].max(),
            "surface_horizon_designation": surface.get("horizon_designation"),
            "surface_top_depth_cm": surface.get("top_depth_cm"),
            "surface_bottom_depth_cm": surface.get("bottom_depth_cm"),
            "has_g_designated_horizon": int(group["horizon_designation"].astype(str).str.contains("g", case=False, regex=False).any()),
            "g_designated_horizon_count": int(group["horizon_designation"].astype(str).str.contains("g", case=False, regex=False).sum()),
            "horizons_with_mir": int((group["mir_scan_count"].fillna(0) > 0).sum()),
            "mir_scan_count": int(group["mir_scan_count"].fillna(0).sum()),
            "has_any_selected_chemistry": int(any(group[c].notna().any() for c in chemistry.values())),
        }
        for label, column in chemistry.items():
            row[f"horizons_with_{label}"] = present(group[column])
            row[f"has_{label}"] = int(group[column].notna().any())
        rows.append(row)
    profile = pd.DataFrame(rows)

    crosswalk = identifiers.merge(profile, on="lims_pedon_id", how="left")
    crosswalk = crosswalk.merge(current_tax, on="lims_pedon_id", how="left")
    crosswalk = crosswalk.merge(tax_history, on="lims_pedon_id", how="left")
    crosswalk = crosswalk.merge(area_rollup, on="lims_pedon_id", how="left")
    crosswalk["likely_neon_site_code"] = crosswalk["submit_proj_name"].map(site_code)
    crosswalk["has_coordinates"] = (
        crosswalk["latitude_std_decimal_degrees"].notna()
        & crosswalk["longitude_std_decimal_degrees"].notna()
    ).astype(int)
    crosswalk["coordinate_source"] = "lims_site standardized decimal degrees"
    crosswalk["coordinate_precision_available"] = 0
    crosswalk["current_taxonomy_selection_note"] = (
        "Highest classification-date ID then taxonomy-history ID; verify against authoritative NASIS"
    )
    crosswalk = crosswalk.sort_values(["lab_proj_name", "user_pedon_id", "lims_pedon_id"])
    crosswalk.to_csv(LINK / "neon_kssl_pedon_crosswalk.csv", index=False)

    # State is carried by the all-KSSL layer table from site-area relationships.
    state = layer_data.groupby("lims_pedon_id")["state"].agg(joined).rename("state")
    summary_source = crosswalk.merge(state, on="lims_pedon_id", how="left")
    summary = summary_source.groupby(
        ["proj_id", "lab_proj_name", "submit_proj_name", "likely_neon_site_code", "state"],
        dropna=False,
        as_index=False,
    ).agg(
        pedon_count=("lims_pedon_id", "nunique"),
        horizon_count=("horizon_count", "sum"),
        pedons_with_coordinates=("has_coordinates", "sum"),
        pedons_with_taxonomy=("current_taxon_name", lambda x: int(x.notna().sum())),
        horizons_with_mir=("horizons_with_mir", "sum"),
        pedons_with_selected_chemistry=("has_any_selected_chemistry", "sum"),
    )
    summary["coordinate_coverage_pct"] = (100 * summary.pedons_with_coordinates / summary.pedon_count).round(2)
    summary["taxonomy_coverage_pct"] = (100 * summary.pedons_with_taxonomy / summary.pedon_count).round(2)
    summary["mir_horizon_coverage_pct"] = (100 * summary.horizons_with_mir / summary.horizon_count).round(2)
    summary = summary.sort_values(["pedon_count", "horizon_count"], ascending=False)
    summary.to_csv(LINK / "neon_kssl_site_summary.csv", index=False)

    direct_user_ids = int(crosswalk["user_pedon_id"].notna().sum())
    ssa_count = int(crosswalk["soil_survey_area_symbols"].fillna("").ne("").sum())
    tax_count = int(crosswalk["current_taxon_name"].notna().sum())
    audit = f"""# NEON-associated KSSL identifier audit

## Scope

This audit covers the {len(crosswalk):,} NEON-associated KSSL pedons selected by NEON text in `project.project_source`, `project.lab_proj_name`, `project.submit_proj_name`, or `project.proj_note`. It does not assign hydric status or query SSURGO.

## Direct-linkage candidates

| Identifier | Exact source | Coverage | Interpretation |
|---|---|---:|---|
| LIMS pedon ID | `lims_pedon.lims_pedon_id` | {crosswalk.lims_pedon_id.notna().sum():,}/{len(crosswalk):,} | Primary relational key inside this Access export; not documented here as a public NASIS key. |
| LIMS pedon natural key | `lims_pedon.natural_key` | {crosswalk.lims_pedon_natural_key.notna().sum():,}/{len(crosswalk):,} | KSSL/LIMS natural key candidate; provenance must be confirmed before treating it as NASIS-compatible. |
| User pedon ID | `lims_pedon.user_pedon_id` | {direct_user_ids:,}/{len(crosswalk):,} | Strongest pedon-level external crosswalk candidate. Values commonly resemble NCSS pedon identifiers, e.g. `S2014AZ019001`; confirm in NASIS/NCSS. |
| LIMS site ID | `lims_site.lims_site_id` | {crosswalk.lims_site_id.notna().sum():,}/{len(crosswalk):,} | Primary relational site key inside this export. |
| User site ID | `lims_site.user_site_id` | {crosswalk.user_site_id.notna().sum():,}/{len(crosswalk):,} | Strong external site-level crosswalk candidate; often equals the user pedon ID in this cohort. |
| Soil Survey Area symbol | `site_area_overlap.lims_site_id -> area.area_id`, where `area.area_type='ssa'`; symbol in `area.area_code` | {ssa_count:,}/{len(crosswalk):,} | Authoritative search constraint, not a unique pedon identifier. |
| Taxon/series name | `lims_ped_tax_hist.taxon_name` | {tax_count:,}/{len(crosswalk):,} selected-current records | Useful corroborating identifier; not unique. All history is retained. |
| Taxonomy history key | `lims_ped_tax_hist.lims_pedon_tax_hist_id` | {taxonomy.lims_pedon_id.nunique():,}/{len(crosswalk):,} | Internal history-row key. |
| Project identifier | `project.proj_id`, `project.lab_proj_name` | {crosswalk.proj_id.notna().sum():,}/{len(crosswalk):,} | KSSL submission context; useful for resolving ambiguous IDs. |
| Coordinates | `lims_site.latitude_std_decimal_degrees`, `lims_site.longitude_std_decimal_degrees` | {int(crosswalk.has_coordinates.sum()):,}/{len(crosswalk):,} | Strong fallback/corroborating linkage. No coordinate-precision or accuracy field exists in `lims_site`; datum is retained. |

## NASIS identifier conclusion

No column is explicitly named or documented inside this portable database as a NASIS site ID, NASIS pedon ID, or NCSS pedon key. The best direct-linkage candidates are `lims_pedon.user_pedon_id` and `lims_site.user_site_id`, supplemented by the KSSL project, taxonomy, SSA symbol, coordinates, and observation date. `lims_pedon.natural_key` is retained but must not be presented as a NASIS identifier without external documentation.

## Taxonomy handling

Taxonomy is stored in `lims_ped_tax_hist`, joined through `lims_ped_tax_hist.lims_pedon_id -> lims_pedon.lims_pedon_id`. There are {len(taxonomy):,} history rows for {taxonomy.lims_pedon_id.nunique():,} NEON pedons. The crosswalk preserves pipe-delimited historical values. Its `current_*` fields use the highest non-null `taxonomic_classification_date_id`, then highest `lims_pedon_tax_hist_id`, solely as a deterministic latest-record proxy. Authoritative NASIS should resolve the current classification.

## Dates and coordinate precision

`lims_pedon.observation_date_id` and the project fields `proj_submit_date_id`, `proj_export_date_id`, `proj_due_date_id`, and `proj_est_comp_date_id` are retained exactly as stored. The portable database has no date-dimension table that translates these IDs within the available schema. It also has no explicit coordinate precision/uncertainty column. Original DMS components, standardized decimal coordinates, and `horizontal_datum_name` are retained.

## Area relationships

Site geography is many-to-many through `site_area_overlap`. The crosswalk retains every `area.area_code` and separately aggregates SSA symbols. State/county/MLRA/country overlaps are contextual search fields and must not be mistaken for pedon identifiers.
"""
    (LINK / "neon_kssl_identifier_audit.md").write_text(audit, encoding="utf-8")

    print(f"Wrote {len(crosswalk):,} pedons to neon_kssl_pedon_crosswalk.csv")
    print(f"Wrote {len(summary):,} project/site rows to neon_kssl_site_summary.csv")


if __name__ == "__main__":
    main()
