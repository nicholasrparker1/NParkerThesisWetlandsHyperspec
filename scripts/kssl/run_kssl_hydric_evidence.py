"""Run hydric evidence with a documented latest-full-taxonomy enrichment."""
from pathlib import Path
import runpy
import pandas as pd
import pyodbc

root=Path(__file__).resolve().parents[2]
target=root/'data/processed/kssl_layer_analysis_table.csv'
db=root/'data/raw/KSSL/MIR Spectra_Access_Portable.accdb'
conn=pyodbc.connect(rf"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={db};READONLY=TRUE;")
cur=conn.cursor(); cur.execute("SELECT lims_pedon_id,taxonomic_classification_date_id,taxonomic_classification_type,taxonomic_subgroup FROM lims_ped_tax_hist")
tax=pd.DataFrame.from_records(cur.fetchall(),columns=[x[0] for x in cur.description]); conn.close()
tax['date_rank']=pd.to_numeric(tax.taxonomic_classification_date_id,errors='coerce').fillna(-1)
tax['type_rank']=tax.taxonomic_classification_type.fillna('').str.lower().map({'ssl':4,'correlated':3,'sampled as':2,'field':1}).fillna(0)
tax=tax.sort_values(['lims_pedon_id','date_rank','type_rank'],ascending=[True,False,False]).drop_duplicates('lims_pedon_id')
tax=tax[['lims_pedon_id','taxonomic_subgroup']]
original=pd.read_csv
def enriched(path,*args,**kwargs):
    frame=original(path,*args,**kwargs)
    try: same=Path(path).resolve()==target.resolve()
    except Exception: same=False
    if same and 'taxonomic_subgroup' not in frame.columns:
        frame=frame.merge(tax,on='lims_pedon_id',how='left',validate='many_to_one')
    return frame
pd.read_csv=enriched
runpy.run_path(str(Path(__file__).with_name('build_kssl_hydric_evidence.py')),run_name='__main__')
