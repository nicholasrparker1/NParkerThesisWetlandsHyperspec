from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pyodbc


ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "raw" / "KSSL" / "MIR Spectra_Access_Portable.accdb"
AUDIT = ROOT / "outputs" / "tables" / "kssl_audit"
OUT = ROOT / "data" / "processed"
QC = ROOT / "outputs" / "tables" / "kssl_analysis"

PRIORITY = {
    "Carbon, Total": "total_carbon_pct",
    "Estimated Organic Carbon": "estimated_organic_carbon_pct",
    "Nitrogen, Total": "total_nitrogen_pct",
    "Sulfur, Total": "total_sulfur_pct",
    "Iron, Dithionite Citrate Extractable": "fe_dithionite_pct",
    "Iron, Oxalate Extractable": "fe_oxalate_pct",
    "Aluminum, Dithionite Citrate Extractable": "al_dithionite_pct",
    "Aluminum, Oxalate Extractable": "al_oxalate_pct",
    "Clay": "clay_pct",
    "Sand, Total": "sand_pct",
    "Silt, Total": "silt_pct",
    "pH, 1:1 Soil-Water Suspension": "ph_water",
    "pH, 1:2 Soil-CaCl2 Suspension": "ph_cacl2",
    "Bulk Density, <2mm Fraction, Ovendry": "bulk_density_ovendry_g_cm3",
    "Bulk Density, <2mm Fraction, 1/3 Bar": "bulk_density_third_bar_g_cm3",
    "Water Retention, 15 Bar, <2mm,  Air-dry": "water_retention_15bar_pct",
    "Water Retention, 1/3 Bar, <2mm Clod": "water_retention_third_bar_pct",
    "CEC, NH4OAc, pH 7.0, 2M KCl displacement": "cec_nh4oac_cmol_kg",
    "Carbonate, <2mm Fraction": "carbonate_pct",
}


def ids(value) -> list[int]:
    if pd.isna(value):
        return []
    return [int(x) for x in re.findall(r"\d+", str(value))]


def read_sql(conn, sql: str) -> pd.DataFrame:
    cursor = conn.cursor()
    cursor.execute(sql)
    names = [x[0] for x in cursor.description]
    return pd.DataFrame.from_records(cursor.fetchall(), columns=names)


def clean_text(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip().replace({"": pd.NA})


def choose_one(candidates: pd.DataFrame, key_cols: list[str]) -> tuple[pd.DataFrame, dict]:
    """Choose one numeric result per layer using global method prevalence, then stable IDs."""
    candidates = candidates.copy()
    candidates["numeric_value"] = pd.to_numeric(candidates["calc_value"], errors="coerce")
    raw_n = len(candidates)
    nonnumeric_n = int(candidates["numeric_value"].isna().sum())
    candidates = candidates.dropna(subset=["numeric_value"])
    candidates["method_key"] = candidates[key_cols].astype("string").fillna("NA").agg("|".join, axis=1)
    prevalence = candidates.groupby("method_key").size().sort_values(ascending=False)
    rank = {key: i for i, key in enumerate(prevalence.index)}
    candidates["method_rank"] = candidates["method_key"].map(rank)
    candidates["candidate_count"] = candidates.groupby("lay_id")["lay_id"].transform("size")
    candidates = candidates.sort_values(
        ["lay_id", "method_rank", "definition_id", "result_record_id"],
        kind="stable",
    )
    selected = candidates.drop_duplicates("lay_id", keep="first")
    summary = {
        "candidate_rows": raw_n,
        "nonnumeric_rows": nonnumeric_n,
        "numeric_rows": len(candidates),
        "unique_layers": selected["lay_id"].nunique(),
        "layers_with_multiple_candidates": int((selected["candidate_count"] > 1).sum()),
        "method_keys": len(prevalence),
        "dominant_method_key": prevalence.index[0] if len(prevalence) else "",
        "dominant_method_rows": int(prevalence.iloc[0]) if len(prevalence) else 0,
    }
    return selected, summary


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    QC.mkdir(parents=True, exist_ok=True)
    ref = pd.read_csv(AUDIT / "property_reference.csv")
    ref = ref[ref["Soil property name"].isin(PRIORITY)].copy()

    conn = pyodbc.connect(
        rf"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={DB};READONLY=TRUE;"
    )
    try:
        layer = read_sql(conn, """
            SELECT lay_id, natural_key AS layer_key, proj_id, lims_site_id,
                   lims_pedon_id, lay_rpt_seq_num, lay_type,
                   lay_depth_to_top AS top_depth_cm,
                   lay_depth_to_bottom AS bottom_depth_cm,
                   horizon_designation, horz_desgn_master,
                   texture_description, texture_desc_abbrev
            FROM layer
        """)
        sample = read_sql(conn, """
            SELECT smp_id, lay_id, smp_type, smp_condition, smp_status
            FROM sample ORDER BY lay_id, smp_id
        """)
        sample["samples_per_layer"] = sample.groupby("lay_id")["smp_id"].transform("size")
        sample = sample.drop_duplicates("lay_id", keep="first")

        site = read_sql(conn, """
            SELECT lims_site_id, user_site_id, horizontal_datum_name,
                   latitude_std_decimal_degrees AS latitude,
                   longitude_std_decimal_degrees AS longitude,
                   latitude_degrees, latitude_minutes, latitude_seconds, latitude_direction,
                   longitude_degrees, longitude_minutes, longitude_seconds, longitude_direction
            FROM lims_site
        """)
        lat_fallback = (
            pd.to_numeric(site.latitude_degrees, errors="coerce")
            + pd.to_numeric(site.latitude_minutes, errors="coerce") / 60
            + pd.to_numeric(site.latitude_seconds, errors="coerce") / 3600
        )
        lon_fallback = (
            pd.to_numeric(site.longitude_degrees, errors="coerce")
            + pd.to_numeric(site.longitude_minutes, errors="coerce") / 60
            + pd.to_numeric(site.longitude_seconds, errors="coerce") / 3600
        )
        lat_fallback *= np.where(clean_text(site.latitude_direction).str.lower().eq("south"), -1, 1)
        lon_fallback *= np.where(clean_text(site.longitude_direction).str.lower().eq("west"), -1, 1)
        site["coordinate_source"] = np.where(site.latitude.notna() & site.longitude.notna(), "standardized", "dms_fallback")
        site["latitude"] = pd.to_numeric(site.latitude, errors="coerce").fillna(lat_fallback)
        site["longitude"] = pd.to_numeric(site.longitude, errors="coerce").fillna(lon_fallback)
        site = site[["lims_site_id", "user_site_id", "horizontal_datum_name", "latitude", "longitude", "coordinate_source"]]

        pedon = read_sql(conn, """
            SELECT lims_pedon_id, natural_key AS pedon_key, user_pedon_id,
                   observation_date_id, pedon_status
            FROM lims_pedon
        """)
        project = read_sql(conn, """
            SELECT proj_id, lab_proj_name, submit_proj_name AS project_focus,
                   fiscal_year, project_source, proj_type, proj_status
            FROM project
        """)
        taxonomy = read_sql(conn, "SELECT * FROM [Taxonomy_sub-query]")
        taxonomy = taxonomy.drop_duplicates("lims_pedon_id", keep="first")
        tax_keep = [c for c in [
            "lims_pedon_id", "taxon_name", "taxonomic_order", "taxonomic_suborder",
            "taxonomic_great_group", "taxonomic_subgroup",
            "taxonomic_family_particle_size", "taxonomic_family_temp_class"
        ] if c in taxonomy.columns]
        taxonomy = taxonomy[tax_keep]

        area = read_sql(conn, """
            SELECT o.lims_site_id, a.area_type, a.area_name
            FROM area AS a INNER JOIN site_area_overlap AS o ON a.area_id=o.area_id
            WHERE a.area_type IN ('country','state_admin_div','county')
        """)
        area = area.drop_duplicates(["lims_site_id", "area_type", "area_name"])
        area["area_rank"] = area.groupby(["lims_site_id", "area_type"]).cumcount() + 1
        area_first = area[area.area_rank.eq(1)].pivot(index="lims_site_id", columns="area_type", values="area_name").reset_index()
        area_first = area_first.rename(columns={"country": "country", "state_admin_div": "state", "county": "county"})

        mir = read_sql(conn, """
            SELECT m.smp_id, COUNT(m.mir_scan_mas_id) AS mir_master_count,
                   COUNT(d.mir_scan_det_id) AS mir_scan_count,
                   SUM(IIF(d.qc_file_status='Passed',1,0)) AS mir_passed_scan_count,
                   SUM(IIF(d.qc_file_status IS NULL OR d.qc_file_status='',1,0)) AS mir_blank_qc_count,
                   MIN(d.scan_date) AS mir_first_scan_date,
                   MAX(d.scan_date) AS mir_last_scan_date
            FROM mir_scan_mas_data AS m LEFT JOIN mir_scan_det_data AS d
              ON m.mir_scan_mas_id=d.mir_scan_mas_id
            GROUP BY m.smp_id
        """)

        base = layer.merge(sample, on="lay_id", how="left", validate="one_to_one")
        base = base.merge(site, on="lims_site_id", how="left", validate="many_to_one")
        base = base.merge(pedon, on="lims_pedon_id", how="left", validate="many_to_one")
        base = base.merge(project, on="proj_id", how="left", validate="many_to_one")
        base = base.merge(taxonomy, on="lims_pedon_id", how="left", validate="many_to_one")
        base = base.merge(area_first, on="lims_site_id", how="left", validate="many_to_one")
        base = base.merge(mir, on="smp_id", how="left", validate="one_to_one")
        base["layer_thickness_cm"] = pd.to_numeric(base.bottom_depth_cm, errors="coerce") - pd.to_numeric(base.top_depth_cm, errors="coerce")
        base["layer_midpoint_cm"] = (pd.to_numeric(base.top_depth_cm, errors="coerce") + pd.to_numeric(base.bottom_depth_cm, errors="coerce")) / 2
        base["surface_or_near_surface"] = pd.to_numeric(base.top_depth_cm, errors="coerce").le(10)
        base["depth_class"] = pd.cut(
            base.layer_midpoint_cm,
            bins=[-np.inf, 10, 30, 60, 100, np.inf],
            labels=["0-10", "10-30", "30-60", "60-100", ">100"],
            right=False,
        ).astype("string")

        selection_summaries = []
        selected_long = []
        for _, r in ref.iterrows():
            prop = r["Soil property name"]
            slug = PRIORITY[prop]
            route = str(r["Query to use"])
            if route.startswith("Measured"):
                analyte_ids = ids(r["analyte_ID"])
                prep_ids = ids(r["master_prep_ID*"])
                prep_clause = f" AND la.master_prep_id IN ({','.join(map(str, prep_ids))})" if prep_ids else ""
                cand = read_sql(conn, f"""
                    SELECT la.lay_analyte_id AS result_record_id, la.lay_id,
                           la.analyte_id AS definition_id, la.calc_value,
                           la.proced_id AS procedure_id, la.master_prep_id AS preparation_id,
                           la.size_frac AS size_fraction, la.instr_set_id AS instrument_set_id,
                           la.lab_id, la.reliability, a.analyte_name AS definition_name,
                           a.analyte_method_code AS method_code, a.uom_abbrev AS units
                    FROM layer_analyte AS la INNER JOIN analyte AS a
                      ON la.analyte_id=a.analyte_id
                    WHERE la.analyte_id IN ({','.join(map(str, analyte_ids))}) {prep_clause}
                """)
                key_cols = ["definition_id", "procedure_id", "preparation_id", "size_fraction", "units"]
            else:
                calc_ids = ids(r["calc_ID"])
                cand = read_sql(conn, f"""
                    SELECT r.result_id AS result_record_id, r.result_source_id AS lay_id,
                           r.calc_id AS definition_id, r.calc_value,
                           NULL AS procedure_id, NULL AS preparation_id,
                           r.size_frac AS size_fraction, NULL AS instrument_set_id,
                           r.lab_id, r.reliability, c.calc_name AS definition_name,
                           c.calc_type AS method_code, c.uom_abbrev AS units
                    FROM result AS r INNER JOIN calc AS c ON r.calc_id=c.calc_id
                    WHERE r.result_type='layer' AND r.calc_id IN ({','.join(map(str, calc_ids))})
                """)
                key_cols = ["definition_id", "size_fraction", "units"]

            chosen, summary = choose_one(cand, key_cols)
            summary.update({"property_name": prop, "column_name": slug, "route": "measured" if route.startswith("Measured") else "derived"})
            selection_summaries.append(summary)
            chosen = chosen.assign(property_name=prop, column_name=slug, source_route=summary["route"])
            selected_long.append(chosen[[
                "lay_id", "property_name", "column_name", "numeric_value", "source_route",
                "result_record_id", "definition_id", "definition_name", "method_code", "units",
                "procedure_id", "preparation_id", "size_fraction", "instrument_set_id",
                "lab_id", "reliability", "method_key", "method_rank", "candidate_count"
            ]])

        long = pd.concat(selected_long, ignore_index=True)
        values = long.pivot(index="lay_id", columns="column_name", values="numeric_value").reset_index()
        base = base.merge(values, on="lay_id", how="left", validate="one_to_one")
        base = base.sort_values(["pedon_key", "top_depth_cm", "lay_id"], kind="stable")

        # Plausibility flags are intentionally non-destructive.
        flags = pd.DataFrame({"lay_id": base.lay_id})
        checks = {
            "total_carbon_outside_0_100": ~base.total_carbon_pct.between(0, 100, inclusive="both") & base.total_carbon_pct.notna(),
            "clay_outside_0_100": ~base.clay_pct.between(0, 100, inclusive="both") & base.clay_pct.notna(),
            "sand_outside_0_100": ~base.sand_pct.between(0, 100, inclusive="both") & base.sand_pct.notna(),
            "silt_outside_0_100": ~base.silt_pct.between(0, 100, inclusive="both") & base.silt_pct.notna(),
            "texture_sum_outside_95_105": ~(
                base.clay_pct + base.sand_pct + base.silt_pct
            ).between(95, 105, inclusive="both") & base[["clay_pct", "sand_pct", "silt_pct"]].notna().all(axis=1),
            "ph_water_outside_2_12": ~base.ph_water.between(2, 12, inclusive="both") & base.ph_water.notna(),
            "bulk_density_outside_0_3": ~base.bulk_density_ovendry_g_cm3.between(0, 3, inclusive="both") & base.bulk_density_ovendry_g_cm3.notna(),
            "invalid_depth_order": base.top_depth_cm.notna() & base.bottom_depth_cm.notna() & base.bottom_depth_cm.le(base.top_depth_cm),
            "invalid_coordinates": base.latitude.notna() & base.longitude.notna() & (~base.latitude.between(-90, 90) | ~base.longitude.between(-180, 180)),
        }
        for name, mask in checks.items():
            flags[name] = mask.fillna(False)
        base["qc_flag_count"] = flags.drop(columns="lay_id").sum(axis=1)

        base.to_csv(OUT / "kssl_layer_analysis_table.csv", index=False)
        long.to_csv(QC / "kssl_selected_property_provenance_long.csv", index=False)
        pd.DataFrame(selection_summaries).to_csv(QC / "kssl_property_selection_summary.csv", index=False)
        flags.to_csv(QC / "kssl_layer_qc_flags.csv", index=False)

        validation = pd.DataFrame([
            ["rows", len(base), counts_expected := 61949, len(base) == counts_expected],
            ["unique_lay_id", base.lay_id.nunique(), 61949, base.lay_id.is_unique],
            ["unique_layer_key", base.layer_key.nunique(), "informational", ""],
            ["rows_with_sample", base.smp_id.notna().sum(), 61949, base.smp_id.notna().all()],
            ["rows_with_mir", base.mir_master_count.notna().sum(), 61949, base.mir_master_count.notna().all()],
            ["rows_with_coordinates", (base.latitude.notna() & base.longitude.notna()).sum(), "informational", ""],
            ["rows_with_any_qc_flag", base.qc_flag_count.gt(0).sum(), 0, base.qc_flag_count.eq(0).all()],
        ], columns=["check", "observed", "expected", "passed"])
        validation.to_csv(QC / "kssl_layer_table_validation.csv", index=False)

        print(f"Wrote {OUT / 'kssl_layer_analysis_table.csv'}: {len(base):,} rows x {len(base.columns):,} columns")
        print(f"Wrote provenance: {len(long):,} selected property-layer values")
        print(validation.to_string(index=False))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
