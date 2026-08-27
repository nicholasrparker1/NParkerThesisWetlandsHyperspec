"""Create a small, reproducible subset for rapid WOOD temporal validation.

The complete temporal holdout remains the authoritative evaluation set. This
script only creates a balanced subset that can be labeled quickly for an early
project checkpoint without changing or overwriting the source export.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_INPUT = Path(
    "data/raw/NEON/WOOD_2023/WOOD_2023_temporal_holdout_points.csv"
)
DEFAULT_OUTPUT = Path(
    "outputs/tables/neon_wood_bare_soil/"
    "WOOD_2023_preliminary_blind_label_subset_40.csv"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a balanced, reproducible preliminary label subset."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--per-class", type=int, default=20)
    parser.add_argument("--seed", type=int, default=2023)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = pd.read_csv(args.input)
    required = {
        "system:index",
        "longitude",
        "latitude",
        "predicted_bare_soil",
        "observed_class",
        "confidence",
        "notes",
    }
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    counts = data["predicted_bare_soil"].value_counts()
    if (counts < args.per_class).any() or set(counts.index) != {0, 1}:
        raise ValueError(
            "Expected both prediction strata with at least "
            f"{args.per_class} records; observed {counts.to_dict()}"
        )

    # Sampling is deterministic and stratified. Prediction is retained for
    # later scoring, but should be hidden from the person assigning labels.
    subset = (
        data.groupby("predicted_bare_soil", group_keys=False)
        .sample(n=args.per_class, random_state=args.seed)
        .sample(frac=1, random_state=args.seed + 1)
        .reset_index(drop=True)
    )
    subset.insert(0, "review_order", range(1, len(subset) + 1))
    subset.insert(1, "validation_stage", "preliminary_40_of_150")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    subset.to_csv(args.output, index=False)
    print(f"Wrote {len(subset)} records to {args.output}")
    print(subset["predicted_bare_soil"].value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
