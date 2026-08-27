from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[2]
scores=pd.read_csv(ROOT/'outputs/tables/kssl_analysis/kssl_lab_property_pca_scores.csv')
variance=pd.read_csv(ROOT/'outputs/tables/kssl_analysis/kssl_lab_property_pca_variance.csv')
out=ROOT/'outputs/figures/kssl_analysis/lab_property_pca_by_depth.png'

order=['0-10','10-30','30-60','60-100','>100']
colors={'0-10':'#D9A441','10-30':'#52A7A8','30-60':'#377D91','60-100':'#31546A','>100':'#17324D'}
fig,ax=plt.subplots(figsize=(8,6))
for depth in order:
    q=scores.depth_class.eq(depth)
    ax.scatter(scores.loc[q,'PC1'],scores.loc[q,'PC2'],s=5,alpha=.16,label=depth,color=colors[depth])
ax.set_xlabel(f"PC1 ({variance.iloc[0].explained_variance_ratio*100:.1f}% of variance)")
ax.set_ylabel(f"PC2 ({variance.iloc[1].explained_variance_ratio*100:.1f}% of variance)")
ax.legend(title='Layer midpoint depth (cm)',markerscale=3,frameon=False)
ax.grid(alpha=.15); fig.tight_layout(); fig.savefig(out,dpi=220,bbox_inches='tight'); plt.close(fig)
print(out)
