from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "outputs" / "tables" / "kssl_neon_linkage"
ND = BASE / "north_dakota_pilot"

diag = pd.read_csv(ND / "nd_pedon_diagnostic.csv", low_memory=False)
h = pd.read_csv(ND / "nd_horizons.csv", low_memory=False)

diag["hydric_group"] = diag["selected_hydricrating"].fillna("UNRESOLVED")

rows = []

for _, p in diag.iterrows():

    g = h[h["user_pedon_id"] == p["user_pedon_id"]].copy()

    if g.empty:
        continue

    g["top_depth_cm"] = pd.to_numeric(g["top_depth_cm"], errors="coerce")
    g["bottom_depth_cm"] = pd.to_numeric(g["bottom_depth_cm"], errors="coerce")
    g["matrix_value"] = pd.to_numeric(g["matrix_value"], errors="coerce")
    g["matrix_chroma"] = pd.to_numeric(g["matrix_chroma"], errors="coerce")
    g["redox_percentage_max"] = pd.to_numeric(
        g["redox_percentage_max"], errors="coerce"
    )

    surface30 = g[g["top_depth_cm"] < 30]
    surface50 = g[g["top_depth_cm"] < 50]

    raw = (
        g["raw_horizon_description"]
        .fillna("")
        .astype(str)
        .str.lower()
        .str.cat(sep=" ")
    )

    wetraw = (
        g["wetness_morphology_raw"]
        .fillna("")
        .astype(str)
        .str.lower()
        .str.cat(sep=" ")
    )

    redoxraw = (
        g["redox_raw"]
        .fillna("")
        .astype(str)
        .str.lower()
        .str.cat(sep=" ")
    )

    moist = g[
        g["color_moisture_status"]
        .fillna("")
        .astype(str)
        .str.lower()
        .eq("moist")
    ]

    low_chroma_30 = surface30[
        (surface30["matrix_chroma"] <= 2)
        & surface30["matrix_chroma"].notna()
    ]

    low_chroma_50 = surface50[
        (surface50["matrix_chroma"] <= 2)
        & surface50["matrix_chroma"].notna()
    ]

    rows.append(
        {
            "lims_pedon_id": p.get("lims_pedon_id"),
            "user_pedon_id": p["user_pedon_id"],
            "MLRA": p.get("MLRA"),
            "nasis_taxon_name": p.get("nasis_taxon_name"),
            "nasis_taxonomy": p.get("nasis_taxonomy"),
            "match_confidence": p.get("match_confidence"),
            "selected_compname": p.get("selected_compname"),
            "selected_drainagecl": p.get("selected_drainagecl"),
            "selected_hydricrating": p.get("selected_hydricrating"),
            "approved_indicators_present": p.get(
                "approved_indicators_present"
            ),
            "n_horizons": len(g),
            "n_moist_color_horizons": len(moist),
            "n_redox_horizons": g["redox_raw"].notna().sum(),
            "n_low_chroma_horizons_0_30cm": len(low_chroma_30),
            "n_low_chroma_horizons_0_50cm": len(low_chroma_50),
            "max_redox_pct": g["redox_percentage_max"].max(),
            "mentions_depletion": "deplet" in (raw + wetraw + redoxraw),
            "mentions_gley": "gley" in (raw + wetraw + redoxraw),
            "mentions_reduced": "reduc" in (raw + wetraw + redoxraw),
            "mentions_muck": "muck" in raw,
            "mentions_peat": "peat" in raw,
            "mentions_h2s": (
                "hydrogen sulfide" in raw
                or "h2s" in raw
                or "sulfur" in raw
            ),
            "aquic_taxonomy": any(
                term in str(p.get("nasis_taxonomy", "")).lower()
                for term in [
                    "aquoll",
                    "aquult",
                    "aquept",
                    "aquent",
                    "aquod",
                    "aquic",
                    "endoaqu",
                    "epiaqu",
                ]
            ),
        }
    )

audit = pd.DataFrame(rows)

audit.to_csv(
    ND / "nd_hydric_morphology_audit.csv",
    index=False,
)

print("\nNorth Dakota morphology audit")
print("=" * 70)

print("\nBy SSURGO hydric rating:")
print(
    audit.groupby("selected_hydricrating", dropna=False)
    .agg(
        pedons=("user_pedon_id", "count"),
        aquic_taxonomy=("aquic_taxonomy", "sum"),
        any_redox=("n_redox_horizons", lambda x: (x > 0).sum()),
        any_low_chroma_30=(
            "n_low_chroma_horizons_0_30cm",
            lambda x: (x > 0).sum(),
        ),
        depletion=("mentions_depletion", "sum"),
        gley=("mentions_gley", "sum"),
        reduced=("mentions_reduced", "sum"),
        muck=("mentions_muck", "sum"),
    )
    .to_string()
)

print("\nHydric SSURGO pedons:")
cols = [
    "user_pedon_id",
    "nasis_taxon_name",
    "nasis_taxonomy",
    "selected_compname",
    "selected_drainagecl",
    "match_confidence",
    "n_redox_horizons",
    "n_low_chroma_horizons_0_30cm",
    "max_redox_pct",
    "mentions_depletion",
    "mentions_gley",
    "mentions_reduced",
    "aquic_taxonomy",
]

print(
    audit[audit["selected_hydricrating"] == "Yes"][cols]
    .to_string(index=False)
)

print(
    "\nWrote:",
    ND / "nd_hydric_morphology_audit.csv",
)