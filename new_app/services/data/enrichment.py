"""
Enrichment — Application-side joins for raw detection DataFrames.

Single Responsibility: enrich raw DataFrames with metadata from
MetadataCache (no DB queries, no I/O — pure transformation).

This module can be reused for both detection and downtime enrichment
(Etapa 4), since both need area_name, product_name, etc.

Added columns:
  - area_name, area_type        (from area cache)
  - product_name, product_code,
    product_weight, product_color (from product cache)
  - line_name, line_code         (from production_line cache, if line_id present)
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, Tuple

import pandas as pd

from new_app.core.cache import metadata_cache

logger = logging.getLogger(__name__)

# Type alias: (column_name, mapper_function) pairs
ColumnMapper = Tuple[str, Callable]


def enrich_detections(df: pd.DataFrame) -> pd.DataFrame:
    """
    Enrich a raw detection DataFrame with metadata from cache.

    Uses vectorized ``Series.map()`` for performance on large DataFrames.

    Args:
        df: Raw DataFrame with at least ``area_id`` and ``product_id``.

    Returns:
        Same DataFrame with metadata columns appended (mutated in place).
        Returns unmodified if empty.
    """
    if df.empty:
        return df

    _apply_area_columns(df)
    _apply_product_columns(df)
    _apply_line_columns(df)
    _ensure_datetime(df)

    return df


# ── Private enrichment steps ─────────────────────────────────────

def _apply_area_columns(df: pd.DataFrame) -> None:
    """Add area_name and area_type from cached areas."""
    if "area_id" not in df.columns:
        return

    areas = metadata_cache.get_areas()
    df["area_name"] = df["area_id"].map(
        lambda x: areas.get(x, {}).get("area_name", "Desconocida")
    )
    df["area_type"] = df["area_id"].map(
        lambda x: areas.get(x, {}).get("area_type", "unknown")
    )


def _apply_product_columns(df: pd.DataFrame) -> None:
    """Add product_name, product_code, product_weight, product_color."""
    if "product_id" not in df.columns:
        return

    products = metadata_cache.get_products()
    df["product_name"] = df["product_id"].map(
        lambda x: products.get(x, {}).get("product_name", "Desconocido")
    )
    df["product_code"] = df["product_id"].map(
        lambda x: products.get(x, {}).get("product_code", "")
    )
    df["product_weight"] = df["product_id"].map(
        lambda x: float(products.get(x, {}).get("product_weight", 0))
    )
    df["product_color"] = df["product_id"].map(
        lambda x: products.get(x, {}).get("product_color", "#888888")
    )


def _apply_line_columns(df: pd.DataFrame) -> None:
    """Add line_name and line_code if a line_id column exists."""
    if "line_id" not in df.columns:
        return

    lines = metadata_cache.get_production_lines()
    df["line_name"] = df["line_id"].map(
        lambda x: lines.get(x, {}).get("line_name", "Desconocida")
    )
    df["line_code"] = df["line_id"].map(
        lambda x: lines.get(x, {}).get("line_code", "")
    )


def _ensure_datetime(df: pd.DataFrame) -> None:
    """Ensure detected_at is a proper datetime column."""
    if "detected_at" in df.columns:
        df["detected_at"] = pd.to_datetime(df["detected_at"])
