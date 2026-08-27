from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.models.hydric_evidence import HydricEvidenceConfig, score_mapped_evidence


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create an exploratory mapped hydric-evidence score and separate confidence value."
    )
    parser.add_argument("--input", required=True, help="Input CSV evidence table")
    parser.add_argument("--out", required=True, help="Output scored CSV")
    parser.add_argument("--summary", help="Optional JSON run summary")
    parser.add_argument("--ssurgo-column", default="RASTERVALU")
    parser.add_argument("--nwi-column", default="nwi_intersect")
    parser.add_argument("--ssurgo-weight", type=float, default=0.5)
    parser.add_argument("--nwi-weight", type=float, default=0.5)
    args = parser.parse_args()

    source = Path(args.input)
    destination = Path(args.out)
    frame = pd.read_csv(source, low_memory=False)
    config = HydricEvidenceConfig(
        ssurgo_weight=args.ssurgo_weight,
        nwi_weight=args.nwi_weight,
    )
    scored = score_mapped_evidence(
        frame,
        ssurgo_column=args.ssurgo_column,
        nwi_column=args.nwi_column,
        config=config,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    scored.to_csv(destination, index=False)

    summary = {
        "input": str(source),
        "output": str(destination),
        "rows": len(scored),
        "model_version": config.version,
        "field_confirmed": False,
        "mean_evidence_score": float(scored["hydric_evidence_score"].mean()),
        "mean_evidence_confidence": float(scored["evidence_confidence"].mean()),
        "category_counts": scored["evidence_category"].value_counts(dropna=False).to_dict(),
    }
    if args.summary:
        summary_path = Path(args.summary)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
