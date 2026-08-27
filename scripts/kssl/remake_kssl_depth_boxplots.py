from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[2]
df=pd.read_csv(ROOT/'data/processed/kssl_layer_analysis_table.csv',low_memory=False)
df=df[df.qc_flag_count.eq(0)]
out=ROOT/'outputs/figures/kssl_analysis/property_distributions_by_depth.png'
order=['0-10','10-30','30-60','60-100','>100']
plots=[
 ('total_carbon_pct','Total carbon','%'),
 ('fe_dithionite_pct','Dithionite-extractable Fe','%'),
 ('fe_oxalate_pct','Oxalate-extractable Fe','%'),
 ('clay_pct','Clay','%'),
 ('ph_water','Soil pH in water','pH units'),
 ('water_retention_15bar_pct','15-bar water retention','%'),
]
fig,axs=plt.subplots(2,3,figsize=(13,8))
for ax,(v,title,unit) in zip(axs.flat,plots):
    vals=[df.loc[df.depth_class.eq(d),v].dropna().clip(upper=df[v].quantile(.99)) for d in order]
    ax.boxplot(vals,showfliers=False,patch_artist=True,boxprops={'facecolor':'#B9DCDD'})
    ax.set_title(title); ax.set_xlabel('Layer midpoint depth (cm)'); ax.set_ylabel(unit)
    ax.set_xticklabels(order,rotation=25); ax.grid(axis='y',alpha=.2)
fig.suptitle('Priority properties by layer midpoint depth class',fontsize=16,fontweight='bold')
fig.tight_layout(rect=[0,0,1,.96]); fig.savefig(out,dpi=220,bbox_inches='tight'); plt.close(fig)
print(out)
