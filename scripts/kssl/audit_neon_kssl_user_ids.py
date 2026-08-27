"""Audit NEON/KSSL user IDs and build a diverse 20-pedon linkage pilot."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "tables" / "kssl_neon_linkage"
CROSSWALK = OUT / "neon_kssl_pedon_crosswalk.csv"
PILOT = OUT / "neon_kssl_linkage_pilot_20.csv"
AUDIT = OUT / "neon_kssl_identifier_audit.md"
PATTERN = re.compile(r"^(S)(\d{4})([A-Z]{2})(\d{3})(\d{3})$")


def text_present(values: pd.Series) -> pd.Series:
    return values.notna() & values.astype(str).str.strip().ne("")


def year_from_iso(values: pd.Series) -> pd.Series:
    return pd.to_numeric(values.astype(str).str.slice(0, 4), errors="coerce").astype("Int64")


def ratio(numerator: int, denominator: int) -> str:
    return "not testable" if denominator == 0 else f"{numerator:,}/{denominator:,} ({100*numerator/denominator:.2f}%)"


def markdown_table(frame: pd.DataFrame) -> str:
    display = frame.fillna("").astype(str)
    header = "| " + " | ".join(display.columns) + " |"
    rule = "|" + "|".join("---" for _ in display.columns) + "|"
    rows = ["| " + " | ".join(row) + " |" for row in display.to_numpy().tolist()]
    return "\n".join([header, rule, *rows])


def main() -> None:
    data = pd.read_csv(CROSSWALK, low_memory=False)
    areas = pd.read_csv(OUT / "site_area_identifiers.csv", low_memory=False)
    counties = areas[areas.area_type.astype(str).str.lower().eq("county")]
    county_rollup = counties.groupby("lims_pedon_id", as_index=False).agg(
        county_area_codes=("area_code", lambda x: " | ".join(sorted(set(x.dropna().astype(str))))),
        county_area_names=("area_name", lambda x: " | ".join(sorted(set(x.dropna().astype(str))))),
    )
    data = data.merge(county_rollup, on="lims_pedon_id", how="left")
    pedon_present = text_present(data.user_pedon_id)
    site_present = text_present(data.user_site_id)
    both = pedon_present & site_present
    identical = both & data.user_pedon_id.eq(data.user_site_id)

    parsed = data.user_pedon_id.fillna("").astype(str).str.extract(PATTERN)
    parsed.columns = [
        "id_sampled_prefix", "id_year", "id_state", "id_county_code",
        "id_sequential_pedon_number",
    ]
    data = pd.concat([data, parsed], axis=1)
    data["id_year"] = pd.to_numeric(data.id_year, errors="coerce").astype("Int64")
    data["user_pedon_id_standard_conforming"] = data.id_sampled_prefix.eq("S").astype(int)
    data["user_ids_identical"] = identical.astype(int)

    data["observation_year"] = year_from_iso(data.observation_date_iso)
    data["sample_received_year"] = year_from_iso(data.earliest_sample_received_date_iso)
    data["sample_login_year"] = year_from_iso(data.earliest_sample_login_date_iso)
    data["project_fiscal_year"] = pd.to_numeric(data.fiscal_year, errors="coerce").astype("Int64")
    data["project_name_state"] = data.lab_proj_name.fillna("").str.extract(
        r"^C\d{4}US([A-Z]{2})", expand=False
    )

    ssa_lists = data.soil_survey_area_symbols.fillna("").str.split(r"\s*\|\s*")
    data["id_state_matches_project_name"] = [
        int(pd.notna(state) and pd.notna(project) and state == project)
        for state, project in zip(data.id_state, data.project_name_state)
    ]
    data["id_state_matches_any_ssa"] = [
        int(pd.notna(state) and any(str(symbol).startswith(state) for symbol in symbols if symbol))
        for state, symbols in zip(data.id_state, ssa_lists)
    ]
    data["id_county_matches_any_ssa"] = [
        int(pd.notna(state) and pd.notna(county) and f"{state}{county}" in symbols)
        for state, county, symbols in zip(data.id_state, data.id_county_code, ssa_lists)
    ]
    county_lists = data.county_area_codes.fillna("").str.split(r"\s*\|\s*")
    data["id_county_matches_area_county"] = [
        int(pd.notna(state) and pd.notna(county) and f"{state}{county}" in codes)
        for state, county, codes in zip(data.id_state, data.id_county_code, county_lists)
    ]
    for reference in ["observation_year", "sample_received_year", "sample_login_year", "project_fiscal_year"]:
        data[f"id_year_matches_{reference}"] = (
            data.id_year.notna() & data[reference].notna() & data.id_year.eq(data[reference])
        ).astype(int)
        data[f"id_year_minus_{reference}"] = data.id_year - data[reference]

    chemistry_flags = [
        "has_organic_carbon", "has_total_carbon", "has_fe_dithionite",
        "has_fe_oxalate", "has_clay", "has_sand", "has_silt", "has_ph_water",
        "has_ph_cacl2", "has_cec_nh4oac", "has_water_retention_15bar",
        "has_water_retention_third_bar",
    ]
    data["pilot_chemistry_property_count"] = data[chemistry_flags].fillna(0).astype(int).sum(axis=1)
    data["pilot_required_fields_complete"] = (
        data.user_pedon_id_standard_conforming.eq(1)
        & data.user_ids_identical.eq(1)
        & data.has_coordinates.eq(1)
        & text_present(data.current_taxon_name)
        & text_present(data.soil_survey_area_symbols)
        & data.horizon_count.ge(2)
        & data.horizons_with_mir.ge(2)
    ).astype(int)
    data["pilot_score"] = (
        100 * data.pilot_required_fields_complete
        + 5 * data.pilot_chemistry_property_count
        + data.horizon_count.clip(upper=20)
        + data.id_state_matches_project_name
        + data.id_state_matches_any_ssa
        + data.id_county_matches_area_county
    )

    eligible = data[data.pilot_required_fields_complete.eq(1)].sort_values(
        ["pilot_score", "pilot_chemistry_property_count", "horizon_count", "lims_pedon_id"],
        ascending=[False, False, False, True],
    )
    # First pass enforces project diversity. A second pass would fill any shortfall.
    first = eligible.drop_duplicates("proj_id", keep="first").head(20)
    if len(first) < 20:
        remainder = eligible[~eligible.lims_pedon_id.isin(first.lims_pedon_id)].head(20 - len(first))
        pilot = pd.concat([first, remainder], ignore_index=True)
    else:
        pilot = first.copy()
    pilot = pilot.sort_values(["pilot_score", "proj_id"], ascending=[False, True])
    pilot.to_csv(PILOT, index=False)

    standard = data.user_pedon_id_standard_conforming.eq(1)
    duplicates = data.loc[pedon_present, "user_pedon_id"].duplicated(keep=False)
    duplicate_rows = data.loc[pedon_present & duplicates, ["lims_pedon_id", "user_pedon_id"]]
    unusual = data.loc[pedon_present & ~standard, [
        "lims_pedon_id", "user_pedon_id", "user_site_id", "lab_proj_name",
        "submit_proj_name",
    ]]

    def agreement(flag: str, testable: pd.Series) -> str:
        subset = standard & testable
        return ratio(int(data.loc[subset, flag].sum()), int(subset.sum()))

    obs_test = data.observation_year.notna()
    received_test = data.sample_received_year.notna()
    login_test = data.sample_login_year.notna()
    fiscal_test = data.project_fiscal_year.notna()
    project_state_test = data.project_name_state.notna()
    ssa_test = text_present(data.soil_survey_area_symbols)
    county_test = text_present(data.county_area_codes)

    unusual_md = markdown_table(unusual) if len(unusual) else "None."
    duplicate_md = markdown_table(duplicate_rows) if len(duplicate_rows) else "None."
    pilot_preview = markdown_table(pilot[[
        "user_pedon_id", "likely_neon_site_code", "submit_proj_name",
        "soil_survey_area_symbols", "current_taxon_name", "horizon_count",
        "pilot_chemistry_property_count",
    ]])

    section = f"""

## User Pedon ID linkage audit

### Coverage and conformance

| Test | Result |
|---|---:|
| Pedons in cohort | {len(data):,} |
| Non-empty `lims_pedon.user_pedon_id` | {int(pedon_present.sum()):,} |
| Non-empty `lims_site.user_site_id` | {int(site_present.sum()):,} |
| Both identifiers present | {int(both.sum()):,} |
| Identifiers identical | {int(identical.sum()):,} |
| Unique User Pedon IDs | {data.loc[pedon_present, 'user_pedon_id'].nunique():,} |
| Duplicate User Pedon ID rows | {len(duplicate_rows):,} |
| Exact `SYYYYSTCCCNNN` conformance | {int(standard.sum()):,}/{len(data):,} ({100*standard.mean():.2f}%) |

The parser preserves the source identifiers and derives: sampled prefix `S`, four-digit year, two-letter state, three-digit county code, and three-digit sequential pedon number. It does not force nonconforming identifiers into this structure.

### Nonconforming or unusual identifiers

{unusual_md}

### Duplicate identifiers

{duplicate_md}

### Internal consistency of conforming identifiers

| Independent comparison | Exact agreement |
|---|---:|
| Encoded year vs pedon observation year | {agreement('id_year_matches_observation_year', obs_test)} |
| Encoded year vs earliest KSSL sample-received year | {agreement('id_year_matches_sample_received_year', received_test)} |
| Encoded year vs earliest KSSL sample-login year | {agreement('id_year_matches_sample_login_year', login_test)} |
| Encoded year vs KSSL project fiscal year | {agreement('id_year_matches_project_fiscal_year', fiscal_test)} |
| Encoded state vs state embedded in `project.lab_proj_name` | {agreement('id_state_matches_project_name', project_state_test)} |
| Encoded state vs at least one linked SSA symbol | {agreement('id_state_matches_any_ssa', ssa_test)} |
| Encoded `STCCC` vs a linked SSA symbol | {agreement('id_county_matches_any_ssa', ssa_test)} |
| Encoded state+county vs linked `area_type='county'` code | {agreement('id_county_matches_area_county', county_test)} |

Coordinates are retained for external spatial validation, but this step does not perform a point-in-state or point-in-county spatial assignment. SSA comparisons use the existing KSSL `site_area_overlap` relationship and are therefore internal corroboration, not a new SSURGO assignment.

### Engineering assessment

The User Pedon ID is a strong candidate bridge because it is populated, nearly unique, usually identical to User Site ID, highly standardized, and independently checkable against project, date, county, and SSA context. It is not yet proven to be an authoritative public NASIS lookup key: the 20-pedon pilot should test exact-ID retrieval and confirm whether results distinguish the original MLRA office record from the KSSL copy.

## Twenty-pedon external-linkage pilot

The pilot requires a conforming and internally identical User Pedon/Site ID, coordinates, taxonomy, SSA, at least two horizons, MIR at multiple depths, and selected chemistry. Selection takes the highest-scoring pedon from each project first, producing {pilot.proj_id.nunique()} projects among 20 pedons. No hydric evidence enters the score.

{pilot_preview}

Full search fields and audit columns are in `neon_kssl_linkage_pilot_20.csv`.
"""
    audit = AUDIT.read_text(encoding="utf-8")
    marker = "\n## User Pedon ID linkage audit\n"
    if marker in audit:
        audit = audit.split(marker, 1)[0].rstrip() + "\n"
    AUDIT.write_text(audit.rstrip() + section + "\n", encoding="utf-8")

    print(f"Standard IDs: {int(standard.sum())}/{len(data)}")
    print(f"Identical user pedon/site IDs: {int(identical.sum())}/{len(data)}")
    print(f"Pilot rows/projects: {len(pilot)}/{pilot.proj_id.nunique()}")


if __name__ == "__main__":
    main()
