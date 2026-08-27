from pathlib import Path
import json
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'data/processed/kssl_layer_analysis_table.csv'
OUT=ROOT/'outputs/tables/kssl_hydric_evidence'; GIS=ROOT/'outputs/gis'; FIG=ROOT/'outputs/figures/kssl_hydric_evidence'
for p in (OUT,GIS,FIG): p.mkdir(parents=True,exist_ok=True)

df=pd.read_csv(SRC,low_memory=False)
for c in ['taxonomic_order','taxonomic_suborder','taxonomic_great_group','taxonomic_subgroup','horizon_designation','horz_desgn_master','project_focus','project_source','lab_proj_name']:
    df[c]=df[c].fillna('').astype(str).str.strip()

# Official NTCHS criterion 1: Histosols except Folists; Histels except Folistels.
order=df.taxonomic_order.str.lower(); suborder=df.taxonomic_suborder.str.lower()
criterion1=(order.eq('histosols') & ~suborder.str.contains('folist',na=False)) | (suborder.str.contains('histel',na=False) & ~suborder.str.contains('folistel',na=False))

# Criterion-2 taxonomy is candidate/supporting evidence only; official criteria additionally require field indicators/evidence.
taxtext=(df.taxonomic_suborder+' '+df.taxonomic_great_group+' '+df.taxonomic_subgroup).str.lower()
aquic_candidate=(
    taxtext.str.contains(r'\baqu|aquic|aquent|aquept|aquoll|aqualf|aquult|aquod|aquert|aquand',regex=True,na=False)
    | suborder.eq('albolls')
    | df.taxonomic_great_group.str.lower().isin(['historthels','histoturbels'])
)
conditional_subgroup=df.taxonomic_subgroup.str.lower().str.contains(r'andic|cumulic|pachic|vitrandic',regex=True,na=False)

projtext=(df.project_focus+' '+df.project_source+' '+df.lab_proj_name).str.lower()
project_wet=projtext.str.contains(r'hydric|wetland|marsh|swamp|bog|fen|peat|floodplain|flood plain|riparian|tidal|mangrove',regex=True,na=False)
project_dry=projtext.str.contains(r'xeric|arid|desert|upland',regex=True,na=False)

# Horizon names are context only. Organic surface and gley/redox cannot be verified reliably from designation alone.
h=df.horizon_designation.str.lower()
organic_horizon=h.str.match(r'^[looh]')
gley_designation=h.str.contains('g',na=False)

df['hydric_ntchs_criterion1_taxonomy']=criterion1
df['hydric_aquic_taxonomy_candidate']=aquic_candidate
df['hydric_conditional_subgroup_candidate']=conditional_subgroup
df['hydric_project_context_candidate']=project_wet
df['dry_project_context_candidate']=project_dry
df['organic_horizon_context']=organic_horizon
df['gley_suffix_context']=gley_designation

signals=pd.DataFrame({
    'criterion1':criterion1,
    'aquic':aquic_candidate,
    'conditional':conditional_subgroup,
    'project_wet':project_wet,
    'organic':organic_horizon,
    'gley':gley_designation,
})
df['hydric_supporting_signal_count']=signals.sum(axis=1)
df['hydric_evidence_tier']=np.select(
    [criterion1, aquic_candidate & project_wet, aquic_candidate | project_wet | conditional_subgroup],
    ['strong_taxonomic_candidate','multiple_supporting_candidates','single_supporting_candidate'],
    default='indeterminate'
)
df['hydric_evidence_basis']=np.select(
    [criterion1, aquic_candidate & project_wet, aquic_candidate, project_wet, conditional_subgroup],
    ['NTCHS criterion 1 taxonomy','Aquic taxonomy + wet-context project','Aquic taxonomy candidate','Wet-context project candidate','Conditional NTCHS subgroup candidate'],
    default='No affirmative hydric evidence in snapshot'
)
df['hydric_interpretation_warning']='Candidate evidence only; field indicators or HSTS observations are required for confirmation.'

# Surface cohort: uppermost sampled layer per pedon, retaining airborne-relevant tops (<=10 cm).
ranked=df.sort_values(['lims_pedon_id','top_depth_cm','bottom_depth_cm','lay_id'],na_position='last').copy()
ranked['layer_rank_within_pedon']=ranked.groupby('lims_pedon_id').cumcount()+1
surface=ranked[(ranked.layer_rank_within_pedon.eq(1)) & pd.to_numeric(ranked.top_depth_cm,errors='coerce').le(10)].copy()
surface['arcgis_display_label']=surface.pedon_key.fillna(surface.user_pedon_id)

evidence_cols=['lay_id','smp_id','lims_site_id','lims_pedon_id','pedon_key','user_pedon_id','lab_proj_name','project_focus','project_source','state','county','latitude','longitude','top_depth_cm','bottom_depth_cm','horizon_designation','horz_desgn_master','taxon_name','taxonomic_order','taxonomic_suborder','taxonomic_great_group','taxonomic_subgroup','hydric_ntchs_criterion1_taxonomy','hydric_aquic_taxonomy_candidate','hydric_conditional_subgroup_candidate','hydric_project_context_candidate','organic_horizon_context','gley_suffix_context','hydric_supporting_signal_count','hydric_evidence_tier','hydric_evidence_basis','hydric_interpretation_warning']
df[evidence_cols].to_csv(OUT/'kssl_layer_hydric_evidence.csv',index=False)
surface.to_csv(OUT/'kssl_surface_layer_cohort.csv',index=False)

# ArcGIS-ready point CSV and GeoJSON. WGS84 is assumed only for standardized decimal coordinates; datum is retained.
giscols=['lay_id','smp_id','pedon_key','user_pedon_id','lab_proj_name','project_focus','state','county','latitude','longitude','horizontal_datum_name','coordinate_source','top_depth_cm','bottom_depth_cm','horizon_designation','taxonomic_order','taxonomic_suborder','taxonomic_subgroup','hydric_evidence_tier','hydric_evidence_basis','hydric_supporting_signal_count','total_carbon_pct','estimated_organic_carbon_pct','fe_dithionite_pct','fe_oxalate_pct','clay_pct','ph_water','water_retention_15bar_pct','cec_nh4oac_cmol_kg']
points=surface[surface.latitude.between(-90,90)&surface.longitude.between(-180,180)][giscols].copy()
points.to_csv(GIS/'kssl_surface_hydric_evidence_points.csv',index=False)
features=[]
for rec in points.to_dict('records'):
    lon=float(rec.pop('longitude')); lat=float(rec.pop('latitude'))
    props={k:(None if pd.isna(v) else v.item() if hasattr(v,'item') else v) for k,v in rec.items()}
    features.append({'type':'Feature','geometry':{'type':'Point','coordinates':[lon,lat]},'properties':props})
(GIS/'kssl_surface_hydric_evidence_points.geojson').write_text(json.dumps({'type':'FeatureCollection','name':'kssl_surface_hydric_evidence_points','crs':{'type':'name','properties':{'name':'urn:ogc:def:crs:OGC:1.3:CRS84'}},'features':features}),encoding='utf-8')

# Audits
summary=df.groupby('hydric_evidence_tier').agg(layer_count=('lay_id','size'),pedon_count=('lims_pedon_id','nunique'),with_coordinates=('latitude','count')).reset_index()
summary['layer_pct']=100*summary.layer_count/len(df); summary.to_csv(OUT/'hydric_evidence_tier_summary.csv',index=False)
surface_summary=surface.groupby('hydric_evidence_tier').agg(layer_count=('lay_id','size'),pedon_count=('lims_pedon_id','nunique'),with_coordinates=('latitude','count')).reset_index(); surface_summary.to_csv(OUT/'surface_hydric_evidence_tier_summary.csv',index=False)
taxaudit=df.groupby(['taxonomic_order','taxonomic_suborder','taxonomic_great_group','taxonomic_subgroup'],dropna=False).agg(layer_count=('lay_id','size'),pedon_count=('lims_pedon_id','nunique')).reset_index().sort_values('layer_count',ascending=False); taxaudit.to_csv(OUT/'taxonomy_hydric_audit.csv',index=False)
projects=df.groupby(['lab_proj_name','project_focus','project_source'],dropna=False).agg(layer_count=('lay_id','size'),pedon_count=('lims_pedon_id','nunique'),wet_keyword=('hydric_project_context_candidate','max')).reset_index().sort_values(['wet_keyword','layer_count'],ascending=[False,False]); projects.to_csv(OUT/'project_hydric_keyword_audit.csv',index=False)

# Simple geographic and evidence figures (context, not proof).
colors={'strong_taxonomic_candidate':'#8B1E3F','multiple_supporting_candidates':'#D9822B','single_supporting_candidate':'#3B82A0','indeterminate':'#B8C0C5'}
fig,ax=plt.subplots(figsize=(11,6))
for tier in ['indeterminate','single_supporting_candidate','multiple_supporting_candidates','strong_taxonomic_candidate']:
    q=points.hydric_evidence_tier.eq(tier); ax.scatter(points.loc[q,'longitude'],points.loc[q,'latitude'],s=5 if tier=='indeterminate' else 12,alpha=.18 if tier=='indeterminate' else .55,label=tier.replace('_',' '),color=colors[tier])
ax.set(xlabel='Longitude (decimal degrees)',ylabel='Latitude (decimal degrees)',title='KSSL surface-layer cohort and hydric-evidence tiers'); ax.legend(frameon=False,markerscale=2); ax.grid(alpha=.15); fig.tight_layout(); fig.savefig(FIG/'kssl_surface_hydric_evidence_map.png',dpi=220); plt.close(fig)

fig,ax=plt.subplots(figsize=(8,4.5)); s=surface_summary.set_index('hydric_evidence_tier').reindex(['strong_taxonomic_candidate','multiple_supporting_candidates','single_supporting_candidate','indeterminate']).fillna(0); ax.barh([x.replace('_',' ') for x in s.index],s.layer_count,color=[colors[x] for x in s.index]); ax.set_xlabel('Surface-cohort layers'); ax.set_title('Hydric evidence available in the current KSSL snapshot'); ax.spines[['top','right','left']].set_visible(False); ax.grid(axis='x',alpha=.2); fig.tight_layout(); fig.savefig(FIG/'surface_hydric_evidence_counts.png',dpi=220); plt.close(fig)

print(summary.to_string(index=False)); print(f'Surface cohort: {len(surface):,}; mapped points: {len(points):,}')
