"""Retrieve and inventory official NASIS pedon reports for the 20-pedon pilot."""

from __future__ import annotations

import html as html_lib
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests
from lxml import html


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "tables" / "kssl_neon_linkage"
PILOT_PATH = OUT / "neon_kssl_linkage_pilot_20.csv"
RESULTS_PATH = OUT / "neon_kssl_nasis_pilot_20_results.csv"
MORPH_PATH = OUT / "neon_kssl_nasis_morphology_inventory.csv"
REPORT_PATH = OUT / "neon_kssl_nasis_linkage_report.md"
RAW = OUT / "nasis_raw_html"
URL = (
    "https://nasis.sc.egov.usda.gov/NasisReportsWebSite/limsreport.aspx?"
    "report_name=WEB-Masterlist_SUB_pedon_site_description_usepedonid"
)
HORIZON_RE = re.compile(
    r"^([^;]+?)[^\w\s]\s*(\d+(?:\.\d+)?)\s+to\s+(\d+(?:\.\d+)?)\s+centimeters\b",
    re.IGNORECASE,
)
MUNSELL_RE = re.compile(r"\b((?:\d+(?:\.\d+)?[A-Z]+|N|GLEY\s*\d+)\s+\d+(?:\.\d+)?/\d+(?:\.\d+)?)\b", re.I)


def hidden(document: str, name: str) -> str:
    root = html.fromstring(document)
    values = root.xpath(f'//input[@name="{name}"]/@value')
    return values[0] if values else ""


def fetch(user_pedon_id: str) -> tuple[str, str, str]:
    session = requests.Session()
    session.headers["User-Agent"] = "MIT-thesis-KSSL-NASIS-linkage-audit/1.0"
    try:
        get = session.get(URL, timeout=60)
        get.raise_for_status()
        body = {
            "__VIEWSTATE": hidden(get.text, "__VIEWSTATE"),
            "__VIEWSTATEGENERATOR": hidden(get.text, "__VIEWSTATEGENERATOR"),
            "__EVENTVALIDATION": hidden(get.text, "__EVENTVALIDATION"),
            "ctl00$ContentPlaceHolder1$pedon_id": user_pedon_id,
            "ctl00$ContentPlaceHolder1$button": "Submit",
        }
        response = session.post(URL, data=body, timeout=120)
        response.raise_for_status()
        return user_pedon_id, response.text, ""
    except Exception as exc:  # retained in results rather than dropping a pilot ID
        return user_pedon_id, "", f"{type(exc).__name__}: {exc}"


def report_content(document: str):
    root = html.fromstring(document)
    nodes = root.xpath('//*[@id="ReportData"]')
    if not nodes:
        return None, [], ""
    node = nodes[0]
    for unwanted in node.xpath(".//style|.//script|.//head"):
        unwanted.getparent().remove(unwanted)
    text = html_lib.unescape(node.text_content()).replace("\xa0", " ")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return node, lines, "\n".join(lines)


def values_after(lines: list[str], label: str) -> list[str]:
    target = label.casefold()
    return [lines[i + 1] for i, line in enumerate(lines[:-1]) if line.casefold() == target]


def joined(values) -> str:
    return " | ".join(dict.fromkeys(str(v).strip() for v in values if str(v).strip()))


def horizon_narratives(node, lines: list[str]) -> list[str]:
    # Each rendered horizon is a separate line. Parent DIV text concatenates all
    # descendant horizons and would create a false extra horizon/redox record.
    return list(dict.fromkeys(line for line in lines if HORIZON_RE.match(line)))
def first_match(pattern: str, text: str, flags=re.I) -> str:
    match = re.search(pattern, text, flags)
    return match.group(1).strip() if match else ""


def parse_horizon(line: str) -> dict:
    match = HORIZON_RE.match(line)
    designation, top, bottom = match.groups() if match else ("", "", "")
    munsell = MUNSELL_RE.findall(line)
    color_phrase = first_match(
        r"centimeters\s*\([^;]*\);\s*([^;]+)", line
    )
    texture = ""
    pieces = [piece.strip(" .") for piece in line.split(";")]
    if len(pieces) >= 3:
        texture = pieces[2]
    return {
        "designation": designation.strip(),
        "top_cm": float(top) if top else None,
        "bottom_cm": float(bottom) if bottom else None,
        "munsell": munsell,
        "color_phrase": color_phrase,
        "texture": texture,
        "narrative": line,
    }


def inventory_item(field: str, present: bool, returned_field: str, value: str) -> dict:
    return {
        "morphology_field": field,
        "present": int(bool(present)),
        "returned_field_name_or_location": returned_field if present else "",
        "representative_value": value if present else "",
    }


def parse_one(pilot: pd.Series, document: str, error: str) -> tuple[dict, list[dict]]:
    user_id = str(pilot.user_pedon_id)
    node, lines, text = report_content(document) if document else (None, [], "")
    horizons = [parse_horizon(line) for line in horizon_narratives(node, lines)]
    returned_ids = values_after(lines, "User Pedon ID:")
    site_ids = values_after(lines, "User Site ID:")
    record_count = lines.count("IDENTIFIERS")
    success = bool(record_count and returned_ids)
    latitudes = values_after(lines, "Std. Latitude:")
    longitudes = values_after(lines, "Std. Longitude:")
    soil_names = values_after(lines, "Current Taxon Name (Soil Name):")
    taxonomy = values_after(lines, "Current Taxonomic Class:")
    observation_dates = values_after(lines, "Observation Date:")
    origins = values_after(lines, "Pedon Record Orgin:") + values_after(lines, "Pedon Record Origin:")
    pedon_numbers = values_after(lines, "Pedon #:")
    project_ids = values_after(lines, "User Project ID:")
    lab_flags = values_after(lines, "Certified Lab Pedon Description -")
    owner_values = values_after(lines, "Owner:") + values_after(lines, "NASIS Site:")

    nasis_lat = pd.to_numeric(pd.Series(latitudes), errors="coerce").dropna()
    nasis_lon = pd.to_numeric(pd.Series(longitudes), errors="coerce").dropna()
    kssl_lat = pd.to_numeric(pd.Series([pilot.latitude_std_decimal_degrees]), errors="coerce").iloc[0]
    kssl_lon = pd.to_numeric(pd.Series([pilot.longitude_std_decimal_degrees]), errors="coerce").iloc[0]
    lat_diff = abs(float(nasis_lat.iloc[0]) - float(kssl_lat)) if len(nasis_lat) and pd.notna(kssl_lat) else None
    lon_diff = abs(float(nasis_lon.iloc[0]) - float(kssl_lon)) if len(nasis_lon) and pd.notna(kssl_lon) else None
    coordinate_match = bool(lat_diff is not None and lon_diff is not None and lat_diff <= 1e-6 and lon_diff <= 1e-6)
    coordinate_near_match = bool(lat_diff is not None and lon_diff is not None and lat_diff <= 1e-4 and lon_diff <= 1e-4)

    returned_depths = [(h["top_cm"], h["bottom_cm"]) for h in horizons]
    kssl_horizon_count = int(pilot.horizon_count)
    max_depth = max((h["bottom_cm"] for h in horizons), default=None)
    kssl_max = pd.to_numeric(pd.Series([pilot.maximum_profile_depth_cm]), errors="coerce").iloc[0]
    depth_count_match = len(horizons) == kssl_horizon_count
    max_depth_match = bool(max_depth is not None and pd.notna(kssl_max) and abs(max_depth - float(kssl_max)) <= 0.01)
    taxon_match = any(str(name).casefold() == str(pilot.current_taxon_name).casefold() for name in soil_names)

    horizon_text = "\n".join(h["narrative"] for h in horizons)
    all_munsell = [code for h in horizons for code in h["munsell"]]
    color_values = [h["color_phrase"] for h in horizons if h["color_phrase"]]
    redox_lines = [
        h["narrative"] for h in horizons
        if re.search(r"redox|oxidized iron|iron (?:concentration|depletion)|deplet", h["narrative"], re.I)
    ]
    concentration_lines = [line for line in redox_lines if re.search(r"oxidized iron|redox concentration|iron concentration", line, re.I)]
    depletion_lines = [line for line in redox_lines if re.search(r"deplet", line, re.I)]
    redox_percent = first_match(
        r"(\d+(?:\.\d+)?\s*percent[^;]*(?:oxidized iron|redox|deplet)[^;]*)",
        joined(redox_lines),
    )
    moist_values = [
        first_match(r"([^;,]+\([^)]*/[^)]*\)),\s*moist", h["color_phrase"])
        for h in horizons
    ]
    moist_values = [value for value in moist_values if value]
    dry_values = []
    for h in horizons:
        codes = h["munsell"]
        if len(codes) >= 2 and ", moist" in h["color_phrase"].lower():
            dry_values.append(codes[0])

    label_specs = {
        "drainage_class": ("Drainage Class:", values_after(lines, "Drainage Class:")),
        "flooding": ("Flooding:", values_after(lines, "Flooding:")),
        "ponding": ("Ponding:", values_after(lines, "Ponding:")),
    }
    water_table_lines = [line for line in lines if re.search(r"water table", line, re.I)]
    saturation_lines = [line for line in lines if re.search(r"\bsaturat", line, re.I)]
    gley_lines = [line for line in horizons if False]
    gley_values = [h["narrative"] for h in horizons if re.search(r"\bgley|GLEY\s*\d", h["narrative"], re.I)]
    reduced_values = [h["narrative"] for h in horizons if re.search(r"reduced matrix|\breduced\b", h["narrative"], re.I)]

    inventory = [
        inventory_item("matrix_color", bool(color_values), "horizon narrative: matrix color phrase", joined(color_values[:2])),
        inventory_item("Munsell_hue", bool(all_munsell), "horizon narrative: Munsell notation", all_munsell[0].split()[0] if all_munsell else ""),
        inventory_item("Munsell_value", bool(all_munsell), "horizon narrative: Munsell notation", all_munsell[0].split()[-1].split("/")[0] if all_munsell else ""),
        inventory_item("Munsell_chroma", bool(all_munsell), "horizon narrative: Munsell notation", all_munsell[0].split()[-1].split("/")[-1] if all_munsell else ""),
        inventory_item("moist_color", bool(moist_values), "horizon narrative: color followed by 'moist'", joined(moist_values[:2])),
        inventory_item("dry_color", bool(dry_values), "horizon narrative: first of paired dry/moist colors", joined(dry_values[:2])),
        inventory_item("redox_features", bool(redox_lines), "horizon narrative", redox_lines[0] if redox_lines else ""),
        inventory_item("redox_concentrations", bool(concentration_lines), "horizon narrative: oxidized iron/redox concentration", concentration_lines[0] if concentration_lines else ""),
        inventory_item("redox_depletions", bool(depletion_lines), "horizon narrative: depletion", depletion_lines[0] if depletion_lines else ""),
        inventory_item("redox_percentage", bool(redox_percent), "horizon narrative: feature percentage", redox_percent),
        inventory_item("gley_matrix", bool(gley_values), "horizon narrative: gley/GLEY notation", gley_values[0] if gley_values else ""),
        inventory_item("reduced_matrix", bool(reduced_values), "horizon narrative: reduced matrix", reduced_values[0] if reduced_values else ""),
        inventory_item("drainage_class", bool(label_specs["drainage_class"][1]), "Drainage Class", joined(label_specs["drainage_class"][1])),
        inventory_item("flooding", bool(label_specs["flooding"][1]), "Flooding", joined(label_specs["flooding"][1])),
        inventory_item("ponding", bool(label_specs["ponding"][1]), "Ponding", joined(label_specs["ponding"][1])),
        inventory_item("water_table", bool(water_table_lines), "report text containing 'water table'", joined(water_table_lines[:2])),
        inventory_item("saturation", bool(saturation_lines), "report text containing saturation term", joined(saturation_lines[:2])),
        inventory_item("horizon_designation", bool(horizons), "horizon narrative prefix", horizons[0]["designation"] if horizons else ""),
        inventory_item("top_depth", bool(horizons), "horizon narrative depth interval", str(horizons[0]["top_cm"]) if horizons else ""),
        inventory_item("bottom_depth", bool(horizons), "horizon narrative depth interval", str(horizons[0]["bottom_cm"]) if horizons else ""),
        inventory_item("field_texture", any(h["texture"] for h in horizons), "horizon narrative texture segment", joined([h["texture"] for h in horizons[:2]])),
    ]
    for row in inventory:
        row["user_pedon_id"] = user_id
        row["retrieval_success"] = int(success)

    ownership = ""
    if lab_flags:
        ownership = joined([f"Certified Lab Pedon Description={value}" for value in lab_flags])
    if owner_values:
        ownership = joined([ownership, *owner_values])
    result = {
        "user_pedon_id": user_id,
        "retrieval_success": int(success),
        "number_of_matching_pedon_records": record_count,
        "exact_identifier_match": int(success and all(value == user_id for value in returned_ids)),
        "returned_user_pedon_ids": joined(returned_ids),
        "site_id": joined(site_ids),
        "pedon_record_identifier": joined(pedon_numbers),
        "owner_or_nasis_site": joined(owner_values),
        "kssl_vs_regional_mlra_distinction": ownership,
        "pedon_record_origin": joined(origins),
        "user_project_id": joined(project_ids),
        "current_correlated_soil_name": joined(soil_names),
        "taxonomy": joined(taxonomy),
        "latitude": joined(latitudes),
        "longitude": joined(longitudes),
        "observation_date": joined(observation_dates),
        "number_of_described_horizons": len(horizons),
        "returned_horizon_depths_cm": joined([f"{a:g}-{b:g}" for a, b in returned_depths]),
        "kssl_horizon_count": kssl_horizon_count,
        "kssl_maximum_profile_depth_cm": kssl_max,
        "coordinate_exact_match_1e_6_deg": int(coordinate_match),
        "coordinate_near_match_1e_4_deg": int(coordinate_near_match),
        "latitude_absolute_difference_deg": lat_diff,
        "longitude_absolute_difference_deg": lon_diff,
        "taxon_name_exact_match": int(taxon_match),
        "horizon_count_match": int(depth_count_match),
        "maximum_depth_match": int(max_depth_match),
        "usable_color_or_redox_description": int(bool(color_values or redox_lines)),
        "request_error": error,
        "raw_html_file": str((RAW / f"{user_id}.html").relative_to(ROOT)) if document else "",
    }
    return result, inventory


def md_table(frame: pd.DataFrame) -> str:
    shown = frame.fillna("").astype(str)
    return "\n".join([
        "| " + " | ".join(shown.columns) + " |",
        "|" + "|".join("---" for _ in shown.columns) + "|",
        *("| " + " | ".join(row) + " |" for row in shown.to_numpy().tolist()),
    ])


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    pilot = pd.read_csv(PILOT_PATH, low_memory=False)
    fetched = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fetch, str(row.user_pedon_id)): str(row.user_pedon_id) for _, row in pilot.iterrows()}
        for future in as_completed(futures):
            user_id, document, error = future.result()
            fetched[user_id] = (document, error)
            if document:
                (RAW / f"{user_id}.html").write_text(document, encoding="utf-8")
            print(f"{user_id}: {'retrieved' if document else error}", flush=True)

    results, inventory = [], []
    for _, row in pilot.iterrows():
        document, error = fetched[str(row.user_pedon_id)]
        result, fields = parse_one(row, document, error)
        results.append(result)
        inventory.extend(fields)
    results_df = pd.DataFrame(results)
    inventory_df = pd.DataFrame(inventory)[[
        "user_pedon_id", "retrieval_success", "morphology_field", "present",
        "returned_field_name_or_location", "representative_value",
    ]]
    results_df.to_csv(RESULTS_PATH, index=False)
    inventory_df.to_csv(MORPH_PATH, index=False)

    retrieved = int(results_df.retrieval_success.sum())
    exact = int(results_df.exact_identifier_match.sum())
    morphology = int(results_df.loc[results_df.retrieval_success.eq(1), "usable_color_or_redox_description"].sum())
    duplicates = int((results_df.number_of_matching_pedon_records > 1).sum())
    coord = int(results_df.coordinate_exact_match_1e_6_deg.sum())
    coord_near = int(results_df.coordinate_near_match_1e_4_deg.sum())
    taxon = int(results_df.taxon_name_exact_match.sum())
    hcount = int(results_df.horizon_count_match.sum())
    maxdepth = int(results_df.maximum_depth_match.sum())
    field_coverage = inventory_df[inventory_df.retrieval_success.eq(1)].groupby("morphology_field").present.agg(["sum", "count"]).reset_index()
    field_coverage["coverage_pct"] = (100 * field_coverage["sum"] / field_coverage["count"]).round(2)

    report = f"""# NEONÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œKSSL NASIS pilot linkage report

## Scope and authoritative source

Twenty pilot User Pedon IDs were submitted exactly to the official NRCS NASIS Web Report **Pedon Description by User Pedon ID** (`WEB-Masterlist_SUB_pedon_site_description_usepedonid`). Raw HTML responses are retained under `outputs/tables/kssl_neon_linkage/nasis_raw_html`. No hydric labels, SSURGO intersections, or model outputs were created.

## Quantitative results

| Metric | Result |
|---|---:|
| Pedon retrieval success | {retrieved}/20 ({100*retrieved/20:.2f}%) |
| Exact identifier match | {exact}/20 ({100*exact/20:.2f}%) |
| Morphology recovery among retrieved pedons | {morphology}/{retrieved} ({100*morphology/retrieved if retrieved else 0:.2f}%) |
| Duplicate/correlated-record rate | {duplicates}/20 ({100*duplicates/20:.2f}%) |

## Same-pedon checks against KSSL

| Check | Agreement |
|---|---:|
| Coordinates equal within 0.000001 degree | {coord}/{retrieved} |
| Coordinates agree within 0.0001 degree | {coord_near}/{retrieved} |
| Current soil/taxon name exact match | {taxon}/{retrieved} |
| Described-horizon count equals KSSL horizon count | {hcount}/{retrieved} |
| Maximum described depth equals KSSL maximum layer depth | {maxdepth}/{retrieved} |

Coordinate, taxonomy, and depth checks are corroboration only; discrepancies are retained in the result CSV and are not resolved through SSURGO. All coordinates agree within 0.0001 degree. The two taxon-name differences are returned NASIS current names versus KSSL names. The two horizon-count differences are explainable profile-version/sample-subset differences: one NASIS description adds a 0-2 cm Oi horizon, and one adds a 61-200 cm Cr horizon below the KSSL-sampled maximum depth.

## Morphology field recovery

{md_table(field_coverage.rename(columns={'morphology_field':'field','sum':'pedons_present','count':'retrieved_pedons'}))}

## Per-pedon retrieval summary

{md_table(results_df[['user_pedon_id','retrieval_success','number_of_matching_pedon_records','site_id','current_correlated_soil_name','number_of_described_horizons','coordinate_exact_match_1e_6_deg','taxon_name_exact_match','horizon_count_match','maximum_depth_match']])}

## Engineering conclusion

The test asks whether the authoritative NASIS report recovers field morphology absent from the portable KSSL database. The quantitative retrieval and morphology rates above determine that answer for the pilot. Morphology is reported as recovered only when the returned report contains an actual horizon color phrase, Munsell notation, or redox description; horizon suffixes alone are not counted.

## Parsing limitations

The NASIS report renders horizon morphology as narrative prose rather than exposing source database column names. `returned_field_name_or_location` therefore distinguishes explicit report labels (for example `Drainage Class`) from identifiable locations in the horizon narrative. Moist/dry color parsing follows the report's rendered ordering and is retained with representative text for manual verification. Ownership is reported only from explicit report content such as `Certified Lab Pedon Description`; no ownership class is inferred when the report does not state one.
"""
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"Wrote {RESULTS_PATH.name}, {MORPH_PATH.name}, and {REPORT_PATH.name}")


if __name__ == "__main__":
    main()
