from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import spearmanr
from sklearn.cross_decomposition import PLSRegression
from sklearn.metrics import r2_score, mean_absolute_error, root_mean_squared_error

ROOT=Path(__file__).resolve().parents[2]
NPZ=ROOT/'data/processed/kssl_mt_nd_mir/kssl_mt_nd_mir_mean_spectra.npz'
COHORT=ROOT/'outputs/tables/kssl_spatial_results/kssl_mt_nd_spatial_analysis_table.csv'
OUT_T=ROOT/'outputs/tables/kssl_mir_geographic_validation'; OUT_F=ROOT/'outputs/figures/kssl_mir_geographic_validation'
plt.rcParams.update({'font.family':'Arial','font.size':10.5,'axes.titlesize':15,'axes.labelsize':11,
                     'axes.titleweight':'bold','figure.facecolor':'white'})
TARGETS={'total_carbon_pct':'Total carbon (%)','clay_pct':'Clay (%)','ph_water':'pH in water',
         'water_retention_15bar_pct':'15-bar water (%)','cec_nh4oac_cmol_kg':r'CEC (cmol$_c$ kg$^{-1}$)',
         'spatial_evidence_score':'Spatial evidence score'}

def prep(x,wn):
    z=(x-x.mean(1,keepdims=True))/x.std(1,keepdims=True)
    return np.gradient(z,wn,axis=1)

def main():
    OUT_T.mkdir(parents=True,exist_ok=True); OUT_F.mkdir(parents=True,exist_ok=True)
    z=np.load(NPZ); ids=z['smp_id'].astype(int); wn=z['wavenumber_cm1']; X=prep(z['absorbance'],wn)
    m=pd.read_csv(COHORT).set_index('smp_id').loc[ids].reset_index()
    m['spatial_evidence_score']=np.select([m.spatial_evidence_group.eq('Both NWI + SSURGO'),
        m.spatial_evidence_group.isin(['SSURGO only','NWI only'])],[2,1],default=0)
    rows=[]; predictions=[]
    for target,label in TARGETS.items():
        valid=m[target].notna().to_numpy()
        for train_state,test_state in [('Montana','North Dakota'),('North Dakota','Montana')]:
            train=valid & m.state.eq(train_state).to_numpy(); test=valid & m.state.eq(test_state).to_numpy()
            model=PLSRegression(n_components=min(10,train.sum()-1),scale=True,max_iter=1000)
            model.fit(X[train],m.loc[train,target]); pred=model.predict(X[test]).ravel(); obs=m.loc[test,target].to_numpy()
            rho,p=spearmanr(obs,pred)
            rows.append({'target':target,'label':label,'train_state':train_state,'test_state':test_state,
                         'train_n':train.sum(),'test_n':test.sum(),'r2':r2_score(obs,pred),
                         'rmse':root_mean_squared_error(obs,pred),'mae':mean_absolute_error(obs,pred),
                         'spearman_rho':rho,'spearman_p':p})
            q=m.loc[test,['smp_id','lay_id','state','lab_proj_name','spatial_evidence_group']].copy()
            q['target']=target; q['train_state']=train_state; q['observed']=obs; q['predicted']=pred
            predictions.append(q)
    metrics=pd.DataFrame(rows); preds=pd.concat(predictions,ignore_index=True)
    metrics.to_csv(OUT_T/'state_holdout_metrics.csv',index=False); preds.to_csv(OUT_T/'state_holdout_predictions.csv',index=False)
    fig,axes=plt.subplots(2,3,figsize=(13,8.2))
    for ax,(target,label) in zip(axes.flat,TARGETS.items()):
        q=metrics[metrics.target.eq(target)]
        x=np.arange(2); vals=q.spearman_rho.to_numpy(); bars=ax.bar(x,vals,color=['#0F7C80','#D9A441'])
        ax.set_xticks(x,['MT to ND','ND to MT']); ax.axhline(0,color='#7D898F',lw=.8); ax.set_ylim(min(-.25,vals.min()-.15),1)
        ax.bar_label(bars,fmt='%.2f',padding=3); ax.set_title(label,fontsize=11); ax.set_ylabel('Spearman rank correlation (rho)'); ax.grid(axis='y',alpha=.2)
    fig.suptitle('State holdouts reveal geographic transferability and asymmetry',fontsize=16,weight='bold')
    fig.tight_layout(rect=(0,0,1,.96)); fig.savefig(OUT_F/'mir_state_holdout_spearman.png',dpi=300); plt.close(fig)
    print(metrics[['target','train_state','test_state','train_n','test_n','r2','spearman_rho']].to_string(index=False))
if __name__=='__main__': main()
