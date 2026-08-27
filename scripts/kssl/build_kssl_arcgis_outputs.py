"""Build validated datum-aware KSSL ArcGIS outputs from physical CSV subsets."""
from pathlib import Path
import pandas as pd
import arcpy

ROOT=Path(__file__).resolve().parents[2]; folder=ROOT/'outputs/gis'; source=folder/'kssl_surface_hydric_evidence_points.csv'; gdb=folder/'kssl_hydric_evidence.gdb'
arcpy.env.overwriteOutput=True
data=pd.read_csv(source,low_memory=False)
defs=[('NAD83',4269),('WGS84',4326),('NAD27',4267),('old hawaiian',4135)]
target_sr=arcpy.SpatialReference(4326); projected=[]
for datum,wkid in defs:
    safe=datum.lower().replace(' ','_'); subset=data[data.horizontal_datum_name.eq(datum)]
    csv=folder/f'_kssl_{safe}_source.csv'; subset.to_csv(csv,index=False)
    raw=str(gdb/f'kssl_surface_{safe}_source'); out=str(gdb/f'kssl_surface_{safe}_wgs84')
    source_sr=arcpy.SpatialReference(wkid)
    arcpy.management.XYTableToPoint(str(csv),raw,'longitude','latitude',coordinate_system=source_sr)
    transforms=arcpy.ListTransformations(source_sr,target_sr)
    arcpy.management.Project(raw,out,target_sr,transforms[0] if transforms else None)
    assert int(arcpy.management.GetCount(out)[0])==len(subset)
    projected.append(out)
merged=str(gdb/'kssl_surface_hydric_evidence_wgs84'); arcpy.management.Merge(projected,merged)
expected=sum(data.horizontal_datum_name.isin([x[0] for x in defs])); assert int(arcpy.management.GetCount(merged)[0])==expected
unknown_data=data[data.horizontal_datum_name.isna()]; unknown_csv=folder/'_kssl_unknown_datum.csv'; unknown_data.to_csv(unknown_csv,index=False)
unknown=str(gdb/'kssl_surface_unknown_datum_unprojected'); arcpy.management.XYTableToPoint(str(unknown_csv),unknown,'longitude','latitude',coordinate_system=target_sr)
assert int(arcpy.management.GetCount(unknown)[0])==len(unknown_data)
geojson=str(folder/'kssl_surface_hydric_evidence_points_corrected.geojson')
arcpy.conversion.FeaturesToJSON(merged,geojson,geoJSON='GEOJSON',outputToWGS84='WGS84')
print('known datum',expected); print('unknown datum',len(unknown_data)); print(merged); print(geojson)
