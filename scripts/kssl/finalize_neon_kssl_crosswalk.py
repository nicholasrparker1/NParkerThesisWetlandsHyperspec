"""Add sample-date provenance and decoded Access serial dates to the crosswalk."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "tables" / "kssl_neon_linkage"


def joined(values: pd.Series) -> str:
    return " | ".join(sorted({str(v).strip() for v in values.dropna() if str(v).strip()}))


def access_date(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    return pd.to_datetime(numeric, unit="D", origin="1899-12-30", errors="coerce").dt.strftime("%Y-%m-%d")


def main() -> None:
    path = OUT / "neon_kssl_pedon_crosswalk.csv"
    crosswalk = pd.read_csv(path, low_memory=False)
    samples = pd.read_csv(OUT / "sample_date_identifiers.csv", low_memory=False)
    sample_rollup = samples.groupby("lims_pedon_id", as_index=False).agg(
        sample_count=("smp_id", "nunique"),
        sample_ids=("smp_id", joined),
        sample_submit_ids=("smp_submit_id", joined),
        sample_received_date_ids=("smp_rcvd_date_id", joined),
        sample_login_date_ids=("smp_login_date_id", joined),
        sample_types=("smp_type", joined),
        sample_conditions=("smp_condition", joined),
        sample_statuses=("smp_status", joined),
        earliest_sample_received_date_id=("smp_rcvd_date_id", "min"),
        latest_sample_received_date_id=("smp_rcvd_date_id", "max"),
        earliest_sample_login_date_id=("smp_login_date_id", "min"),
        latest_sample_login_date_id=("smp_login_date_id", "max"),
    )
    crosswalk = crosswalk.merge(sample_rollup, on="lims_pedon_id", how="left")
    date_fields = [
        "observation_date_id", "proj_submit_date_id", "proj_export_date_id",
        "proj_due_date_id", "proj_est_comp_date_id",
        "earliest_sample_received_date_id", "latest_sample_received_date_id",
        "earliest_sample_login_date_id", "latest_sample_login_date_id",
    ]
    for field in date_fields:
        crosswalk[field.removesuffix("_id") + "_iso"] = access_date(crosswalk[field])
    crosswalk.to_csv(path, index=False)

    audit_path = OUT / "neon_kssl_identifier_audit.md"
    audit = audit_path.read_text(encoding="utf-8")
    old = "`lims_pedon.observation_date_id` and the project fields `proj_submit_date_id`, `proj_export_date_id`, `proj_due_date_id`, and `proj_est_comp_date_id` are retained exactly as stored. The portable database has no date-dimension table that translates these IDs within the available schema. It also has no explicit coordinate precision/uncertainty column. Original DMS components, standardized decimal coordinates, and `horizontal_datum_name` are retained."
    new = "`lims_pedon.observation_date_id`; project date fields; and `sample.smp_rcvd_date_id` / `sample.smp_login_date_id` are retained exactly as stored. Their observed values are consistent with Microsoft Access/OLE Automation serial dates, so derived ISO dates use the documented origin `1899-12-30`; original numeric values remain for auditability. There is no explicit coordinate precision/uncertainty column. Original DMS components, standardized decimal coordinates, and `horizontal_datum_name` are retained."
    audit_path.write_text(audit.replace(old, new), encoding="utf-8")
    print(f"Added sample/date fields for {sample_rollup.lims_pedon_id.nunique():,} pedons")


if __name__ == "__main__":
    main()
