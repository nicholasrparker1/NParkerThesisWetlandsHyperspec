from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class HydricEvidenceConfig:
    """Transparent provisional weights for mapped evidence only."""

    ssurgo_weight: float = 0.5
    nwi_weight: float = 0.5
    version: str = "mapped-evidence-v0.1"

    def __post_init__(self) -> None:
        if self.ssurgo_weight < 0 or self.nwi_weight < 0:
            raise ValueError("Evidence weights must be non-negative.")
        if self.ssurgo_weight + self.nwi_weight <= 0:
            raise ValueError("At least one evidence weight must be positive.")


def _numeric_component(values: pd.Series, scale: float) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    return (numeric / scale).clip(0.0, 1.0)


def _binary_component(values: pd.Series) -> pd.Series:
    normalized = values.astype(str).str.strip().str.lower()
    true_values = {"1", "true", "yes", "y"}
    false_values = {"0", "false", "no", "n"}
    out = pd.Series(np.nan, index=values.index, dtype=float)
    out.loc[normalized.isin(true_values)] = 1.0
    out.loc[normalized.isin(false_values)] = 0.0
    return out


def score_mapped_evidence(
    frame: pd.DataFrame,
    *,
    ssurgo_column: str = "RASTERVALU",
    nwi_column: str = "nwi_intersect",
    config: HydricEvidenceConfig | None = None,
) -> pd.DataFrame:
    """Score weak mapped evidence while keeping data support separate.

    SSURGO is interpreted as hydric percentage on a 0-100 scale. NWI is a
    binary intersection flag. Missing components are not treated as negative
    evidence; the score is normalized across available components and
    confidence reports the fraction of requested weight that was observed.
    """

    cfg = config or HydricEvidenceConfig()
    if ssurgo_column not in frame.columns and nwi_column not in frame.columns:
        raise ValueError(
            f"Input needs at least one evidence column: {ssurgo_column!r} or {nwi_column!r}."
        )

    out = frame.copy()
    ssurgo = (
        _numeric_component(out[ssurgo_column], 100.0)
        if ssurgo_column in out.columns
        else pd.Series(np.nan, index=out.index, dtype=float)
    )
    nwi = (
        _binary_component(out[nwi_column])
        if nwi_column in out.columns
        else pd.Series(np.nan, index=out.index, dtype=float)
    )

    numerator = ssurgo.fillna(0.0) * cfg.ssurgo_weight + nwi.fillna(0.0) * cfg.nwi_weight
    available_weight = (
        ssurgo.notna().astype(float) * cfg.ssurgo_weight
        + nwi.notna().astype(float) * cfg.nwi_weight
    )
    total_weight = cfg.ssurgo_weight + cfg.nwi_weight

    out["ssurgo_evidence_component"] = ssurgo
    out["nwi_evidence_component"] = nwi
    out["hydric_evidence_score"] = numerator.div(available_weight.replace(0.0, np.nan))
    out["evidence_confidence"] = available_weight / total_weight
    out["evidence_category"] = pd.cut(
        out["hydric_evidence_score"],
        bins=[-np.inf, 0.25, 0.5, 0.75, np.inf],
        labels=["low", "moderate", "high", "very high"],
    ).astype("string")
    out.loc[out["evidence_confidence"].eq(0), "evidence_category"] = "insufficient"
    out["evidence_model_version"] = cfg.version
    out["evidence_is_field_confirmed"] = False
    return out
