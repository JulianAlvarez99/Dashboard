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
from typing import Any, Dict

import pandas as pd

from new_app.core.cache import metadata_cache

logger = logging.getLogger(__name__)


# ── Public API ───────────────────────────────────────────────────

def enrich_detections(df: pd.DataFrame) -> pd.DataFrame:
    """
    Enrich a raw detection DataFrame with metadata from cache.

    Uses vectorized ``Series.map(dict)`` — a flat lookup dict is
    built once per column set, then Pandas applies it at C speed
    (no per-row Python lambda overhead).

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


# ── Vectorized helper ────────────────────────────────────────────

def _map_column(
    df: pd.DataFrame,
    src_col: str,
    cache: Dict[Any, Dict[str, Any]],
    field: str,
    default: Any,
) -> "pd.Series":
    """
    Vectorized column derivation using a pre-built flat lookup dict.

    Builds ``{id: value}`` once, then delegates to ``Series.map()``
    which runs at C speed — avoids a Python function call per row.
    """
    lookup: Dict[Any, Any] = {k: v[field] for k, v in cache.items() if field in v}
    result = df[src_col].map(lookup)
    # fillna handles IDs not present in cache
    if isinstance(default, (int, float)):
        return result.fillna(default)
    return result.fillna(default).astype(object)


# ── Private enrichment steps ─────────────────────────────────────

def _apply_area_columns(df: pd.DataFrame) -> None:
    """Add area_name and area_type from cached areas."""
    if "area_id" not in df.columns:
        return

    areas = metadata_cache.get_areas()
    df["area_name"] = _map_column(df, "area_id", areas, "area_name", "Desconocida")
    df["area_type"] = _map_column(df, "area_id", areas, "area_type", "unknown")


def _apply_product_columns(df: pd.DataFrame) -> None:
    """Add product_name, product_code, product_weight, product_color."""
    if "product_id" not in df.columns:
        return

    products = metadata_cache.get_products()
    df["product_name"]   = _map_column(df, "product_id", products, "product_name",   "Desconocido")
    df["product_code"]   = _map_column(df, "product_id", products, "product_code",   "")
    df["product_color"]  = _map_column(df, "product_id", products, "product_color",  "#888888")
    # product_weight needs numeric default — ensure float Series
    weight_lookup = {
        k: float(v.get("product_weight", 0))
        for k, v in products.items()
        if "product_weight" in v
    }
    df["product_weight"] = df["product_id"].map(weight_lookup).fillna(0.0)


def _apply_line_columns(df: pd.DataFrame) -> None:
    """Add line_name and line_code if a line_id column exists."""
    if "line_id" not in df.columns:
        return

    lines = metadata_cache.get_production_lines()
    df["line_name"] = _map_column(df, "line_id", lines, "line_name", "Desconocida")
    df["line_code"]  = _map_column(df, "line_id", lines, "line_code",  "")


def _ensure_datetime(df: pd.DataFrame) -> None:
    """Ensure detected_at is a proper datetime column."""
    if "detected_at" in df.columns:
        df["detected_at"] = pd.to_datetime(df["detected_at"])
