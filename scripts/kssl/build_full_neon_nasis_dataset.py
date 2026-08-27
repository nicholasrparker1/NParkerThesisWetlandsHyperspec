"""Retrieve full NEON NASIS reports and build morphology/KSSL joined tables."""

from __future__ import annotations

import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import retrieve_nasis_pilot_descriptions as nasis  # noqa: E402

OUT = ROOT / "outputs" / "tables" / "kssl_neon_linkage"
CROSSWALK = OUT / "neon_kssl_pedon_crosswalk.csv"
KSSL_LAYERS = ROOT / "data" / "processed" / "kssl_layer_analysis_table.csv"
FE_MN = OUT / "neon_kssl_fe_mn_measurements.csv"
RAW = OUT / "nasis_raw_html"
PEDON_OUT = OUT / "neon_kssl_nasis_full_pedon_summary.csv"
HORIZON_OUT = OUT / "neon_kssl_nasis_horizon_morphology.csv"
JOIN_OUT = OUT / "neon_kssl_nasis_kssl_horizon_crosswalk.csv"
MASTER_OUT = OUT / "neon_kssl_master_pedon_horizon_table.csv"
REPORT_OUT = OUT / "neon_kssl_nasis_full_retrieval_report.md"
STANDARD = re.compile(r"^S\d{4}[A-Z]{2}\d{6}$")


def joined(values) -> str:
    return " | ".join(dict.fromkeys(str(v).strip() for v in values if str(v).strip()))


def fetch_with_retry(user_id: str) -> tuple[str, str, str]:
    cached = RAW / f"{user_id}.html"
    if cached.exists() and cached.stat().st_size > 1000:
        return user_id, cached.read_text(encoding="utf-8"), ""
    last_error = ""
    for attempt in range(3):
        _, document, error = nasis.fetch(user_id)
        if document and 'id="ReportData"' in document:
            cached.write_text(document, encoding="utf-8")
            return user_id, document, ""
        last_error = error or "ReportData absent from response"
        time.sleep(2 ** attempt)
    return user_id, "", last_error


def after(lines: list[str], label: str) -> list[str]:
    return nasis.values_after(lines, label)


def nullable_flag(condition: bool):
    return 1 if condition else pd.NA


def parse_color(raw: str) -> dict:
    codes = nasis.MUNSELL_RE.findall(raw)
    names = re.findall(r"([a-z][a-z ]+?)\s*\(([^()]*/[^()]*)\)", raw, re.I)
    selected = codes[-1] if codes else ""
    hue = value = chroma = ""
    if selected:
        parts = selected.split()
        hue = " ".join(parts[:-1])
        value, chroma = parts[-1].split("/", 1)
    status = "moist" if re.search(r",\s*moist\b", raw, re.I) else ""
    dry = codes[0] if len(codes) >= 2 and status == "moist" else ""
    moist = codes[-1] if codes and status == "moist" else ""
    return {
        "matrix_color_raw": raw,
        "matrix_color_name": names[-1][0].strip() if names else "",
        "matrix_munsell": selected,
        "matrix_hue": hue,
        "matrix_value": pd.to_numeric(value, errors="coerce"),
        "matrix_chroma": pd.to_numeric(chroma, errors="coerce"),
        "color_moisture_status": status,
        "dry_munsell": dry,
        "moist_munsell": moist,
    }


def parse_redox(text: str) -> dict:
    segments = [
        segment.strip() for segment in text.split(";")
        if re.search(r"redox|oxidized iron|deplet|reduced matrix|gley", segment, re.I)
    ]
    raw = joined(segments)
    concentrations = bool(re.search(r"oxidized iron|redox concentration|iron concentration", raw, re.I))
    depletions = bool(re.search(r"deplet", raw, re.I))
    percentages = re.findall(
        r"(\d+(?:\.\d+)?)\s*percent(?=[^;]*(?:oxidized iron|redox|deplet|reduced matrix))",
        raw,
        re.I,
    )
    abundance = joined(re.findall(r"\b(few|common|many)\b", raw, re.I))
    size = joined(re.findall(r"\b(very fine|fine|medium|coarse|very coarse)\b", raw, re.I))
    contrast = joined(re.findall(r"\b(faint|distinct|prominent)\b", raw, re.I))
    location = joined(re.findall(
        r"\b(throughout|between peds|on faces of peds|in pores|along root channels|on ped faces)\b",
        raw,
        re.I,
    ))
    types = []
    if concentrations:
        types.append("concentration")
    if depletions:
        types.append("depletion")
    if re.search(r"reduced matrix|\breduced\b", raw, re.I):
        types.append("reduced matrix")
    if re.search(r"\bgley|GLEY\s*\d", raw, re.I):
        types.append("gley")
    return {
        "redox_raw": raw,
        "redox_feature_type": joined(types),
        "redox_concentration_rendered": nullable_flag(concentrations),
        "redox_depletion_rendered": nullable_flag(depletions),
        "redox_percentages": joined(percentages),
        "redox_percentage_max": max(map(float, percentages)) if percentages else np.nan,
        "redox_abundance": abundance,
        "redox_size": size,
        "redox_contrast": contrast,
        "redox_location": location,
        "reduced_matrix_rendered": nullable_flag(bool(re.search(r"reduced matrix|\breduced\b", raw, re.I))),
        "gley_rendered": nullable_flag(bool(re.search(r"\bgley|GLEY\s*\d", raw, re.I))),
        "wetness_morphology_raw": raw,
    }


def parse_report(user_id: str, document: str, error: str) -> tuple[dict, list[dict]]:
    node, lines, _ = nasis.report_content(document) if document else (None, [], "")
    narratives = nasis.horizon_narratives(node, lines)
    horizons = []
    for sequence, narrative in enumerate(narratives, start=1):
        base = nasis.parse_horizon(narrative)
        color = parse_color(base["color_phrase"])
        redox = parse_redox(narrative)
        designation = base["designation"]
        organic = bool(re.match(r"^\d*O", designation, re.I) or re.search(r"\b(peat|muck|mucky|organic material)\b", narrative, re.I))
        horizons.append({
            "user_pedon_id": user_id,
            "nasis_horizon_sequence": sequence,
            "horizon_designation": designation,
            "top_depth_cm": base["top_cm"],
            "bottom_depth_cm": base["bottom_cm"],
            "thickness_cm": base["bottom_cm"] - base["top_cm"],
            "field_texture": base["texture"],
            **color,
            **redox,
            "organic_horizon_or_material_rendered": nullable_flag(organic),
            "raw_horizon_description": narrative,
        })
    returned_ids = after(lines, "User Pedon ID:")
    latitudes = after(lines, "Std. Latitude:")
    longitudes = after(lines, "Std. Longitude:")
    lab = after(lines, "Certified Lab Pedon Description -")
    origins = after(lines, "Pedon Record Orgin:") + after(lines, "Pedon Record Origin:")
    summary = {
        "user_pedon_id": user_id,
        "retrieval_success": int(bool(returned_ids)),
        "number_of_matching_pedon_records": lines.count("IDENTIFIERS"),
        "exact_identifier_match": int(bool(returned_ids) and all(value == user_id for value in returned_ids)),
        "returned_user_pedon_ids": joined(returned_ids),
        "site_id": joined(after(lines, "User Site ID:")),
        "latitude": joined(latitudes),
        "longitude": joined(longitudes),
        "observation_date": joined(after(lines, "Observation Date:")),
        "current_correlated_soil_name": joined(after(lines, "Current Taxon Name (Soil Name):")),
        "taxonomy": joined(after(lines, "Current Taxonomic Class:")),
        "drainage_class": joined(after(lines, "Drainage Class:")),
        "flooding": joined(after(lines, "Flooding:")),
        "ponding": joined(after(lines, "Ponding:")),
        "horizon_count": len(horizons),
        "maximum_described_depth_cm": max((row["bottom_depth_cm"] for row in horizons), default=np.nan),
        "certified_lab_pedon_description": joined(lab),
        "record_origin": joined(origins),
        "usable_morphology": int(any(row["matrix_munsell"] or row["redox_raw"] for row in horizons)),
        "request_error": error,
        "raw_html_file": str((RAW / f"{user_id}.html").relative_to(ROOT)) if document else "",
    }
    return summary, horizons


def normalize_designation(value) -> str:
    return re.sub(r"\s+", "", str(value or "")).casefold()


def assign_join(kssl: pd.Series, nasis_rows: pd.DataFrame) -> tuple[str, int | None, str]:
    if nasis_rows.empty:
        return "UNMATCHED", None, "No NASIS horizons returned"
    top = pd.to_numeric(pd.Series([kssl.top_depth_cm]), errors="coerce").iloc[0]
    bottom = pd.to_numeric(pd.Series([kssl.bottom_depth_cm]), errors="coerce").iloc[0]
    designation = normalize_designation(kssl.horizon_designation)
    depth = nasis_rows[
        np.isclose(nasis_rows.top_depth_cm, top, equal_nan=False)
        & np.isclose(nasis_rows.bottom_depth_cm, bottom, equal_nan=False)
    ] if pd.notna(top) and pd.notna(bottom) else nasis_rows.iloc[0:0]
    exact = depth[depth.horizon_designation.map(normalize_designation).eq(designation)]
    if len(exact) == 1:
        return "EXACT", int(exact.index[0]), "Designation and top/bottom depths agree"
    if len(exact) > 1 or len(depth) > 1:
        return "AMBIGUOUS", None, "Multiple NASIS horizons satisfy exact/depth criteria"
    if len(depth) == 1:
        return "HIGH", int(depth.index[0]), "Top/bottom depths agree; designation differs"
    same_designation = nasis_rows[nasis_rows.horizon_designation.map(normalize_designation).eq(designation)]
    seq = int(kssl.lay_rpt_seq_num) if pd.notna(kssl.lay_rpt_seq_num) else None
    sequence_match = same_designation[same_designation.nasis_horizon_sequence.eq(seq)] if seq else same_designation.iloc[0:0]
    if len(sequence_match) == 1:
        return "HIGH", int(sequence_match.index[0]), "Designation and profile sequence agree"
    if len(same_designation) > 1:
        return "AMBIGUOUS", None, "Designation matches multiple NASIS horizons"
    return "UNMATCHED", None, "No unique designation/depth/sequence match"


def metal_wide() -> pd.DataFrame:
    if not FE_MN.exists():
        return pd.DataFrame(columns=["lay_id"])
    metals = pd.read_csv(FE_MN, low_memory=False)
    metals["method_key"] = (
        metals.analyte_abbrev.fillna(metals.analyte_name).astype(str)
        + "__analyte_" + metals.analyte_id.astype(str)
    ).str.lower().str.replace(r"[^a-z0-9_]+", "_", regex=True)
    metals["calc_value"] = pd.to_numeric(metals.calc_value, errors="coerce")
    wide = metals.pivot_table(index="lay_id", columns="method_key", values="calc_value", aggfunc="first")
    wide.columns = [f"lab_{column}" for column in wide.columns]
    return wide.reset_index()


def md_table(frame: pd.DataFrame) -> str:
    shown = frame.fillna("").astype(str)
    return "\n".join([
        "| " + " | ".join(shown.columns) + " |",
        "|" + "|".join("---" for _ in shown.columns) + "|",
        *("| " + " | ".join(row) + " |" for row in shown.to_numpy().tolist()),
    ])


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    crosswalk = pd.read_csv(CROSSWALK, low_memory=False)
    conforming = crosswalk[crosswalk.user_pedon_id.fillna("").str.match(STANDARD)].copy()
    user_ids = sorted(conforming.user_pedon_id.unique())
    print(f"Target: {len(conforming)} KSSL pedons, {len(user_ids)} unique User Pedon IDs", flush=True)

    responses = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fetch_with_retry, user_id): user_id for user_id in user_ids}
        completed = 0
        for future in as_completed(futures):
            user_id, document, error = future.result()
            responses[user_id] = (document, error)
            completed += 1
            if completed % 20 == 0 or completed == len(user_ids):
                successes = sum(bool(document) for document, _ in responses.values())
                print(f"Completed {completed}/{len(user_ids)}; responses={successes}", flush=True)

    summaries, horizon_rows = [], []
    for user_id in user_ids:
        summary, horizons = parse_report(user_id, *responses[user_id])
        summaries.append(summary)
        horizon_rows.extend(horizons)
    unique_summary = pd.DataFrame(summaries)
    # Map a single authoritative response back to every conforming KSSL pedon row.
    pedon_summary = conforming.merge(unique_summary, on="user_pedon_id", how="left", suffixes=("_kssl", "_nasis"))
    pedon_summary.to_csv(PEDON_OUT, index=False)
    horizon_df = pd.DataFrame(horizon_rows)
    horizon_df.to_csv(HORIZON_OUT, index=False)

    layers = pd.read_csv(KSSL_LAYERS, low_memory=False)
    layers = layers[layers.lims_pedon_id.isin(conforming.lims_pedon_id)].copy()
    kssl_user = conforming[["lims_pedon_id", "user_pedon_id"]].drop_duplicates()
    layers = layers.merge(kssl_user, on="lims_pedon_id", how="left", suffixes=("", "_crosswalk"))
    join_rows = []
    for _, layer in layers.iterrows():
        candidates = horizon_df[horizon_df.user_pedon_id.eq(layer.user_pedon_id)]
        confidence, index, basis = assign_join(layer, candidates)
        row = layer.to_dict()
        row.update({"join_confidence": confidence, "join_basis": basis, "nasis_horizon_row": index})
        if index is not None:
            row.update({f"nasis_{key}": value for key, value in horizon_df.loc[index].to_dict().items()})
        join_rows.append(row)
    joined_df = pd.DataFrame(join_rows)
    joined_df.to_csv(JOIN_OUT, index=False)

    metals = metal_wide()
    master = joined_df.merge(metals, on="lay_id", how="left")
    pedon_context = unique_summary[[
        "user_pedon_id", "drainage_class", "flooding", "ponding", "taxonomy",
        "current_correlated_soil_name", "certified_lab_pedon_description", "record_origin",
    ]].rename(columns={column: f"nasis_{column}" for column in unique_summary.columns if column != "user_pedon_id"})
    master = master.merge(pedon_context, on="user_pedon_id", how="left")
    master.to_csv(MASTER_OUT, index=False)

    retrieval = int(unique_summary.retrieval_success.sum())
    exact_ids = int(unique_summary.exact_identifier_match.sum())
    morph = int(unique_summary.usable_morphology.sum())
    join_counts = joined_df.join_confidence.value_counts().reindex(["EXACT", "HIGH", "AMBIGUOUS", "UNMATCHED"], fill_value=0)
    joined_success = int(join_counts.EXACT + join_counts.HIGH)
    chemistry_columns = [
        column for column in [
            "total_carbon_pct", "estimated_organic_carbon_pct",
            "fe_dithionite_pct", "fe_oxalate_pct", "clay_pct", "sand_pct",
            "silt_pct", "ph_water", "ph_cacl2", "cec_nh4oac_cmol_kg",
            "water_retention_15bar_pct", "water_retention_third_bar_pct",
        ] if column in master.columns
    ]
    master["has_selected_chemistry"] = master[chemistry_columns].notna().any(axis=1).astype(int)
    pedon_master = master.groupby("lims_pedon_id").agg(
        has_morphology=("nasis_matrix_munsell", lambda x: x.fillna("").astype(str).str.strip().ne("").any()),
        has_chemistry=("has_selected_chemistry", lambda x: pd.to_numeric(x, errors="coerce").fillna(0).gt(0).any()),
        has_mir=("mir_scan_count", lambda x: pd.to_numeric(x, errors="coerce").fillna(0).gt(0).any()),
        has_depths=("top_depth_cm", lambda x: x.notna().any()),
        has_matrix=("nasis_matrix_chroma", lambda x: x.notna().any()),
        has_texture=("nasis_field_texture", lambda x: x.fillna("").astype(str).str.strip().ne("").any()),
        has_wetness_input=("nasis_wetness_morphology_raw", lambda x: x.fillna("").astype(str).str.strip().ne("").any()),
    )
    combo = int((pedon_master.has_morphology & pedon_master.has_chemistry & pedon_master.has_mir).sum())
    # Coverage bundle only, not a hydric rule: depth + Munsell + texture + at
    # least one explicitly rendered wetness/organic morphology input.
    quantitative_ready = int((pedon_master.has_depths & pedon_master.has_matrix & pedon_master.has_texture & pedon_master.has_wetness_input).sum())

    coverage_fields = {
        "top/bottom depth": horizon_df.top_depth_cm.notna() & horizon_df.bottom_depth_cm.notna(),
        "horizon thickness": horizon_df.thickness_cm.notna(),
        "matrix hue/value/chroma": horizon_df.matrix_hue.ne("") & horizon_df.matrix_value.notna() & horizon_df.matrix_chroma.notna(),
        "redox percentage": horizon_df.redox_percentage_max.notna(),
        "redox concentrations": horizon_df.redox_concentration_rendered.notna(),
        "redox depletions": horizon_df.redox_depletion_rendered.notna(),
        "reduced matrix": horizon_df.reduced_matrix_rendered.notna(),
        "organic horizon/material": horizon_df.organic_horizon_or_material_rendered.notna(),
        "texture": horizon_df.field_texture.fillna("").ne(""),
    }
    coverage = pd.DataFrame([
        {"input": name, "horizons": int(mask.sum()), "pedons": int(horizon_df.loc[mask, "user_pedon_id"].nunique())}
        for name, mask in coverage_fields.items()
    ])
    for name, column in [("drainage class", "drainage_class"), ("flooding", "flooding"), ("ponding", "ponding"), ("taxonomy", "taxonomy")]:
        mask = unique_summary[column].fillna("").ne("")
        coverage.loc[len(coverage)] = {"input": name, "horizons": "pedon-level", "pedons": int(mask.sum())}

    join_table = pd.DataFrame({
        "confidence": join_counts.index,
        "horizons": join_counts.values,
        "percent": (100 * join_counts.values / len(joined_df)).round(2),
    })
    report = f"""# Full NEON-KSSL-NASIS retrieval and horizon linkage report

## Scope

The official NRCS NASIS **Pedon Description by User Pedon ID** report was queried for {len(user_ids)} unique standardized IDs representing {len(conforming)} conforming NEON/KSSL pedon rows. Raw HTML is retained in `outputs/tables/kssl_neon_linkage/nasis_raw_html`. The source Access database was opened only by the separate read-only Fe/Mn extractor and was not modified.

## Retrieval metrics

| Metric | Result |
|---|---:|
| Unique-ID retrieval success | {retrieval}/{len(user_ids)} ({100*retrieval/len(user_ids):.2f}%) |
| Exact-ID match | {exact_ids}/{len(user_ids)} ({100*exact_ids/len(user_ids):.2f}%) |
| Usable morphology recovery | {morph}/{retrieval} ({100*morph/retrieval if retrieval else 0:.2f}%) |
| KSSL horizon join success (`EXACT` + `HIGH`) | {joined_success}/{len(joined_df)} ({100*joined_success/len(joined_df):.2f}%) |
| Pedons with chemistry + MIR + joined morphology | {combo}/{len(pedon_master)} |
| Pedons meeting the provisional quantitative-input coverage bundle | {quantitative_ready}/{len(pedon_master)} |

The last metric is not a hydric classification. It requires depth, quantitative matrix Munsell, texture, and at least one explicitly rendered wetness/organic morphology input so official rules can be evaluated later.

## Horizon join confidence

{md_table(join_table)}

## Potential hydric-criteria input coverage

{md_table(coverage)}

## Parsing and linkage safeguards

- Missing rendered morphology remains blank, not false or zero.
- `EXACT` requires normalized designation and top/bottom depth agreement.
- `HIGH` requires a unique depth match or a unique designation-plus-sequence match.
- Multiple candidates are `AMBIGUOUS`; no morphology is forced onto them.
- Fe and Mn measurements retain analyte/method-specific columns and a separate long-form provenance export.
- Horizon suffixes, including `g`, are not treated as hydric labels.
"""
    REPORT_OUT.write_text(report, encoding="utf-8")
    print(f"Wrote full outputs. Retrieval={retrieval}/{len(user_ids)}; joined={joined_success}/{len(joined_df)}", flush=True)


if __name__ == "__main__":
    main()
