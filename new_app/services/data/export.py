"""
Export — DataFrame serialization to CSV and Excel.

Single Responsibility: convert enriched DataFrames to downloadable
byte formats.  No business logic, no DB access.
"""

from __future__ import annotations

import io

import pandas as pd


def to_csv(df: pd.DataFrame) -> str:
    """Export a DataFrame to a CSV string."""
    if df.empty:
        return ""
    return df.to_csv(index=False)


def to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Detecciones") -> bytes:
    """Export a DataFrame to Excel bytes (xlsx)."""
    if df.empty:
        return b""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return buffer.getvalue()


def format_datetime_columns(df: pd.DataFrame, fmt: str = "%Y-%m-%dT%H:%M:%S") -> pd.DataFrame:
    """
    Convert all datetime64 columns to formatted strings for JSON serialization.

    Returns the modified DataFrame (mutated in place).
    """
    for col in df.select_dtypes(include=["datetime64"]).columns:
        df[col] = df[col].dt.strftime(fmt)
    return df
