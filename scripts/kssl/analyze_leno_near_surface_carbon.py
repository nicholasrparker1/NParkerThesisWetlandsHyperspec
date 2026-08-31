"""Describe 0-10 cm carbon for hydric-evidence groups at LENO.

One depth-overlap-weighted value is calculated per pedon. Layers are never
extended beyond their recorded depths, and incomplete interval coverage is
retained explicitly.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
LINK = ROOT / "outputs" / "tables" / "kssl_neon_linkage"
MASTER = LINK / "neon_kssl_master_pedon_horizon_table.csv"
BRIDGE = LINK / "neon_kssl_hydric_evidence_bridge.csv"
RESULTS = ROOT / "outputs" / "results" / "leno_near_surface_carbon"
FIGURE_DATA = ROOT / "outputs" / "figure_data" / "leno_near_surface_carbon.csv"
FIGURE = ROOT / "outputs" / "figures" / "leno_near_surface_carbon.png"

ELIGIBLE = {
    "STRONG_HYDRIC_SUPPORT",
    "SSURGO_HYDRIC_SUPPORT",
    "SSURGO_NONHYDRIC_SUPPORT",
}
VALUE_COLUMNS = {
    "estimated_organic_carbon_pct": "organic_carbon",
    "total_carbon_pct": "total_carbon",
}


def weighted_value(rows: pd.DataFrame, value_column: str) -> tuple[float, float]:
    usable = rows[rows[value_column].notna() & rows["overlap_0_10_cm"].gt(0)]
    represented = usable["overlap_0_10_cm"].sum()
    if represented <= 0:
        return np.nan, 0.0
    value = np.average(usable[value_column], weights=usable["overlap_0_10_cm"])
    return float(value), float(represented)


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    FIGURE_DATA.parent.mkdir(parents=True, exist_ok=True)
    FIGURE.parent.mkdir(parents=True, exist_ok=True)

    bridge = pd.read_csv(BRIDGE, low_memory=False)
    master = pd.read_csv(MASTER, low_memory=False)
    leno_all = bridge[bridge["likely_neon_site_code"].eq("LENO")].copy()
    cohort = leno_all[leno_all["evidence_class"].isin(ELIGIBLE)].copy()

    excluded = leno_all[~leno_all.index.isin(cohort.index)][
        ["user_pedon_id", "evidence_class", "match_confidence", "selected_compname"]
    ]
    excluded.to_csv(RESULTS / "leno_excluded_pedons.csv", index=False)

    layers = master[master["user_pedon_id"].isin(cohort["user_pedon_id"])].copy()
    layers["overlap_0_10_cm"] = (
        np.minimum(pd.to_numeric(layers["bottom_depth_cm"], errors="coerce"), 10.0)
        - np.maximum(pd.to_numeric(layers["top_depth_cm"], errors="coerce"), 0.0)
    ).clip(lower=0)
    contributions = layers[layers["overlap_0_10_cm"].gt(0)].copy()

    contribution_rows = []
    pedon_rows = []
    for _, evidence in cohort.sort_values("user_pedon_id").iterrows():
        pedon_layers = contributions[
            contributions["user_pedon_id"].eq(evidence["user_pedon_id"])
        ].copy()
        calculated = {}
        for value_column, label in VALUE_COLUMNS.items():
            value, represented = weighted_value(pedon_layers, value_column)
            calculated[f"near_surface_{label}_pct"] = value
            calculated[f"{label}_represented_depth_cm"] = represented
            for _, layer in pedon_layers[pedon_layers[value_column].notna()].iterrows():
                contribution_rows.append({
                    "pedon_id": evidence["user_pedon_id"],
                    "property": label,
                    "layer_id": layer["lay_id"],
                    "layer_top_depth_cm": layer["top_depth_cm"],
                    "layer_bottom_depth_cm": layer["bottom_depth_cm"],
                    "overlap_with_0_10_cm": layer["overlap_0_10_cm"],
                    "laboratory_value_pct": layer[value_column],
                    "weight_in_pedon_mean": (
                        layer["overlap_0_10_cm"] / represented if represented else np.nan
                    ),
                })

        plot_group = (
            "Hydric-supported"
            if evidence["evidence_class"] in {"STRONG_HYDRIC_SUPPORT", "SSURGO_HYDRIC_SUPPORT"}
            else "Nonhydric-supported"
        )
        component_status = (
            "Major" if str(evidence["selected_majcompflag"]).strip().lower() == "yes" else "Minor"
        )
        oc_depth = calculated["organic_carbon_represented_depth_cm"]
        pedon_rows.append({
            "pedon_id": evidence["user_pedon_id"],
            "neon_site": "LENO",
            "hydric_evidence_category": evidence["evidence_class"],
            "simplified_plot_group": plot_group,
            "ssurgo_component": evidence["selected_compname"],
            "component_major_minor": component_status,
            "match_confidence": evidence["match_confidence"],
            "available_kssl_layers": int(
                master["user_pedon_id"].eq(evidence["user_pedon_id"]).sum()
            ),
            "near_surface_oc_pct": calculated["near_surface_organic_carbon_pct"],
            "near_surface_total_c_pct": calculated["near_surface_total_carbon_pct"],
            "represented_depth_cm": oc_depth,
            "complete_0_10cm_coverage": bool(np.isclose(oc_depth, 10.0)),
            "total_c_represented_depth_cm": calculated["total_carbon_represented_depth_cm"],
        })

    pedons = pd.DataFrame(pedon_rows)
    contribution_frame = pd.DataFrame(contribution_rows)
    contribution_frame.to_csv(RESULTS / "leno_0_10cm_layer_contributions.csv", index=False)
    pedons.to_csv(RESULTS / "leno_near_surface_carbon_by_pedon.csv", index=False)
    pedons.to_csv(FIGURE_DATA, index=False)

    summary = (
        pedons.groupby("simplified_plot_group", sort=False)
        .agg(
            n_pedons=("pedon_id", "size"),
            n_with_oc=("near_surface_oc_pct", "count"),
            oc_median_pct=("near_surface_oc_pct", "median"),
            oc_min_pct=("near_surface_oc_pct", "min"),
            oc_max_pct=("near_surface_oc_pct", "max"),
            total_c_median_pct=("near_surface_total_c_pct", "median"),
            total_c_min_pct=("near_surface_total_c_pct", "min"),
            total_c_max_pct=("near_surface_total_c_pct", "max"),
        )
        .reset_index()
    )
    summary.to_csv(RESULTS / "leno_near_surface_carbon_summary.csv", index=False)

    order = ["Hydric-supported", "Nonhydric-supported"]
    fig, ax = plt.subplots(figsize=(6.2, 4.5))
    rng = np.random.default_rng(20260831)
    tick_labels = []
    for x, group in enumerate(order):
        values = pedons.loc[
            pedons["simplified_plot_group"].eq(group), "near_surface_oc_pct"
        ].dropna()
        jitter = rng.uniform(-0.08, 0.08, len(values))
        ax.scatter(np.full(len(values), x) + jitter, values, s=42, color="#24557A", zorder=3)
        if len(values):
            median = values.median()
            ax.plot([x - 0.18, x + 0.18], [median, median], color="black", lw=2)
        tick_labels.append(f"{group}\n(n = {len(values)})")
    ax.set_xticks(range(len(order)), tick_labels)
    ax.set_ylabel("Near-surface estimated organic carbon (%)")
    ax.set_title("LENO: 0–10 cm estimated organic carbon by hydric evidence group")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="0.9", linewidth=0.8)
    fig.tight_layout()
    fig.savefig(FIGURE, dpi=200)
    plt.close(fig)

    print(summary.to_string(index=False))
    print(f"Eligible LENO pedons: {len(pedons)}")
    print(f"Excluded LENO pedons: {len(excluded)}")
    print(f"Wrote {FIGURE_DATA}")
    print(f"Wrote {FIGURE}")


if __name__ == "__main__":
    main()
