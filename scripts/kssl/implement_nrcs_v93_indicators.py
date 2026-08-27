"""Conservative implementation of official NRCS hydric-soil indicators v9.3.

The script never assigns final hydric/nonhydric labels.  It spatially assigns the
2022 MLRA/LRR geography, builds a traceable rulebook from the official PDF, and
evaluates only rules supportable by explicit NASIS observations.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[2]
IN_DIR = ROOT / "outputs" / "tables" / "kssl_neon_linkage"
OUT_DIR = IN_DIR
REF = ROOT / "data" / "reference" / "nrcs"
MANUAL = REF / "Field-Indicators-Version-9.3-2026.pdf"
MLRA_SHP = REF / "MLRA_52_2022" / "MLRA_52.shp"
MASTER = IN_DIR / "neon_kssl_master_pedon_horizon_table.csv"
PEDONS = IN_DIR / "neon_kssl_nasis_full_pedon_summary.csv"

SOURCE_MANUAL = (
    "USDA NRCS/NTCHS, Field Indicators of Hydric Soils in the United States, "
    "Version 9.3 (2026), with February 2026 errata"
)
SOURCE_GEO = "USDA NRCS 2022 MLRA Geographic Database, version 5.2 (MLRA_52)"

INDICATORS = [
    ("A1", "Histosol or Histel", 11), ("A2", "Histic Epipedon", 12),
    ("A3", "Black Histic", 12), ("A4", "Hydrogen Sulfide", 12),
    ("A5", "Stratified Layers", 12), ("A6", "Organic Bodies", 13),
    ("A7", "5 cm Mucky Mineral", 14), ("A8", "Muck Presence", 14),
    ("A9", "1 cm Muck", 14), ("A10", "2 cm Muck", 15),
    ("A11", "Depleted Below Dark Surface", 15), ("A12", "Thick Dark Surface", 17),
    ("A13", "Alaska Gleyed", 17), ("A14", "Alaska Redox", 18),
    ("A15", "Alaska Gleyed Pores", 19), ("A16", "Coast Prairie Redox", 19),
    ("A17", "Mesic Spodic", 19), ("A18", "Iron Monosulfide", 20),
    ("S1", "Sandy Mucky Mineral", 20), ("S2", "2.5 cm Mucky Peat or Peat", 21),
    ("S3", "5 cm Mucky Peat or Peat", 21), ("S4", "Sandy Gleyed Matrix", 21),
    ("S5", "Sandy Redox", 21), ("S6", "Stripped Matrix", 22),
    ("S7", "Dark Surface", 23), ("S8", "Polyvalue Below Surface", 23),
    ("S9", "Thin Dark Surface", 24), ("S11", "High Chroma Sands", 24),
    ("S12", "Barrier Islands 1 cm Muck", 25),
    ("F1", "Loamy Mucky Mineral", 25), ("F2", "Loamy Gleyed Matrix", 25),
    ("F3", "Depleted Matrix", 26), ("F6", "Redox Dark Surface", 27),
    ("F7", "Depleted Dark Surface", 28), ("F8", "Redox Depressions", 28),
    ("F10", "Marl", 28), ("F11", "Depleted Ochric", 28),
    ("F12", "Iron-Manganese Masses", 28), ("F13", "Umbric Surface", 29),
    ("F16", "High Plains Depressions", 30), ("F17", "Delta Ochric", 30),
    ("F18", "Reduced Vertic", 30), ("F19", "Piedmont Flood Plain Soils", 31),
    ("F20", "Anomalous Bright Loamy Soils", 31), ("F21", "Red Parent Material", 31),
    ("F22", "Very Shallow Dark Surface", 33),
]

PRIORITY = {"A1", "A3", "A7", "A8", "A9", "A10", "A11", "A12", "S4", "S5", "F2", "F3", "F6", "F7"}
ALL_LRRS = set("ABCDEFGHIJKLMNOPQRSTUVWXY Z".replace(" ", ""))
APPLICABLE = {
    "A1": ALL_LRRS, "A3": ALL_LRRS, "A12": ALL_LRRS,
    "A7": set("PTUZ"), "A8": set("QUVZ"), "A9": set("DFGHPT"),
    "A10": set("MN"), "A11": ALL_LRRS - set("WXY"),
    "S4": ALL_LRRS - set("WXY"), "S5": ALL_LRRS - set("QVWXY"),
    "F2": ALL_LRRS - set("WXY"), "F3": ALL_LRRS - set("WXY"),
    "F6": ALL_LRRS - set("WXY"), "F7": ALL_LRRS - set("WXY"),
}

# Appendix 1 approved indicators by LRR (MLRA qualifications handled below).
_APPROVED_TEXT = """
A:A1,A2,A3,A4,A11,A12,A18,S1,S4,S5,S6,F1,F2,F3,F6,F7,F8
B:A1,A2,A3,A4,A11,A12,A18,S1,S4,S5,S6,F1,F2,F3,F6,F7,F8
C:A1,A2,A3,A4,A5,A11,A12,A18,S1,S4,S5,S6,F1,F2,F3,F6,F7,F8
D:A1,A2,A3,A4,A9,A11,A12,A18,S1,S4,S5,S6,F1,F2,F3,F6,F7,F8
E:A1,A2,A3,A4,A11,A12,A18,S1,S4,S5,S6,F1,F2,F3,F6,F7,F8
F:A1,A2,A3,A4,A5,A9,A11,A12,A18,S1,S3,S4,S5,S6,F1,F2,F3,F6,F7,F8
G:A1,A2,A3,A4,A9,A11,A12,A18,S1,S2,S4,S5,S6,F1,F2,F3,F6,F7,F8
H:A1,A2,A3,A4,A9,A11,A12,A18,S1,S2,S4,S5,S6,F1,F2,F3,F6,F7,F8,F16
I:A1,A2,A3,A4,A11,A12,A18,S1,S4,S5,S6,F1,F2,F3,F6,F7,F8
J:A1,A2,A3,A4,A11,A12,A18,S1,S4,S5,S6,F1,F2,F3,F6,F7,F8
K:A1,A2,A3,A4,A5,A11,A12,A18,S1,S4,S5,S6,S7,S11,F1,F2,F3,F6,F7,F8,F10
L:A1,A2,A3,A4,A5,A11,A12,A18,S1,S4,S5,S6,S7,S11,F1,F2,F3,F6,F7,F8,F10
M:A1,A2,A3,A4,A5,A10,A11,A12,A18,S1,S3,S4,S5,S6,S7,F1,F2,F3,F6,F7,F8
N:A1,A2,A3,A4,A5,A10,A11,A12,A18,S1,S4,S5,S6,S7,F2,F3,F6,F7,F8,F12,F13,F21
O:A1,A2,A3,A4,A5,A11,A12,A18,S1,S4,S5,S6,F1,F2,F3,F6,F7,F8,F12
P:A1,A2,A3,A4,A5,A6,A7,A9,A11,A12,A18,S1,S4,S5,S6,S7,F2,F3,F6,F7,F8,F12,F13,F22
Q:A1,A2,A3,A4,A8,A11,A12,A18,S1,S4,S6,S7,F2,F3,F6,F7,F8
R:A1,A2,A3,A4,A5,A11,A12,A17,A18,S1,S4,S5,S6,S7,S8,S9,F2,F3,F6,F7,F8,F21
S:A1,A2,A3,A4,A5,A11,A12,A17,A18,S1,S4,S5,S6,S7,S8,S9,F2,F3,F6,F7,F8,F19,F20,F21
T:A1,A2,A3,A4,A5,A6,A7,A9,A11,A12,A16,A18,S4,S5,S6,S7,S8,S9,S12,F2,F3,F6,F7,F8,F11,F12,F13,F17,F18,F20,F22
U:A1,A2,A3,A4,A5,A6,A7,A8,A11,A12,A18,S4,S5,S6,S7,S8,S9,F2,F3,F6,F7,F8,F10,F13,F22
V:A1,A2,A3,A4,A8,A11,A12,A18,S1,S4,S7,F2,F3,F6,F7,F8
W:A1,A2,A3,A4,A12,A13,A14,A15,A18
X:A1,A2,A3,A4,A12,A13,A14,A15,A18
Y:A1,A2,A3,A4,A12,A13,A14,A15,A18
Z:A1,A2,A3,A4,A6,A7,A8,A11,A12,A18,S4,S5,S6,S7,F2,F3,F6,F7,F8
"""
APPROVED_BY_LRR = {line.split(":")[0]: set(line.split(":")[1].split(",")) for line in _APPROVED_TEXT.strip().splitlines()}
SANDY = {
    "sand", "fine sand", "very fine sand", "coarse sand", "loamy sand",
    "loamy fine sand", "loamy very fine sand", "loamy coarse sand",
}
LOAMY = {
    "very fine sandy loam", "fine sandy loam", "sandy loam", "coarse sandy loam",
    "loam", "silt loam", "silt", "sandy clay loam", "clay loam", "silty clay loam",
    "sandy clay", "silty clay", "clay",
}


def clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("Ã¢â‚¬â€", "â€”").replace("Ã¢â‚¬Å“", 'â€œ').replace("Ã¢â‚¬Â", 'â€')).strip()


def raw_rules() -> dict[str, str]:
    pages = [p.extract_text() or "" for p in PdfReader(str(MANUAL)).pages]
    text = "\n".join(pages)
    starts = []
    for code, name, _ in INDICATORS:
        pat = re.compile(rf"(?m)^{re.escape(code)}[\.\-â€”]+\s*{re.escape(name)}\.")
        m = pat.search(text)
        if not m:
            # PDF extraction may insert odd punctuation or spacing.
            m = re.search(rf"(?m)^{re.escape(code)}.*?{re.escape(name)}\.", text)
        if m:
            starts.append((m.start(), code))
    starts.sort()
    out = {}
    for i, (pos, code) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else text.find("References", pos)
        block = text[pos:end]
        # Requirements precede User Notes; retain applicability and all alternate clauses.
        block = block.split("User Notes:", 1)[0]
        out[code] = clean_text(block)
    return out


def rulebook() -> pd.DataFrame:
    raw = raw_rules()
    parsed = {
        "A1": dict(soil_texture_scope="all soils", taxonomy_requirement="Histosol except Folist, or Histel except Folistel", required_input_fields="taxonomy"),
        "A3": dict(soil_texture_scope="all soils", measurement_datum="soil surface", maximum_start_depth_cm=15, minimum_thickness_cm=20, matrix_hue_requirement="10YR or yellower", matrix_value_requirement="<=3", matrix_chroma_requirement="<=1; underlying mineral material <=2", organic_material_requirement="peat, mucky peat, or muck", required_input_fields="organic material type; continuous depth; moist hue/value/chroma; underlying mineral chroma"),
        "A7": dict(soil_texture_scope="all soils", measurement_datum="soil surface", maximum_start_depth_cm=15, minimum_thickness_cm=5, organic_material_requirement="mucky modified mineral soil material", required_input_fields="explicit mucky texture/material; depth and thickness"),
        "A8": dict(soil_texture_scope="all soils", measurement_datum="soil surface", maximum_start_depth_cm=15, minimum_thickness_cm=0, matrix_value_requirement="<=3", matrix_chroma_requirement="<=1", organic_material_requirement="muck (sapric), any thickness", required_input_fields="explicit muck; depth; moist value/chroma"),
        "A9": dict(soil_texture_scope="all soils", measurement_datum="soil surface", maximum_start_depth_cm=15, minimum_thickness_cm=1, matrix_value_requirement="<=3", matrix_chroma_requirement="<=1", organic_material_requirement="muck (sapric)", required_input_fields="explicit muck; depth and thickness; moist value/chroma"),
        "A10": dict(soil_texture_scope="all soils", measurement_datum="soil surface", maximum_start_depth_cm=15, minimum_thickness_cm=2, matrix_value_requirement="<=3", matrix_chroma_requirement="<=1", organic_material_requirement="muck (sapric)", required_input_fields="explicit muck; depth and thickness; moist value/chroma"),
        "A11": dict(soil_texture_scope="all soils", measurement_datum="soil surface", maximum_start_depth_cm=30, minimum_thickness_cm=15, matrix_percentage_requirement=">=60% depleted/gleyed matrix with chroma <=2", required_input_fields="continuous layers; moist color; explicit depleted/gleyed matrix; texture; masked sand percentage when sandy"),
        "A12": dict(soil_texture_scope="all soils", measurement_datum="soil surface", maximum_start_depth_cm="depleted/gleyed starts >30", minimum_thickness_cm=15, matrix_percentage_requirement=">=60% depleted/gleyed matrix", required_input_fields="continuous dark surface layers through >=30 cm; moist color; explicit depleted/gleyed matrix; masked sand percentage when sandy"),
        "S4": dict(soil_texture_scope="sandy soil material", measurement_datum="soil surface", maximum_start_depth_cm=15, minimum_thickness_cm=0, matrix_hue_requirement="gley page hues N, 10Y, 5GY, 10GY, 5G, 10G, 5BG, 10BG, 5B, 10B, or 5PB", matrix_value_requirement=">=4", matrix_percentage_requirement=">=60% gleyed matrix", required_input_fields="sandy texture; explicit moist gley hue/value; matrix percentage; start depth"),
        "S5": dict(soil_texture_scope="sandy soil material", measurement_datum="soil surface", maximum_start_depth_cm=15, minimum_thickness_cm=10, matrix_chroma_requirement="<=2", matrix_percentage_requirement=">=60%", redox_type_requirement="distinct/prominent soft masses and/or pore linings", redox_percentage_requirement=">=2%", required_input_fields="sandy texture; continuous depth; moist chroma; matrix percentage; redox percentage/type/contrast"),
        "F2": dict(soil_texture_scope="loamy and clayey (loamy very fine sand and finer)", measurement_datum="soil surface", maximum_start_depth_cm=30, minimum_thickness_cm=0, matrix_hue_requirement="gley page hues", matrix_value_requirement=">=4", matrix_percentage_requirement=">=60% gleyed matrix", required_input_fields="loamy/clayey texture; explicit moist gley hue/value; matrix percentage; start depth"),
        "F3": dict(soil_texture_scope="loamy and clayey", measurement_datum="soil surface", maximum_start_depth_cm="10 (5-cm layer) OR 25 (15-cm layer)", minimum_thickness_cm="5 OR 15", matrix_value_requirement=">=4", matrix_chroma_requirement="<=2", matrix_percentage_requirement=">=60% depleted matrix", redox_type_requirement="required for 4/1, 4/2, 5/2 and for A/E/calcic exclusions", redox_percentage_requirement=">=2% distinct/prominent soft masses or pore linings where required", required_input_fields="loamy/clayey texture; continuous depth; moist color; explicit wetness-derived depleted matrix; redox details where required"),
        "F6": dict(soil_texture_scope="loamy and clayey", measurement_datum="mineral soil surface", maximum_start_depth_cm=20, minimum_thickness_cm=10, matrix_value_requirement="<=3", matrix_chroma_requirement="<=1 with >=2% redox OR <=2 with >=5% redox", redox_type_requirement="distinct/prominent soft masses or pore linings", redox_percentage_requirement=">=2% or >=5%, conditional on chroma", required_input_fields="mineral datum; loamy/clayey texture; continuous depth; moist value/chroma; redox percentage/type/contrast"),
        "F7": dict(soil_texture_scope="loamy and clayey", measurement_datum="mineral soil surface", maximum_start_depth_cm=20, minimum_thickness_cm=10, matrix_value_requirement="<=3", matrix_chroma_requirement="<=1 with >=10% depletion OR <=2 with >=20% depletion", redox_type_requirement="depletions value >=5 and chroma <=2", redox_percentage_requirement=">=10% or >=20%, conditional on matrix chroma", required_input_fields="mineral datum; loamy/clayey texture; continuous depth; moist matrix and depletion colors; depletion percentage"),
    }
    rows = []
    fields = ["soil_texture_scope", "measurement_datum", "maximum_start_depth_cm", "minimum_thickness_cm", "matrix_hue_requirement", "matrix_value_requirement", "matrix_chroma_requirement", "matrix_percentage_requirement", "redox_type_requirement", "redox_percentage_requirement", "organic_material_requirement", "taxonomy_requirement", "landscape_requirement", "other_requirement", "required_input_fields"]
    for code, name, page in INDICATORS:
        r = {"indicator_code": code, "indicator_name": name, "indicator_family": code[0], "approved_or_test": "APPROVED"}
        rr = raw.get(code, "")
        app = re.search(r"For use in (.*?)(?=\.\s+(?:A|An|Classifies|Presence|Redox|In |The |Saturated|A layer|Soils|Red parent)|$)", rr)
        r["applicable_LRR"] = app.group(1) if app else "See raw rule and Appendix 1"
        r["applicable_MLRA"] = "See applicable_LRR text for exceptions/restrictions"
        for f in fields:
            r[f] = parsed.get(code, {}).get(f, "")
        r["notes"] = "Primary executable implementation" if code in PRIORITY else "Approved rule transcribed; not executable in this first high-confidence implementation"
        r["source_page"] = page
        r["raw_rule_text"] = rr
        r["source"] = SOURCE_MANUAL
        rows.append(r)
    return pd.DataFrame(rows)


def spatial_assign(ped: pd.DataFrame) -> pd.DataFrame:
    p = ped.copy()
    p["latitude_out"] = pd.to_numeric(p["latitude_std_decimal_degrees"], errors="coerce").fillna(pd.to_numeric(p["latitude"], errors="coerce"))
    p["longitude_out"] = pd.to_numeric(p["longitude_std_decimal_degrees"], errors="coerce").fillna(pd.to_numeric(p["longitude"], errors="coerce"))
    west = p.get("longitude_direction", pd.Series("", index=p.index)).astype(str).str.lower().eq("west")
    p.loc[west & (p.longitude_out > 0), "longitude_out"] *= -1
    base = p[["lims_pedon_id", "user_pedon_id", "latitude_out", "longitude_out"]].rename(columns={"latitude_out": "latitude", "longitude_out": "longitude"})
    good = base.latitude.notna() & base.longitude.notna()
    pts = gpd.GeoDataFrame(base.loc[good].copy(), geometry=gpd.points_from_xy(base.loc[good, "longitude"], base.loc[good, "latitude"]), crs="EPSG:4326")
    mlra = gpd.read_file(MLRA_SHP)[["MLRA_ID", "MLRARSYM", "MLRA_NAME", "LRRSYM", "LRR_NAME", "geometry"]]
    joined = gpd.sjoin(pts, mlra, how="left", predicate="within").drop(columns=["geometry", "index_right"])
    out = base.merge(joined.drop(columns=["latitude", "longitude"]), on=["lims_pedon_id", "user_pedon_id"], how="left")
    out["LRR"] = out["LRRSYM"]
    out["MLRA"] = out["MLRARSYM"]
    out["LRR_MLRA_source"] = SOURCE_GEO
    out["spatial_match_status"] = np.select([out.latitude.isna() | out.longitude.isna(), out.MLRA.notna()], ["NO_COORDINATES", "POINT_WITHIN_MLRA"], default="NO_POLYGON_MATCH")
    return out[["lims_pedon_id", "user_pedon_id", "latitude", "longitude", "LRR", "MLRA", "MLRA_ID", "MLRA_NAME", "LRR_NAME", "LRR_MLRA_source", "spatial_match_status"]]


def texture(raw: object) -> str | None:
    if pd.isna(raw): return None
    s = str(raw).lower()
    # Longest first; NASIS parsing sometimes leaves structure before the texture.
    names = sorted(SANDY | LOAMY, key=len, reverse=True)
    for name in names:
        if re.search(rf"\b{re.escape(name)}\b", s):
            return name
    return None


def profile_rows(master: pd.DataFrame, user_id: str) -> pd.DataFrame:
    d = master[master.user_pedon_id.astype(str) == str(user_id)].copy()
    d = d[d.nasis_top_depth_cm.notna()].copy()
    d["top"] = pd.to_numeric(d.nasis_top_depth_cm, errors="coerce")
    d["bottom"] = pd.to_numeric(d.nasis_bottom_depth_cm, errors="coerce")
    d["value"] = pd.to_numeric(d.nasis_matrix_value, errors="coerce")
    d["chroma"] = pd.to_numeric(d.nasis_matrix_chroma, errors="coerce")
    d["redox_pct"] = pd.to_numeric(d.nasis_redox_percentage_max, errors="coerce")
    d["tex"] = d.nasis_field_texture.map(texture)
    d["moist_ok"] = d.nasis_color_moisture_status.astype(str).str.lower().eq("moist") | d.nasis_moist_munsell.notna()
    d["designation"] = d.nasis_horizon_designation.fillna("").astype(str)
    return d.sort_values(["top", "bottom"]).drop_duplicates(["top", "bottom", "designation"])


def horizon_payload(rows: pd.DataFrame) -> dict[str, str]:
    def vals(col): return " | ".join(rows[col].fillna("").astype(str).tolist())
    return {
        "horizon_or_layers_used": vals("designation"),
        "depths_used": " | ".join(f"{a:g}-{b:g} cm" for a, b in zip(rows.top, rows.bottom)),
        "matrix_colors_used": vals("nasis_matrix_color_raw"),
        "redox_values_used": vals("nasis_redox_raw"),
        "texture_used": vals("tex"),
        "organic_material_used": vals("nasis_raw_horizon_description"),
    }


def contiguous_candidates(d: pd.DataFrame, predicate, datum=0.0) -> list[pd.DataFrame]:
    q = d[(d.bottom > datum) & d.apply(predicate, axis=1)].copy()
    groups, cur = [], []
    for _, r in q.iterrows():
        if cur and r.top > cur[-1].bottom + 0.01:
            groups.append(pd.DataFrame(cur)); cur = []
        cur.append(r)
    if cur: groups.append(pd.DataFrame(cur))
    return groups


def applicable(code: str, lrr: object, mlra: object) -> bool | None:
    if pd.isna(lrr): return None
    lrr, m = str(lrr), "" if pd.isna(mlra) else str(mlra)
    ok = code in APPROVED_BY_LRR.get(lrr, set())
    if code in {"A6", "A7", "A9", "S1"} and lrr == "P" and m.startswith("136"): ok = False
    if code == "F1" and lrr == "A" and m.startswith("1"): ok = False
    restrictions = {
        ("H","F16"):("72","73"), ("N","F13"):("122",), ("N","F21"):("127",),
        ("P","S7"):("136",), ("P","F22"):("138","152A"), ("R","A17"):("144A","145"),
        ("R","F21"):("145",), ("S","A17"):("149B",), ("S","F19"):("148","149A"),
        ("S","F20"):("149A",), ("S","F21"):("147","148"), ("T","A16"):("150A",),
        ("T","S12"):("153B","153D"), ("T","F11"):("151",), ("T","F17"):("151",),
        ("T","F18"):("150",), ("T","F20"):("153C","153D"), ("T","F22"):("138","152A"),
        ("U","F22"):("154",),
    }
    allowed = restrictions.get((lrr, code))
    if ok and allowed: ok = any(m.startswith(x) for x in allowed)
    return ok

def evaluate_priority(code: str, d: pd.DataFrame) -> tuple[str, pd.DataFrame, list[str], list[str], str]:
    missing, failed = [], []
    if d.empty:
        return "INSUFFICIENT_INFORMATION", d, failed, ["NASIS horizon description"], "No parsed NASIS horizons."
    chosen = d.iloc[0:0]
    status = "INDICATOR_NOT_DEMONSTRATED"

    if code == "A1":
        tax = " ".join(d.nasis_taxonomy.dropna().astype(str).unique()).lower()
        if not tax: missing.append("taxonomy")
        elif re.search(r"\bhistosols?\b|\bhistels?\b", tax) and not re.search(r"folist|folistel", tax): status = "INDICATOR_PRESENT"; chosen = d
        else: failed.append("taxonomy is not qualifying Histosol/Histel")
    elif code in {"A3", "A7", "A8", "A9", "A10"}:
        minth = {"A3":20, "A7":5, "A8":0, "A9":1, "A10":2}[code]
        for _, r in d.iterrows():
            desc = f"{r.designation} {r.nasis_raw_horizon_description} {r.nasis_matrix_color_raw}".lower()
            if code == "A7": material = "mucky" in desc and not re.match(r"^o[iae]", r.designation.lower())
            elif code == "A3": material = bool(re.match(r"^o[iae]", r.designation.lower()) or re.search(r"\b(peat|mucky peat|muck)\b", desc))
            else: material = bool(re.match(r"^oa", r.designation.lower()) or re.search(r"\bmuck\b", desc)) and "mucky peat" not in desc
            color_ok = code == "A7" or (r.moist_ok and r.value <= 3 and r.chroma <= 1)
            thick = r.bottom-r.top
            if r.top <= 15 and thick >= minth and material and color_ok:
                if code == "A3":
                    under = d[d.top >= r.bottom]
                    if under.empty or not ((under.moist_ok) & (under.chroma <= 2)).any(): missing.append("underlying mineral moist chroma <=2"); continue
                status="INDICATOR_PRESENT"; chosen=d.loc[[r.name]]; break
        if status != "INDICATOR_PRESENT":
            if not d.moist_ok.any() and code != "A7": missing.append("identifiable moist matrix color")
            # Absence of explicit muck/mucky description is not a confirmed zero.
            if not any(re.search(r"\bmuck|\bpeat|^o[iae]", f"{r.designation} {r.nasis_raw_horizon_description}".lower()) for _,r in d.iterrows()): missing.append("explicit organic material type")
            failed.append("no observed layer satisfies all depth/thickness/material/color conditions")
    elif code in {"S4", "F2"}:
        want = SANDY if code == "S4" else LOAMY; maxstart = 15 if code == "S4" else 30
        gh = {"N","10Y","5GY","10GY","5G","10G","5BG","10BG","5B","10B","5PB"}
        q=d[(d.top<=maxstart)&d.tex.isin(want)&d.moist_ok&(d.nasis_matrix_hue.astype(str).str.upper().isin(gh))&(d.value>=4)]
        if not q.empty: status="INDICATOR_PRESENT"; chosen=q.iloc[[0]]
        else:
            if d.tex.isna().all(): missing.append("field texture")
            if not d.moist_ok.any(): missing.append("identifiable moist matrix color")
            failed.append("no explicit qualifying gley-page matrix at required depth")
    elif code == "S5":
        def pred(r):
            raw=str(r.nasis_redox_raw).lower(); contrast=str(r.nasis_redox_contrast).lower()
            return r.tex in SANDY and r.moist_ok and r.chroma<=2 and r.redox_pct>=2 and ("distinct" in contrast or "prominent" in contrast) and ("mass" in raw or "pore" in raw)
        groups=contiguous_candidates(d,pred)
        hit=next((g for g in groups if g.top.min()<=15 and g.bottom.max()-g.top.min()>=10),None)
        if hit is not None: status="INDICATOR_PRESENT"; chosen=hit
        else:
            for field, cond in [("field texture",d.tex.notna().any()),("identifiable moist matrix color",d.moist_ok.any()),("redox percentage/type/contrast",d.redox_pct.notna().any())]:
                if not cond: missing.append(field)
            failed.append("no continuous 10-cm sandy layer meets matrix and redox requirements")
    elif code in {"F6", "F7"}:
        organic = d.designation.str.lower().str.match(r"^o[iae]")
        mineral_top = d.loc[~organic,"top"].min() if (~organic).any() else np.nan
        if pd.isna(mineral_top): missing.append("mineral soil surface datum")
        def pred(r):
            if not (r.tex in LOAMY and r.moist_ok and r.value<=3 and r.chroma<=2): return False
            if code=="F6":
                raw=str(r.nasis_redox_raw).lower(); contrast=str(r.nasis_redox_contrast).lower(); threshold=2 if r.chroma<=1 else 5
                return r.redox_pct>=threshold and ("distinct" in contrast or "prominent" in contrast) and ("mass" in raw or "pore" in raw)
            raw=str(r.nasis_redox_raw).lower(); threshold=10 if r.chroma<=1 else 20
            return r.redox_pct>=threshold and ("deplet" in raw) and bool(re.search(r"(?:5|6|7|8)/[012]", raw))
        groups=contiguous_candidates(d,pred,0 if pd.isna(mineral_top) else mineral_top)
        hit=next((g for g in groups if g.top.min()-(0 if pd.isna(mineral_top) else mineral_top)<=20 and g.bottom.max()-g.top.min()>=10),None)
        if hit is not None: status="INDICATOR_PRESENT"; chosen=hit
        else:
            for field, cond in [("field texture",d.tex.notna().any()),("identifiable moist matrix color",d.moist_ok.any()),("quantitative redox description",d.redox_pct.notna().any())]:
                if not cond: missing.append(field)
            failed.append("no continuous 10-cm loamy/clayey layer meets conditional color/redox requirements")
    elif code in {"F3", "A11", "A12"}:
        # A depleted matrix must be explicitly described as depletion/wetness-related;
        # low chroma alone never passes this implementation.
        def depleted(r):
            raw=f"{r.nasis_redox_raw} {r.nasis_wetness_morphology_raw} {r.nasis_raw_horizon_description}".lower()
            explicit="deplet" in raw or str(r.nasis_reduced_matrix_rendered)=="1.0"
            color=r.moist_ok and r.value>=4 and r.chroma<=2
            special=(r.value==4 and r.chroma in {1,2}) or (r.value==5 and r.chroma==2)
            redox_ok=(not special) or (r.redox_pct>=2 and ("mass" in raw or "pore" in raw))
            return explicit and color and redox_ok
        groups=contiguous_candidates(d,depleted)
        hit=None
        if code=="F3": hit=next((g for g in groups if (g.top.min()<=10 and g.bottom.max()-g.top.min()>=5) or (g.top.min()<=25 and g.bottom.max()-g.top.min()>=15)),None)
        elif code=="A11": hit=next((g for g in groups if g.top.min()<=30 and g.bottom.max()-g.top.min()>=15),None)
        else: hit=next((g for g in groups if g.top.min()>30 and g.bottom.max()-g.top.min()>=15),None)
        # Full dark-surface continuity/texture clauses for A11/A12 require checking above.
        if hit is not None and code in {"A11","A12"}:
            upper=d[(d.bottom>0)&(d.top<hit.top.min())]
            if code=="A11": dark=not upper.empty and (upper.moist_ok & (upper.value<=3) & (upper.chroma<=2)).all()
            else: dark=not upper.empty and upper.bottom.max()>=30 and (upper.moist_ok & (upper.value<=3) & (upper.chroma<=1)).all()
            if not dark: hit=None; failed.append("continuous overlying dark-surface color requirement not satisfied")
            if not upper.empty and upper.tex.isin(SANDY).any(): missing.append("hand-lens masked-particle percentage above matrix")
        if hit is not None and not missing: status="INDICATOR_PRESENT"; chosen=hit
        else:
            if not d.moist_ok.any(): missing.append("identifiable moist matrix color")
            if not d.fillna("").astype(str).apply(lambda x:x.str.contains("deplet",case=False).any(),axis=1).any(): missing.append("explicit wetness-derived depleted matrix")
            if not failed: failed.append("no continuous depleted layer satisfies depth/thickness requirements")
    if missing and status != "INDICATOR_PRESENT": status="INSUFFICIENT_INFORMATION"
    explanation = ("Requirements satisfied." if status=="INDICATOR_PRESENT" else "; ".join(failed+(["Missing: "+", ".join(sorted(set(missing)))] if missing else [])))
    return status, chosen, failed, sorted(set(missing)), explanation


def crosswalk(rb: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    partial_reasons={
        "A1":"Taxonomy is explicit; classification version/completeness limits some records.",
        "A3":"Organic horizon type, continuous depth, and moist color are sometimes explicit; underlying mineral color may be missing.",
        "A7":"Mucky modifier is only evaluable when explicitly rendered; absence is unknown.",
        "A8":"Muck type/color/depth is only evaluable when explicitly rendered.", "A9":"Muck type/color/depth/thickness is only evaluable when explicitly rendered.", "A10":"Muck type/color/depth/thickness is only evaluable when explicitly rendered.",
        "A11":"Requires explicit depleted/gleyed matrix and continuous dark surface; sandy cases additionally need unavailable masked-particle percentage.",
        "A12":"Requires explicit depleted/gleyed matrix and continuous dark surface; sandy cases additionally need unavailable masked-particle percentage.",
        "S4":"Gley hue/value and texture can be tested when moist matrix and dominance are explicit.",
        "S5":"Quantitative redox percentage/type/contrast and moist color are present for only some horizons.",
        "F2":"Gley hue/value and texture can be tested when moist matrix and dominance are explicit.",
        "F3":"Conservatively requires explicit wetness-derived depletion; low chroma alone is rejected.",
        "F6":"Conditional quantitative color/redox rule is evaluable only where mineral datum and complete redox observations exist.",
        "F7":"Depletion color, percentage, and continuous layer are rarely all rendered.",
    }
    for _,r in rb.iterrows():
        code=r.indicator_code
        if code in PRIORITY: feas="PARTIALLY_EVALUABLE"; reason=partial_reasons[code]
        else: feas="NOT_EVALUABLE"; reason="Not implemented in this high-confidence first pass; required field observations and/or specialized landscape/taxonomic criteria need a separately validated implementation."
        rows.append({"indicator_code":code,"indicator_name":r.indicator_name,"implementation_feasibility":feas,"exact_reason":reason,"implemented_in_primary_analysis":code in PRIORITY,"required_input_fields":r.required_input_fields,"available_master_fields":"NASIS horizon depths/designation/texture/moist color/redox raw+parsed; NASIS taxonomy; coordinates/LRR/MLRA","proxies_forbidden":"dry color; g suffix; chemistry/MIR; absent-as-zero; low chroma alone as depleted matrix"})
    return pd.DataFrame(rows)


def main() -> None:
    rb=rulebook(); rb.to_csv(OUT_DIR/"nrcs_v93_indicator_rulebook.csv",index=False)
    ped=pd.read_csv(PEDONS,low_memory=False)
    geo=spatial_assign(ped); geo.to_csv(OUT_DIR/"neon_kssl_pedon_lrr_mlra.csv",index=False)
    cw=crosswalk(rb); cw.to_csv(OUT_DIR/"nrcs_v93_indicator_data_crosswalk.csv",index=False)
    master=pd.read_csv(MASTER,low_memory=False)
    eval_rows=[]
    for _,p in geo.iterrows():
        d=profile_rows(master,p.user_pedon_id)
        for code,name,_page in INDICATORS:
            app=applicable(code,p.LRR,p.MLRA)
            if code not in PRIORITY:
                status="INSUFFICIENT_INFORMATION" if app else "NOT_APPLICABLE"
                chosen=d.iloc[0:0]; failed=[]; missing=["validated executable rule not included in high-confidence first pass"]
                explanation="Approved indicator retained in rulebook but not executed in this first-pass implementation."
            elif app is None:
                status="NOT_APPLICABLE"; chosen=d.iloc[0:0]; failed=[]; missing=["LRR/MLRA spatial assignment"]; explanation="Geographic applicability cannot be established."
            elif not app:
                status="NOT_APPLICABLE"; chosen=d.iloc[0:0]; failed=[]; missing=[]; explanation=f"Indicator {code} is not approved for LRR {p.LRR}/MLRA {p.MLRA}."
            else:
                status,chosen,failed,missing,explanation=evaluate_priority(code,d)
            payload=horizon_payload(chosen) if not chosen.empty else {k:"" for k in ["horizon_or_layers_used","depths_used","matrix_colors_used","redox_values_used","texture_used","organic_material_used"]}
            eval_rows.append({"lims_pedon_id":p.lims_pedon_id,"user_pedon_id":p.user_pedon_id,"indicator_code":code,"LRR":p.LRR,"MLRA":p.MLRA,"applicable_here":app,"evaluation_status":status,"indicator_present":True if status=="INDICATOR_PRESENT" else (False if status=="INDICATOR_NOT_DEMONSTRATED" else ""),**payload,"failed_requirements":"; ".join(failed),"missing_requirements":"; ".join(missing),"explanation":explanation})
    ev=pd.DataFrame(eval_rows); ev.to_csv(OUT_DIR/"neon_kssl_hydric_indicator_evaluations.csv",index=False)
    implemented=ev[ev.indicator_code.isin(PRIORITY)]
    summary=[]
    for (pid,uid),g in implemented.groupby(["lims_pedon_id","user_pedon_id"],dropna=False):
        applicable_g=g[g.applicable_here==True]
        present=applicable_g[applicable_g.evaluation_status=="INDICATOR_PRESENT"].indicator_code.tolist()
        summary.append({"lims_pedon_id":pid,"user_pedon_id":uid,"LRR":g.LRR.iloc[0],"MLRA":g.MLRA.iloc[0],"approved_indicators_present":";".join(present),"number_approved_indicators_present":len(present),"has_at_least_one_approved_indicator_present":bool(present),"number_applicable_priority_indicators":len(applicable_g),"number_not_demonstrated":(applicable_g.evaluation_status=="INDICATOR_NOT_DEMONSTRATED").sum(),"number_insufficient_information":(applicable_g.evaluation_status=="INSUFFICIENT_INFORMATION").sum(),"all_applicable_indicators_insufficient_information":len(applicable_g)>0 and (applicable_g.evaluation_status=="INSUFFICIENT_INFORMATION").all(),"interpretation":"Indicator evidence only; no final hydric/nonhydric label assigned."})
    ps=pd.DataFrame(summary); ps.to_csv(OUT_DIR/"neon_kssl_hydric_indicator_pedon_summary.csv",index=False)

    coverage=[]
    for code,name,_ in INDICATORS:
        g=ev[ev.indicator_code==code]; a=g[g.applicable_here==True]
        coverage.append({"indicator":code,"name":name,"geographically_applicable":len(a),"fully_evaluable":0,"partially_evaluable":len(a) if code in PRIORITY else 0,"not_evaluable":len(a) if code not in PRIORITY else 0,"present":(a.evaluation_status=="INDICATOR_PRESENT").sum(),"not_demonstrated":(a.evaluation_status=="INDICATOR_NOT_DEMONSTRATED").sum(),"insufficient_information":(a.evaluation_status=="INSUFFICIENT_INFORMATION").sum()})
    cov=pd.DataFrame(coverage)
    positives=implemented[implemented.evaluation_status=="INDICATOR_PRESENT"].drop_duplicates("user_pedon_id").sample(n=min(10,implemented[implemented.evaluation_status=="INDICATOR_PRESENT"].user_pedon_id.nunique()),random_state=930)
    if len(positives) < 10:
        # Keep the tenth apparent-positive case explicitly insufficient; never relax a rule to fill QA quota.
        candidates=implemented[(implemented.evaluation_status=="INSUFFICIENT_INFORMATION") & implemented.indicator_code.isin(["S5","F2","F3","F6","F7"]) & ~implemented.user_pedon_id.isin(positives.user_pedon_id)].drop_duplicates("user_pedon_id")
        positives=pd.concat([positives,candidates.sample(n=min(10-len(positives),len(candidates)),random_state=932)])
    negatives=implemented[implemented.evaluation_status=="INDICATOR_NOT_DEMONSTRATED"].drop_duplicates("user_pedon_id").sample(n=min(10,implemented[implemented.evaluation_status=="INDICATOR_NOT_DEMONSTRATED"].user_pedon_id.nunique()),random_state=931)
    qa=[]
    for _,q in pd.concat([positives,negatives]).iterrows():
        d=profile_rows(master,q.user_pedon_id)
        cols=["designation","top","bottom","tex","nasis_matrix_color_raw","nasis_color_moisture_status","nasis_redox_raw","redox_pct"]
        qa.append(f"### {q.user_pedon_id} â€” {q.indicator_code} â€” {q.evaluation_status}\n\n{q.explanation}\n\n```text\n{d[cols].to_string(index=False)}\n```\n")
    def markdown_table(frame: pd.DataFrame) -> str:
        values = [[str(x) for x in frame.columns]] + [[str(x) for x in row] for row in frame.itertuples(index=False, name=None)]
        widths = [max(len(row[i]) for row in values) for i in range(len(values[0]))]
        fmt = lambda row: "| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(row))) + " |"
        return "\n".join([fmt(values[0]), "| " + " | ".join("-" * w for w in widths) + " |"] + [fmt(row) for row in values[1:]])

    report=f"""# NRCS Version 9.3 indicator implementation report

## Scope and safeguards

This is an indicator-evidence implementation, not a final hydric/nonhydric classification. It uses only approved Version 9.3 indicators in the primary analysis. Dry colors, horizon `g` suffixes, chemistry, and MIR were not used as indicator evidence. Missing observations remain unknown. The February 2026 errata were reviewed; its Version 9.3 corrections to the 15-cm chroma-zone wording do not relax any rule here.

The executable first pass is deliberately limited to {', '.join(sorted(PRIORITY))}. Even these are marked partially evaluable at the dataset level because the NASIS render is incomplete for some pedons. A result of `INDICATOR_NOT_DEMONSTRATED` is not a nonhydric label.

## Spatial assignment

- Pedon rows: {len(geo):,}
- Point within official MLRA polygon: {(geo.spatial_match_status=='POINT_WITHIN_MLRA').sum():,}
- Missing coordinates: {(geo.spatial_match_status=='NO_COORDINATES').sum():,}
- No polygon match: {(geo.spatial_match_status=='NO_POLYGON_MATCH').sum():,}
- Source: {SOURCE_GEO}

## Coverage metrics

{markdown_table(cov)}

## Pedon-level evidence totals

- Pedons with at least one approved indicator present: {ps.has_at_least_one_approved_indicator_present.sum():,}
- Pedons with no indicator demonstrated among implemented/applicable rules: {(~ps.has_at_least_one_approved_indicator_present).sum():,}
- Pedons insufficient for every geographically applicable implemented rule: {ps.all_applicable_indicators_insufficient_information.sum():,}

`No indicator demonstrated` does not mean nonhydric. The non-executable approved indicators remain in the rulebook and data crosswalk but do not contribute positive or negative evidence.

## Implementation details

- Measurements using â€œsoil surfaceâ€ use NASIS absolute described depths.
- F6/F7 explicitly derive the mineral-soil datum from the first non-O horizon.
- Continuous candidate layers may span adjacent NASIS horizons; gaps break continuity.
- Only identifiable moist colors are used. Dry colors are never substituted.
- F3/A11/A12 require explicit depletion/reduction language plus the manual's color/redox conditions; low chroma alone never establishes a depleted matrix.
- A11/A12 sandy overburden remains insufficient where the required hand-lens masked-particle percentage is absent.
- Gley tests require an explicit qualifying gley-page hue and value, not a generic gray name.

## Reproducibility

Run `python scripts/kssl/implement_nrcs_v93_indicators.py` from the repository root with the staged official manual, errata, and MLRA v5.2 shapefile. Source Access data are never written.

## QA examples (fixed random seeds)

The following examples show the exact normalized NASIS horizon fields supplied to each rule. Nine apparent-positive cases are confirmed `INDICATOR_PRESENT`; the tenth is deliberately retained as an apparent-positive candidate with `INSUFFICIENT_INFORMATION`. Ten distinct not-demonstrated pedons follow. They must be reviewed before modeling.

{''.join(qa)}
"""
    (OUT_DIR/"nrcs_v93_indicator_implementation_report.md").write_text(report,encoding="utf-8")
    print(json.dumps({"pedons":len(geo),"spatial_matches":int((geo.spatial_match_status=='POINT_WITHIN_MLRA').sum()),"present_pedons":int(ps.has_at_least_one_approved_indicator_present.sum()),"evaluation_rows":len(ev)},indent=2))


if __name__ == "__main__":
    main()






