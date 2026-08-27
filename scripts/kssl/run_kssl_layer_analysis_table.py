"""Compatibility entry point for null-safe KSSL layer table construction."""

import pandas as pd

import build_kssl_layer_analysis_table as builder


original_clean_text = builder.clean_text
original_series_le = pd.Series.le


def clean_text_without_missing_boolean_values(series):
    return original_clean_text(series).fillna("")


def null_safe_series_le(self, other, *args, **kwargs):
    try:
        return original_series_le(self, other, *args, **kwargs)
    except TypeError:
        return original_series_le(
            pd.to_numeric(self, errors="coerce"),
            pd.to_numeric(other, errors="coerce"),
            *args,
            **kwargs,
        )


builder.clean_text = clean_text_without_missing_boolean_values
pd.Series.le = null_safe_series_le
builder.main()
