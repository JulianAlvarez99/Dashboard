"""
DataFrame utilities — shared helpers for pandas DataFrames.

Centralises common DataFrame operations used across DetectionService,
DowntimeService, and WidgetEngine to avoid code duplication.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd


# ── Column helpers ────────────────────────────────────────────────

def ensure_datetime_col(
    df: pd.DataFrame,
    col: str,
    utc: bool = False,
) -> pd.DataFrame:
    """
    Convert *col* to ``datetime64`` in-place (no-op if already correct).

    Args:
        df:   DataFrame to modify.
        col:  Column name to convert.
        utc:  If ``True``, coerce to UTC-aware timestamps.

    Returns the same DataFrame (mutated) for chaining convenience.
    """
    if col not in df.columns:
        return df
    if not pd.api.types.is_datetime64_any_dtype(df[col]):
        df[col] = pd.to_datetime(df[col], errors="coerce", utc=utc)
    return df


def safe_merge(
    left: pd.DataFrame,
    right: pd.DataFrame,
    on: str | List[str],
    how: str = "left",
    suffixes: tuple = ("", "_r"),
) -> pd.DataFrame:
    """
    Merge *left* and *right* DataFrames, returning *left* unchanged if
    either is empty (avoids merge errors on empty frames).
    """
    if left.empty or right.empty:
        return left
    return left.merge(right, on=on, how=how, suffixes=suffixes)


# ── Filtering helpers ─────────────────────────────────────────────

def filter_by_daterange(
    df: pd.DataFrame,
    col: str,
    start: Optional[Any] = None,
    end: Optional[Any] = None,
) -> pd.DataFrame:
    """
    Filter *df* rows where *col* falls within [start, end] (inclusive).

    Missing bounds are silently ignored.  Returns original DataFrame if
    *col* is not present.
    """
    if col not in df.columns or df.empty:
        return df
    mask = pd.Series(True, index=df.index)
    if start is not None:
        mask &= df[col] >= start
    if end is not None:
        mask &= df[col] <= end
    return df[mask]


# ── Aggregation helpers ───────────────────────────────────────────

def resample_count(
    df: pd.DataFrame,
    datetime_col: str,
    freq: str,
    group_cols: Optional[List[str]] = None,
    count_col: str = "count",
) -> pd.DataFrame:
    """
    Resample *df* by *freq* (pandas offset alias, e.g. ``'1h'``, ``'1D'``),
    counting rows within each bucket.

    Args:
        df:           Source DataFrame.
        datetime_col: Name of the datetime column to resample on.
        freq:         Pandas offset alias.
        group_cols:   Additional columns to group by before resampling.
        count_col:    Name for the aggregated count column in the result.

    Returns a DataFrame with the resampled timestamps and *count_col*.
    """
    if df.empty or datetime_col not in df.columns:
        return pd.DataFrame(columns=[datetime_col, count_col])

    df = df.copy()
    df[datetime_col] = pd.to_datetime(df[datetime_col], errors="coerce")
    df = df.dropna(subset=[datetime_col])
    df = df.set_index(datetime_col)

    if group_cols:
        result = (
            df.groupby(group_cols)
            .resample(freq)
            .size()
            .reset_index(name=count_col)
        )
    else:
        result = df.resample(freq).size().reset_index(name=count_col)

    return result


# ── Serialization ─────────────────────────────────────────────────

def df_to_records(
    df: pd.DataFrame,
    datetime_cols: Optional[List[str]] = None,
    fmt: str = "%Y-%m-%dT%H:%M:%S",
) -> List[Dict[str, Any]]:
    """
    Convert a DataFrame to a list of dicts, optionally stringifying
    datetime columns to ISO format for JSON serialisation.

    Args:
        df:            Source DataFrame.
        datetime_cols: Columns to convert to strings using *fmt*.
        fmt:           strftime format for datetime columns.

    Returns a list of row dicts.
    """
    if df.empty:
        return []

    out = df.copy()
    for col in (datetime_cols or []):
        if col in out.columns and pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime(fmt)

    return out.where(pd.notna(out), other=None).to_dict(orient="records")
