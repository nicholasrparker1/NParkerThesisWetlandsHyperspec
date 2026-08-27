"""Link NEON/KSSL pedons to official SSURGO map units and components via SDA.

This produces candidate component ratings, not final ML labels. No KSSL/NASIS
source is modified and no chemistry, MIR, or morphology is used in matching.
"""
from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "outputs" / "tables" / "kssl_neon_linkage"
PEDON_FILE = BASE / "neon_kssl_nasis_full_pedon_summary.csv"
INDICATOR_FILE = BASE / "neon_kssl_hydric_indicator_evaluations.csv"
RAW = BASE / "ssurgo_sda_raw"
SDA = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest"
SOURCE = "USDA NRCS Soil Data Access (official SSURGO), retrieved 2026-08-26"


def post_sql(sql: str, raw_path: Path, retries: int = 5) -> list[list[object]]:
    payload = {"query": sql, "format": "JSON+COLUMNNAME"}
    error = None
    for attempt in range(retries):
        try:
            response = requests.post(SDA, json=payload, timeout=120)
            response.raise_for_status()
            raw_path.write_text(response.text, encoding="utf-8")
            body = response.json()
            table = body.get("Table", [])
            return table
        except Exception as exc:
            error = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"SDA request failed after {retries} attempts: {error}")


def table_frame(table: list[list[object]]) -> pd.DataFrame:
    if not table:
        return pd.DataFrame()
    return pd.DataFrame(table[1:], columns=table[0])


def sql_quote(value: object) -> str:
    return str(value).replace("'", "''")


def pedon_coordinates() -> pd.DataFrame:
    d = pd.read_csv(PEDON_FILE, low_memory=False)
    d["latitude_out"] = pd.to_numeric(d.latitude_std_decimal_degrees, errors="coerce").fillna(pd.to_numeric(d.latitude, errors="coerce"))
    d["longitude_out"] = pd.to_numeric(d.longitude_std_decimal_degrees, errors="coerce").fillna(pd.to_numeric(d.longitude, errors="coerce"))
    west = d.longitude_direction.astype(str).str.lower().eq("west")
    d.loc[west & (d.longitude_out > 0), "longitude_out"] *= -1
    return d


def spatial_lookup(pedons: pd.DataFrame, batch_size: int = 15) -> pd.DataFrame:
    RAW.mkdir(parents=True, exist_ok=True)
    good = pedons[pedons.latitude_out.notna() & pedons.longitude_out.notna()].copy()
    frames = []
    for batch_no, start in enumerate(range(0, len(good), batch_size), 1):
        b = good.iloc[start:start + batch_size]
        selects = []
        for _, r in b.iterrows():
            uid = sql_quote(r.user_pedon_id)
            pid = sql_quote(r.lims_pedon_id)
            point = f"POINT({r.longitude_out:.8f} {r.latitude_out:.8f})"
            selects.append(
                "SELECT '" + pid + "' AS lims_pedon_id, '" + uid + "' AS user_pedon_id, "
                + f"{r.latitude_out:.8f} AS latitude, {r.longitude_out:.8f} AS longitude, "
                + "x.mukey, l.areasymbol, m.musym, m.muname "
                + "FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('" + point + "') x "
                + "JOIN mapunit m ON m.mukey=x.mukey JOIN legend l ON l.lkey=m.lkey"
            )
        table = post_sql(" UNION ALL ".join(selects), RAW / f"spatial_batch_{batch_no:03d}.json")
        f = table_frame(table)
        if not f.empty: frames.append(f)
        print(f"spatial batch {batch_no}: {len(f)} matches")
    found = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    base = pedons[["lims_pedon_id", "user_pedon_id", "latitude_out", "longitude_out"]].rename(columns={"latitude_out":"latitude", "longitude_out":"longitude"})
    if not found.empty:
        found["lims_pedon_id"] = pd.to_numeric(found.lims_pedon_id, errors="coerce")
        found["latitude"] = pd.to_numeric(found.latitude, errors="coerce")
        found["longitude"] = pd.to_numeric(found.longitude, errors="coerce")
        keys = found.groupby(["lims_pedon_id", "user_pedon_id"], dropna=False).mukey.transform("count")
        found["spatial_match_status"] = np.where(keys > 1, "AMBIGUOUS_MULTIPLE_MAPUNITS", "MATCHED")
        out = base.merge(found.drop(columns=["latitude", "longitude"]), on=["lims_pedon_id", "user_pedon_id"], how="left")
    else:
        out = base.copy()
    out["spatial_match_status"] = np.select(
        [out.latitude.isna() | out.longitude.isna(), out.get("mukey", pd.Series(index=out.index, dtype=object)).notna()],
        ["NO_COORDINATES", out.get("spatial_match_status", "MATCHED")], default="NO_SSURGO_COVERAGE")
    out["ssurgo_source"] = SOURCE
    return out


COMPONENT_FIELDS = ["mukey","cokey","compname","comppct_r","majcompflag","taxorder","taxsuborder","taxgrtgroup","taxsubgrp","taxpartsize","localphase","otherph","drainagecl","hydricrating"]


def retrieve_components(mukeys: list[str], batch_size: int = 150) -> pd.DataFrame:
    frames = []
    for batch_no, start in enumerate(range(0, len(mukeys), batch_size), 1):
        vals = ",".join("'" + sql_quote(x) + "'" for x in mukeys[start:start+batch_size])
        fields = ",".join("c." + x for x in COMPONENT_FIELDS)
        sql = f"SELECT {fields} FROM component c WHERE c.mukey IN ({vals}) ORDER BY c.mukey, c.comppct_r DESC, c.cokey"
        f = table_frame(post_sql(sql, RAW / f"components_batch_{batch_no:03d}.json"))
        if not f.empty: frames.append(f)
        print(f"component batch {batch_no}: {len(f)} components")
    comps = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COMPONENT_FIELDS)
    if comps.empty: return comps
    cokeys = comps.cokey.astype(str).drop_duplicates().tolist()
    criteria_frames=[]
    for batch_no,start in enumerate(range(0,len(cokeys),500),1):
        vals=",".join("'"+sql_quote(x)+"'" for x in cokeys[start:start+500])
        sql=f"SELECT cokey,cohydcritkey,hydriccriterion FROM cohydriccriteria WHERE cokey IN ({vals}) ORDER BY cokey,cohydcritkey"
        f=table_frame(post_sql(sql,RAW/f"hydric_criteria_batch_{batch_no:03d}.json"))
        if not f.empty: criteria_frames.append(f)
    if criteria_frames:
        crit=pd.concat(criteria_frames,ignore_index=True).groupby("cokey",as_index=False).agg(
            hydric_criteria=("hydriccriterion",lambda x:"; ".join(dict.fromkeys(x.dropna().astype(str)))),
            hydric_criteria_keys=("cohydcritkey",lambda x:"; ".join(dict.fromkeys(x.dropna().astype(str)))))
        comps=comps.merge(crit,on="cokey",how="left")
    else:
        comps["hydric_criteria"]=""; comps["hydric_criteria_keys"]=""
    return comps


def normalize_name(value: object) -> str:
    if pd.isna(value): return ""
    s=unicodedata.normalize("NFKD",str(value)).encode("ascii","ignore").decode().lower()
    s=re.sub(r"\b(?:series|taxadjunct|variant|complex|association|undifferentiated group)\b"," ",s)
    return re.sub(r"[^a-z0-9]+"," ",s).strip()


def norm_tax(value: object) -> str:
    return normalize_name(value).replace(" soils","")


def score_candidates(group: pd.DataFrame, pedon: pd.Series) -> pd.DataFrame:
    g=group.copy()
    names={normalize_name(pedon.get(x)) for x in ["current_correlated_soil_name","current_taxon_name"]}
    names.discard("")
    taxfull=norm_tax(pedon.get("taxonomy"))
    taxfields={
        "taxorder":norm_tax(pedon.get("current_taxonomic_order")),
        "taxsuborder":norm_tax(pedon.get("current_taxonomic_suborder")),
        "taxgrtgroup":norm_tax(pedon.get("current_taxonomic_great_group")),
        "taxsubgrp":norm_tax(pedon.get("current_taxonomic_subgroup")),
        "taxpartsize":norm_tax(pedon.get("current_taxonomic_family_particle_size")),
    }
    evidence=[]
    for _,r in g.iterrows():
        cn=normalize_name(r.compname)
        exact=cn in names and bool(cn)
        fuzzy=max([SequenceMatcher(None,cn,n).ratio() for n in names] or [0.0])
        agrees=[]; conflicts=[]
        for field,pval in taxfields.items():
            cval=norm_tax(r.get(field))
            if pval and cval:
                (agrees if pval==cval or pval in cval or cval in pval else conflicts).append(field)
        # Full taxonomy can recover agreement when structured NASIS fields are absent.
        if taxfull:
            for field in ["taxsubgrp","taxgrtgroup","taxsuborder","taxorder"]:
                cval=norm_tax(r.get(field))
                if cval and cval in taxfull and field not in agrees: agrees.append(field)
        score=(100 if exact else 0)+(35*fuzzy)+12*len(agrees)-8*len(conflicts)
        phase=" ".join(x for x in [str(r.get("localphase") or ""),str(r.get("otherph") or "")] if x and x!="nan")
        evidence.append((exact,fuzzy,len(agrees),len(conflicts),score,phase,agrees,conflicts))
    g[["exact_name_match","name_similarity","taxonomy_agreement_count","taxonomy_conflict_count","match_score","phase_text","taxonomy_agreements","taxonomy_conflicts"]]=pd.DataFrame(evidence,index=g.index)
    return g


def choose_component(g: pd.DataFrame) -> tuple[pd.Series | None,str,str,str]:
    q=g.sort_values(["match_score","comppct_r"],ascending=[False,False]).copy()
    top=q.iloc[0]; second=q.iloc[1] if len(q)>1 else None
    exacts=q[q.exact_name_match==True]
    if len(exacts)==1:
        selected=exacts.iloc[0]; conf="EXACT"; why="Unique exact normalized NASIS taxon/component-name match within the intersected map unit."
    elif len(exacts)>1:
        ex=exacts.sort_values(["taxonomy_agreement_count","taxonomy_conflict_count","comppct_r"],ascending=[False,True,False])
        if len(ex)>1 and ex.iloc[0].taxonomy_agreement_count==ex.iloc[1].taxonomy_agreement_count and ex.iloc[0].taxonomy_conflict_count==ex.iloc[1].taxonomy_conflict_count:
            return None,"AMBIGUOUS","Multiple components share the exact name without decisive taxonomic/phase evidence.","No alternative rejected; tied exact-name components retained."
        selected=ex.iloc[0]; conf="HIGH"; why="Multiple exact-name components; unique best taxonomic agreement selected."
    elif top.name_similarity>=0.90 and (second is None or top.match_score-second.match_score>=12):
        selected=top; conf="HIGH"; why="Unique near-exact component-name match supported by taxonomy."
    elif top.taxonomy_agreement_count>=3 and top.taxonomy_conflict_count==0 and (second is None or top.match_score-second.match_score>=18):
        selected=top; conf="MEDIUM"; why="No name match; unique candidate supported by at least three taxonomic ranks."
    elif top.taxonomy_agreement_count>=2 or top.name_similarity>=0.65:
        return None,"AMBIGUOUS","Multiple plausible candidates remain without a decisive name/taxonomy margin.","No plausible alternative rejected."
    else:
        return None,"UNMATCHED","No candidate has adequate name or taxonomic agreement.","All candidates lack sufficient correspondence to the sampled pedon."
    rejected=q[q.cokey.astype(str)!=str(selected.cokey)]
    reject="; ".join(f"{r.compname} ({r.cokey}): weaker name/taxonomy score {r.match_score:.1f}" for _,r in rejected.iterrows())
    return selected,conf,why,reject


def build_matches(spatial: pd.DataFrame, components: pd.DataFrame, pedons: pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame]:
    sp=spatial[spatial.spatial_match_status=="MATCHED"].copy()
    candidates=sp.merge(components,on="mukey",how="left")
    pedcols=["lims_pedon_id","user_pedon_id","likely_neon_site_code","lab_proj_name","submit_proj_name","current_correlated_soil_name","current_taxon_name","taxonomy","current_taxonomic_order","current_taxonomic_suborder","current_taxonomic_great_group","current_taxonomic_subgroup","current_taxonomic_family_particle_size"]
    candidates=candidates.merge(pedons[pedcols],on=["lims_pedon_id","user_pedon_id"],how="left")
    scored=[]; matches=[]
    for (pid,uid),g in candidates.groupby(["lims_pedon_id","user_pedon_id"],dropna=False):
        p=g.iloc[0]
        if g.cokey.isna().all():
            matches.append({"lims_pedon_id":pid,"user_pedon_id":uid,"match_confidence":"UNMATCHED","match_evidence":"Map unit returned no components."}); continue
        g=score_candidates(g,p); selected,confidence,why,rejected=choose_component(g)
        g["candidate_selected"]=False
        if selected is not None: g.loc[g.cokey.astype(str)==str(selected.cokey),"candidate_selected"]=True
        scored.append(g)
        row={"lims_pedon_id":pid,"user_pedon_id":uid,"latitude":p.latitude,"longitude":p.longitude,"areasymbol":p.areasymbol,"mukey":p.mukey,"musym":p.musym,"muname":p.muname,"likely_neon_site_code":p.likely_neon_site_code,"lab_proj_name":p.lab_proj_name,"submit_proj_name":p.submit_proj_name,"nasis_taxon_name":p.current_correlated_soil_name if pd.notna(p.current_correlated_soil_name) else p.current_taxon_name,"nasis_taxonomy":p.taxonomy,"candidate_component_count":len(g),"candidate_components":" | ".join(f"{r.compname} [{r.cokey}; {r.comppct_r}%; {r.hydricrating}]" for _,r in g.iterrows()),"match_confidence":confidence,"match_evidence":why,"alternatives_rejected":rejected}
        if selected is not None:
            for col in COMPONENT_FIELDS[1:]+["hydric_criteria","hydric_criteria_keys"]: row["selected_"+col]=selected.get(col)
        matches.append(row)
    # Add spatial failures/ambiguities as unmatched records without forcing components.
    seen={(x["lims_pedon_id"],x["user_pedon_id"]) for x in matches}
    for _,r in spatial.iterrows():
        if (r.lims_pedon_id,r.user_pedon_id) not in seen:
            matches.append({"lims_pedon_id":r.lims_pedon_id,"user_pedon_id":r.user_pedon_id,"latitude":r.latitude,"longitude":r.longitude,"areasymbol":r.get("areasymbol"),"mukey":r.get("mukey"),"musym":r.get("musym"),"muname":r.get("muname"),"match_confidence":"AMBIGUOUS" if str(r.spatial_match_status).startswith("AMBIGUOUS") else "UNMATCHED","match_evidence":f"Spatial status: {r.spatial_match_status}"})
    return (pd.concat(scored,ignore_index=True) if scored else pd.DataFrame()),pd.DataFrame(matches)


def normalize_rating(x: object) -> str:
    if pd.isna(x) or not str(x).strip(): return "missing"
    return str(x).strip().lower()


def make_report(spatial: pd.DataFrame,candidates: pd.DataFrame,matches: pd.DataFrame,validation: pd.DataFrame,pedons: pd.DataFrame) -> tuple[pd.DataFrame,str]:
    matches["rating_group"]=matches.get("selected_hydricrating",pd.Series(index=matches.index,dtype=object)).map(normalize_rating)
    summary=matches.groupby(["match_confidence","rating_group"],dropna=False).size().unstack(fill_value=0).reset_index()
    for col in ["yes","no","unranked","missing"]:
        if col not in summary: summary[col]=0
    summary=summary[["match_confidence","yes","no","unranked","missing"]]
    high=matches[matches.match_confidence.isin(["EXACT","HIGH"])]
    site=high.groupby("likely_neon_site_code",dropna=True).rating_group.agg(set)
    site_hydric=sum("yes" in x for x in site); site_non=sum("no" in x for x in site); site_both=sum({"yes","no"}.issubset(x) for x in site)
    pos=validation
    qa_yes=high[high.rating_group=="yes"].head(10); qa_no=high[high.rating_group=="no"].head(10)
    qa=pd.concat([qa_yes,qa_no,matches[matches.user_pedon_id.isin(pos.user_pedon_id)] ]).drop_duplicates(["user_pedon_id"])
    audits=[]
    for _,r in qa.iterrows():
        cg=candidates[candidates.user_pedon_id==r.user_pedon_id]
        show=["compname","cokey","comppct_r","taxorder","taxsubgrp","localphase","hydricrating","match_score","candidate_selected"]
        audits.append(f"### {r.user_pedon_id} — {r.match_confidence}\n\nCoordinate: {r.latitude}, {r.longitude}  \nNASIS taxon: {r.get('nasis_taxon_name','')}  \nMap unit: {r.get('areasymbol','')} / {r.get('musym','')} / {r.get('mukey','')} — {r.get('muname','')}  \nSelected: {r.get('selected_compname','')} ({r.get('selected_cokey','')}); hydricrating={r.get('selected_hydricrating','')}  \nReason: {r.match_evidence}\n\n```text\n{cg[show].to_string(index=False) if not cg.empty else 'No component candidates'}\n```\n")
    def md(df):
        vals=[[str(x) for x in df.columns]]+[[str(x) for x in row] for row in df.itertuples(index=False,name=None)]; widths=[max(len(r[i]) for r in vals) for i in range(len(vals[0]))]; fmt=lambda r:'| '+' | '.join(r[i].ljust(widths[i]) for i in range(len(r)))+' |'; return '\n'.join([fmt(vals[0]),'| '+' | '.join('-'*x for x in widths)+' |']+[fmt(r) for r in vals[1:]])
    report=f"""# NEON–KSSL SSURGO component linkage report

## Scope

Official USDA NRCS Soil Data Access/SSURGO data only. `component.hydricrating` is preserved verbatim. No polygon-level rating, dominant-component shortcut, chemistry, MIR, spectral data, or `g` suffix was used. Ambiguous component matches remain unassigned.

## Spatial results

- Pedons: {spatial[['lims_pedon_id','user_pedon_id']].drop_duplicates().shape[0]}
- Successfully intersecting one SSURGO map unit: {(spatial.spatial_match_status=='MATCHED').sum()}
- No SSURGO coverage: {(spatial.spatial_match_status=='NO_SSURGO_COVERAGE').sum()}
- Ambiguous multiple spatial matches: {(spatial.spatial_match_status=='AMBIGUOUS_MULTIPLE_MAPUNITS').sum()}
- Missing coordinates: {(spatial.spatial_match_status=='NO_COORDINATES').sum()}

## Component-match and rating summary

{md(summary)}

High confidence means `EXACT` or `HIGH` for site metrics:

- NEON sites with at least one high-confidence hydric=yes pedon: {site_hydric}
- NEON sites with at least one high-confidence hydric=no pedon: {site_non}
- NEON sites containing both: {site_both}

## Field-indicator validation

{md(validation)}
Validation totals:

- Successfully component-matched: {validation.selected_cokey.notna().sum()} of 9
- SSURGO hydricrating=Yes: {validation.selected_hydricrating.astype(str).str.lower().eq('yes').sum()}
- SSURGO hydricrating=No: {validation.selected_hydricrating.astype(str).str.lower().eq('no').sum()}
- SSURGO hydricrating=unranked: {validation.selected_hydricrating.astype(str).str.lower().eq('unranked').sum()}
- Ambiguous or unmatched: {validation.match_confidence.isin(['AMBIGUOUS','UNMATCHED']).sum()}

### Disagreement investigation

One Florida A7 pedon (`S2016FL107005`) agrees with its exact Placid component, rated `Yes`. Four Puerto Rico A7 pedons have exact normalized NASIS-to-component name matches but the matched La Covana or Pitahaya components are rated `No`. The A7 evidence is an explicitly described mucky modified mineral surface layer at the sampled point, whereas `component.hydricrating` is the official rating of the correlated SSURGO component. Both authoritative results are retained without reconciliation or relabeling. The other four indicator-positive pedons remain ambiguous or unmatched and therefore have no inherited component rating.

## QA audits

{''.join(audits)}
"""
    return summary,report


def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument("--limit",type=int); args=ap.parse_args()
    ped=pedon_coordinates()
    if args.limit: ped=ped.head(args.limit).copy()
    spatial=spatial_lookup(ped)
    spatial.to_csv(BASE/"neon_kssl_ssurgo_spatial_crosswalk.csv",index=False)
    mukeys=spatial.loc[spatial.spatial_match_status=="MATCHED","mukey"].dropna().astype(str).drop_duplicates().tolist()
    comps=retrieve_components(mukeys)
    candidates,matches=build_matches(spatial,comps,ped)
    for col in ["selected_"+x for x in COMPONENT_FIELDS[1:]+["hydric_criteria","hydric_criteria_keys"]]:
        if col not in matches: matches[col]=np.nan
    candidates.to_csv(BASE/"neon_kssl_ssurgo_component_candidates.csv",index=False)
    matches.to_csv(BASE/"neon_kssl_ssurgo_component_matches.csv",index=False)
    ind=pd.read_csv(INDICATOR_FILE,low_memory=False)
    pos=ind[ind.evaluation_status=="INDICATOR_PRESENT"][["user_pedon_id","indicator_code"]].drop_duplicates()
    validation=pos.merge(matches,on="user_pedon_id",how="left")
    validation["agreement_disagreement"]=np.select([validation.selected_hydricrating.astype(str).str.lower().eq("yes"),validation.selected_hydricrating.astype(str).str.lower().eq("no")],["AGREEMENT","DISAGREEMENT"],default="UNRESOLVED")
    valcols=["user_pedon_id","indicator_code","areasymbol","mukey","musym","muname","selected_cokey","selected_compname","match_confidence","selected_hydricrating","agreement_disagreement"]
    validation[valcols].to_csv(BASE/"neon_kssl_ssurgo_field_indicator_validation.csv",index=False)
    summary,report=make_report(spatial,candidates,matches,validation[valcols],ped)
    summary.to_csv(BASE/"neon_kssl_ssurgo_hydric_candidate_summary.csv",index=False)
    (BASE/"neon_kssl_ssurgo_linkage_report.md").write_text(report,encoding="utf-8")
    print(json.dumps({"pedons":len(ped),"spatial_rows":len(spatial),"components":len(comps),"candidates":len(candidates),"matches":matches.match_confidence.value_counts(dropna=False).to_dict()},indent=2))


if __name__ == "__main__": main()





