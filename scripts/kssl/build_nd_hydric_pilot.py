from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "outputs" / "tables" / "kssl_neon_linkage"
OUT = BASE / "north_dakota_pilot"
OUT.mkdir(parents=True, exist_ok=True)

files = {
    "bridge": "neon_kssl_hydric_evidence_bridge.csv",
    "pedons": "neon_kssl_nasis_full_pedon_summary.csv",
    "horizons": "neon_kssl_nasis_horizon_morphology.csv",
    "master": "neon_kssl_master_pedon_horizon_table.csv",
    "indicators": "neon_kssl_hydric_indicator_evaluations.csv",
    "ssurgo": "neon_kssl_ssurgo_component_matches.csv",
}

frames = {
    k: pd.read_csv(BASE / v, low_memory=False)
    for k, v in files.items()
}

# Identify North Dakota pedons using the SSURGO area symbol
# or the User Pedon ID.
ssurgo = frames["ssurgo"]

nd_ids = set(
    ssurgo.loc[
        ssurgo["areasymbol"]
        .fillna("")
        .astype(str)
        .str.startswith("ND")
        |
        ssurgo["user_pedon_id"]
        .fillna("")
        .astype(str)
        .str.contains(r"^\S*ND", regex=True),
        "user_pedon_id",
    ].dropna()
)

print(f"North Dakota pedons identified: {len(nd_ids)}")

# Create ND-only versions of each supporting table.
for name, df in frames.items():

    if "user_pedon_id" not in df.columns:
        continue

    subset = df[df["user_pedon_id"].isin(nd_ids)].copy()

    path = OUT / f"nd_{name}.csv"
    subset.to_csv(path, index=False)

    print(
        f"{name}: {len(subset)} rows, "
        f"{subset['user_pedon_id'].nunique()} unique pedons"
    )

# Build a compact pedon-level diagnostic table.
bridge = frames["bridge"]
nd = bridge[bridge["user_pedon_id"].isin(nd_ids)].copy()

cols = [
    "lims_pedon_id",
    "user_pedon_id",
    "LRR",
    "MLRA",
    "approved_indicators_present",
    "number_applicable_priority_indicators",
    "number_not_demonstrated",
    "number_insufficient_information",
    "areasymbol",
    "muname",
    "nasis_taxon_name",
    "nasis_taxonomy",
    "match_confidence",
    "selected_compname",
    "selected_drainagecl",
    "selected_hydricrating",
    "evidence_class",
]

cols = [c for c in cols if c in nd.columns]

diagnostic = (
    nd[cols]
    .sort_values("user_pedon_id")
)

diagnostic.to_csv(
    OUT / "nd_pedon_diagnostic.csv",
    index=False,
)

print("\nEvidence classes:")
print(
    nd["evidence_class"]
    .value_counts(dropna=False)
    .to_string()
)

print("\nSSURGO match confidence:")
print(
    nd["match_confidence"]
    .value_counts(dropna=False)
    .to_string()
)

print("\nSSURGO hydric rating among ND pedons:")
print(
    nd["selected_hydricrating"]
    .value_counts(dropna=False)
    .to_string()
)

print(f"\nWrote ND pilot files to: {OUT}")