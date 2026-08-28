from pathlib import Path
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

BASE = (
    ROOT
    / "outputs"
    / "tables"
    / "kssl_neon_linkage"
)

OUTDIR = BASE / "florida_validation_candidate"
OUTDIR.mkdir(parents=True, exist_ok=True)

PEDONS = BASE / "neon_kssl_nasis_full_pedon_summary.csv"
BRIDGE = BASE / "neon_kssl_hydric_evidence_bridge.csv"
MASTER = BASE / "neon_kssl_master_pedon_horizon_table.csv"
SSURGO = BASE / "neon_kssl_ssurgo_component_matches.csv"


def find_col(df, candidates):
    """Return first matching column name, case-insensitive."""
    lookup = {c.lower(): c for c in df.columns}
    for candidate in candidates:
        if candidate.lower() in lookup:
            return lookup[candidate.lower()]
    return None


def florida_mask(df):
    """
    Identify Florida records using explicit state fields first,
    then pedon IDs containing FL.
    """
    masks = []

    state_candidates = [
        "state",
        "state_code",
        "state_abbr",
        "state_symbol",
        "state_name",
        "site_state",
    ]

    for c in state_candidates:
        col = find_col(df, [c])
        if col:
            s = df[col].astype(str).str.strip().str.upper()
            masks.append(
                s.isin(["FL", "FLORIDA"])
                | s.str.contains("FLORIDA", na=False)
            )

    pedon_col = find_col(
        df,
        ["user_pedon_id", "pedon_id"]
    )

    if pedon_col:
        s = df[pedon_col].astype(str).str.upper()
        masks.append(
            s.str.contains(r"FL", regex=True, na=False)
        )

    if not masks:
        return pd.Series(False, index=df.index)

    out = masks[0].copy()
    for m in masks[1:]:
        out = out | m

    return out


def summarize_file(name, path):

    print("\n" + "=" * 80)
    print(name)
    print("=" * 80)

    if not path.exists():
        print("MISSING:", path)
        return None

    df = pd.read_csv(path, low_memory=False)

    print("Rows:", len(df))
    print("Columns:", len(df.columns))

    fl = df[florida_mask(df)].copy()

    print("Florida rows:", len(fl))

    pedon_col = find_col(
        fl,
        ["user_pedon_id", "pedon_id"]
    )

    if pedon_col:
        print(
            "Florida unique pedons:",
            fl[pedon_col].nunique()
        )

    useful = [
        "user_pedon_id",
        "site_id",
        "site_code",
        "neon_site",
        "project_name",
        "lab_proj_name",
        "nasis_taxon_name",
        "nasis_taxonomy",
        "selected_compname",
        "selected_hydricrating",
        "selected_drainagecl",
        "match_confidence",
        "evidence_class",
        "indicator_state",
        "aquic_taxonomy",
        "latitude",
        "longitude",
    ]

    cols = [
        c for c in useful
        if c in fl.columns
    ]

    if len(fl) and cols:
        print("\nAvailable useful fields:")
        print(cols)

        print("\nFlorida preview:")
        print(
            fl[cols]
            .head(40)
            .to_string(index=False)
        )

    return fl


def main():

    print(
        "FLORIDA / NEON OSBS VALIDATION CANDIDATE AUDIT"
    )
    print(
        "NO MIR SPECTRAL VALUES ARE READ BY THIS SCRIPT."
    )

    datasets = {
        "PEDON SUMMARY": PEDONS,
        "HYDRIC EVIDENCE BRIDGE": BRIDGE,
        "MASTER HORIZON TABLE": MASTER,
        "SSURGO MATCHES": SSURGO,
    }

    results = {}

    for name, path in datasets.items():
        results[name] = summarize_file(
            name,
            path
        )

    # -----------------------------------------------------
    # Consolidated Florida pedon evidence table
    # -----------------------------------------------------

    frames = []

    for name, df in results.items():

        if df is None or df.empty:
            continue

        pedon_col = find_col(
            df,
            ["user_pedon_id", "pedon_id"]
        )

        if not pedon_col:
            continue

        temp = df.copy()

        if pedon_col != "user_pedon_id":
            temp = temp.rename(
                columns={
                    pedon_col: "user_pedon_id"
                }
            )

        temp["_source"] = name

        frames.append(temp)

    if not frames:
        print(
            "\nNo Florida records found."
        )
        return

    all_fl = pd.concat(
        frames,
        ignore_index=True,
        sort=False,
    )

    pedon_ids = sorted(
        all_fl["user_pedon_id"]
        .dropna()
        .astype(str)
        .unique()
    )

    print("\n" + "=" * 80)
    print("CONSOLIDATED FLORIDA COHORT")
    print("=" * 80)

    print("Unique Florida pedons:", len(pedon_ids))

    # -----------------------------------------------------
    # Evidence class
    # -----------------------------------------------------

    if "evidence_class" in all_fl.columns:

        e = (
            all_fl[
                [
                    "user_pedon_id",
                    "evidence_class",
                ]
            ]
            .dropna()
            .drop_duplicates()
        )

        print("\nEvidence classes:")
        print(
            e["evidence_class"]
            .value_counts(dropna=False)
            .to_string()
        )

    # -----------------------------------------------------
    # SSURGO hydric rating
    # -----------------------------------------------------

    if "selected_hydricrating" in all_fl.columns:

        s = (
            all_fl[
                [
                    "user_pedon_id",
                    "selected_hydricrating",
                ]
            ]
            .drop_duplicates(
                subset=["user_pedon_id"]
            )
        )

        print("\nSSURGO hydric rating:")
        print(
            s["selected_hydricrating"]
            .value_counts(dropna=False)
            .to_string()
        )

    # -----------------------------------------------------
    # Match confidence
    # -----------------------------------------------------

    if "match_confidence" in all_fl.columns:

        m = (
            all_fl[
                [
                    "user_pedon_id",
                    "match_confidence",
                ]
            ]
            .drop_duplicates(
                subset=["user_pedon_id"]
            )
        )

        print("\nSSURGO match confidence:")
        print(
            m["match_confidence"]
            .value_counts(dropna=False)
            .to_string()
        )

    # -----------------------------------------------------
    # Search for explicit OSBS identifiers
    # -----------------------------------------------------

    osbs_hits = []

    for col in all_fl.columns:

        if all_fl[col].dtype != "object":
            continue

        hit = (
            all_fl[col]
            .astype(str)
            .str.contains(
                "OSBS",
                case=False,
                na=False,
            )
        )

        if hit.any():
            x = all_fl.loc[
                hit,
                [
                    "user_pedon_id",
                    col,
                ],
            ].copy()

            x["matched_column"] = col

            osbs_hits.append(x)

    print("\n" + "=" * 80)
    print("EXPLICIT OSBS IDENTIFIER SEARCH")
    print("=" * 80)

    if osbs_hits:

        osbs = (
            pd.concat(
                osbs_hits,
                ignore_index=True,
            )
            .drop_duplicates()
        )

        print(
            osbs.to_string(index=False)
        )

        osbs.to_csv(
            OUTDIR
            / "florida_explicit_osbs_hits.csv",
            index=False,
        )

    else:
        print(
            "No explicit 'OSBS' text found in these "
            "bridge tables."
        )

    # -----------------------------------------------------
    # Save IDs only. No spectra.
    # -----------------------------------------------------

    pd.DataFrame(
        {"user_pedon_id": pedon_ids}
    ).to_csv(
        OUTDIR
        / "florida_candidate_pedon_ids.csv",
        index=False,
    )

    print("\nWrote:")
    print(
        OUTDIR
        / "florida_candidate_pedon_ids.csv"
    )

    print(
        "\nIMPORTANT: This audit intentionally did NOT "
        "read MIR spectra."
    )


if __name__ == "__main__":
    main()