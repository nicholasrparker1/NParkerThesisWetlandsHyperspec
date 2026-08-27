from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'data/processed/kssl_layer_analysis_table.csv'
OUT=ROOT/'outputs/tables/kssl_analysis'; FIG=ROOT/'outputs/figures/kssl_analysis'
OUT.mkdir(parents=True,exist_ok=True); FIG.mkdir(parents=True,exist_ok=True)

VARS=['total_carbon_pct','estimated_organic_carbon_pct','total_nitrogen_pct','fe_dithionite_pct','fe_oxalate_pct','clay_pct','sand_pct','silt_pct','ph_water','ph_cacl2','bulk_density_ovendry_g_cm3','water_retention_15bar_pct','water_retention_third_bar_pct','cec_nh4oac_cmol_kg','carbonate_pct']
LABEL={'total_carbon_pct':'Total C','estimated_organic_carbon_pct':'Est. organic C','total_nitrogen_pct':'Total N','fe_dithionite_pct':'Dithionite Fe','fe_oxalate_pct':'Oxalate Fe','clay_pct':'Clay','sand_pct':'Sand','silt_pct':'Silt','ph_water':'pH water','ph_cacl2':'pH CaCl₂','bulk_density_ovendry_g_cm3':'Bulk density','water_retention_15bar_pct':'15-bar water','water_retention_third_bar_pct':'1/3-bar water','cec_nh4oac_cmol_kg':'CEC','carbonate_pct':'Carbonate'}

df=pd.read_csv(DATA,low_memory=False)
clean=df[df.qc_flag_count.eq(0)].copy()

desc=clean[VARS].describe(percentiles=[.01,.05,.25,.5,.75,.95,.99]).T
desc.insert(0,'missing_n',len(clean)-desc['count'])
desc.insert(1,'coverage_pct',100*desc['count']/len(clean))
desc.to_csv(OUT/'kssl_priority_property_descriptive_statistics.csv')

missing=pd.DataFrame({'variable':VARS,'label':[LABEL[x] for x in VARS],'n': [clean[x].notna().sum() for x in VARS]})
missing['coverage_pct']=100*missing.n/len(clean); missing.to_csv(OUT/'kssl_priority_property_missingness.csv',index=False)

corr=clean[VARS].corr(method='spearman',min_periods=500)
corr.to_csv(OUT/'kssl_priority_property_spearman_correlations.csv')
pairs=corr.where(np.triu(np.ones(corr.shape),1).astype(bool)).stack().reset_index(); pairs.columns=['variable_1','variable_2','spearman_rho']; pairs['abs_rho']=pairs.spearman_rho.abs(); pairs.sort_values('abs_rho',ascending=False).to_csv(OUT/'kssl_priority_property_top_correlations.csv',index=False)

depth=clean.groupby('depth_class',observed=True)[VARS].agg(['count','median','mean','std'])
depth.to_csv(OUT/'kssl_property_summary_by_depth_class.csv')
horizon=clean.groupby('horz_desgn_master',dropna=False)[VARS].agg(['count','median']).sort_values((VARS[0],'count'),ascending=False)
horizon.to_csv(OUT/'kssl_property_summary_by_master_horizon.csv')

# Complete-case PCA: exploratory only; capped variables by 1st/99th percentiles.
pvars=['total_carbon_pct','total_nitrogen_pct','fe_dithionite_pct','fe_oxalate_pct','clay_pct','ph_water','water_retention_15bar_pct','cec_nh4oac_cmol_kg']
pdat=clean[['lay_id','pedon_key','depth_class']+pvars].dropna().copy()
for v in pvars: pdat[v]=pdat[v].clip(pdat[v].quantile(.01),pdat[v].quantile(.99))
X=StandardScaler().fit_transform(pdat[pvars]); pca=PCA(n_components=5,random_state=0); scores=pca.fit_transform(X)
load=pd.DataFrame(pca.components_.T,index=pvars,columns=[f'PC{i}' for i in range(1,6)]); load.to_csv(OUT/'kssl_lab_property_pca_loadings.csv')
pd.DataFrame({'component':[f'PC{i}' for i in range(1,6)],'explained_variance_ratio':pca.explained_variance_ratio_,'cumulative_variance':np.cumsum(pca.explained_variance_ratio_)}).to_csv(OUT/'kssl_lab_property_pca_variance.csv',index=False)
pd.concat([pdat[['lay_id','pedon_key','depth_class']].reset_index(drop=True),pd.DataFrame(scores[:,:3],columns=['PC1','PC2','PC3'])],axis=1).to_csv(OUT/'kssl_lab_property_pca_scores.csv',index=False)

plt.style.use('default')
fig,ax=plt.subplots(figsize=(9,5)); m=missing.sort_values('coverage_pct'); ax.barh(m.label,m.coverage_pct,color='#0F7C80'); ax.set(xlabel='Coverage among quality-screened layers (%)',xlim=(0,100)); ax.spines[['top','right','left']].set_visible(False); ax.grid(axis='x',alpha=.2); ax.set_axisbelow(True); fig.tight_layout(); fig.savefig(FIG/'property_coverage.png',dpi=220); plt.close(fig)

fig,ax=plt.subplots(figsize=(9,8)); im=ax.imshow(corr,cmap='RdBu_r',vmin=-1,vmax=1); ax.set_xticks(range(len(VARS)),[LABEL[x] for x in VARS],rotation=55,ha='right'); ax.set_yticks(range(len(VARS)),[LABEL[x] for x in VARS]); fig.colorbar(im,ax=ax,label='Spearman ρ',shrink=.8); fig.tight_layout(); fig.savefig(FIG/'property_correlation_heatmap.png',dpi=220); plt.close(fig)

plotvars=['total_carbon_pct','fe_dithionite_pct','fe_oxalate_pct','clay_pct','ph_water','water_retention_15bar_pct']
fig,axs=plt.subplots(2,3,figsize=(12,7)); order=['0-10','10-30','30-60','60-100','>100']
for ax,v in zip(axs.flat,plotvars):
    vals=[clean.loc[clean.depth_class.eq(d),v].dropna().clip(upper=clean[v].quantile(.99)) for d in order]
    ax.boxplot(vals,showfliers=False,patch_artist=True,boxprops={'facecolor':'#B9DCDD'}); ax.set_title(LABEL[v]); ax.set_xticklabels(order,rotation=25); ax.grid(axis='y',alpha=.2)
fig.suptitle('Priority properties by layer midpoint depth class',fontsize=15,fontweight='bold'); fig.tight_layout(); fig.savefig(FIG/'property_distributions_by_depth.png',dpi=220); plt.close(fig)

fig,ax=plt.subplots(figsize=(8,6)); groups=pdat.depth_class.fillna('Unknown'); colors={'0-10':'#D9A441','10-30':'#52A7A8','30-60':'#377D91','60-100':'#31546A','>100':'#17324D','Unknown':'#999999'}
for g in groups.unique():
    q=groups.eq(g); ax.scatter(scores[q,0],scores[q,1],s=5,alpha=.15,label=g,color=colors.get(g,'gray'))
ax.set(xlabel=f'PC1 ({pca.explained_variance_ratio_[0]*100:.1f}%)',ylabel=f'PC2 ({pca.explained_variance_ratio_[1]*100:.1f}%)'); ax.legend(markerscale=3,frameon=False); ax.grid(alpha=.15); fig.tight_layout(); fig.savefig(FIG/'lab_property_pca_by_depth.png',dpi=220); plt.close(fig)

print(f'Analyzed {len(clean):,} quality-screened layers; PCA complete cases: {len(pdat):,}')
