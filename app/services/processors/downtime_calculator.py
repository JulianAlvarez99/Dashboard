"""
Gap-based downtime calculator.

Detects production stops by analysing time gaps between consecutive
detections.  Gaps that exceed the configured *downtime threshold* are
flagged as downtime events.

**Merge rule** — consecutive above-threshold gaps belong to the **same**
downtime event.  A new downtime only begins after at least one
below-threshold gap (i.e. production must resume with a real detection
in between).
"""

from typing import List, Optional

import pandas as pd

from app.core.cache import metadata_cache


# ── Public API ───────────────────────────────────────────────────────

def calculate_gap_downtimes(
    detections_df: pd.DataFrame,
    line_ids: List[int],
    threshold_override: Optional[int] = None,
) -> pd.DataFrame:
    """
    Scan detection timestamps per line and emit downtime events for
    gaps that exceed the threshold.

    Args:
        detections_df: Enriched detections DataFrame (must contain
            ``detected_at`` and ``line_id`` columns).
        line_ids: Lines to process.
        threshold_override: Seconds — overrides the per-line DB value
            when the dashboard filter supplies one.

    Returns:
        DataFrame with columns:
        ``start_time, end_time, duration, reason_code, line_id, source``
    """
    if detections_df.empty:
        return pd.DataFrame()

    required = {"detected_at", "line_id"}
    if not required.issubset(detections_df.columns):
        return pd.DataFrame()

    all_events: List[dict] = []

    for line_id in line_ids:
        line_meta = metadata_cache.get_production_line(line_id)
        if not line_meta:
            continue
        # Honour the DB toggle — skip if disabled
        if not line_meta.get("auto_detect_downtime", True):
            continue

        threshold = threshold_override or line_meta.get("downtime_threshold")
        if not threshold or int(threshold) <= 0:
            continue
        threshold = int(threshold)

        line_df = detections_df[detections_df["line_id"] == line_id]
        if len(line_df) < 2:
            continue

        line_df = line_df.sort_values("detected_at")
        times = line_df["detected_at"].values  # numpy datetime64 array

        current_start: Optional[pd.Timestamp] = None
        current_end: Optional[pd.Timestamp] = None

        for i in range(len(times) - 1):
            gap_sec = (times[i + 1] - times[i]) / pd.Timedelta(seconds=1)

            if gap_sec >= threshold:
                if current_start is None:
                    current_start = pd.Timestamp(times[i])
                current_end = pd.Timestamp(times[i + 1])
            else:
                # Production resumed → close any open downtime
                if current_start is not None:
                    all_events.append(
                        _make_event(current_start, current_end, line_id)
                    )
                    current_start = None
                    current_end = None

        # Close trailing downtime
        if current_start is not None:
            all_events.append(
                _make_event(current_start, current_end, line_id)
            )

    if not all_events:
        return pd.DataFrame()

    return pd.DataFrame(all_events)


# ── De-duplication ───────────────────────────────────────────────────

def remove_overlapping(
    calculated_df: pd.DataFrame,
    db_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Drop calculated downtimes that overlap with any DB-registered
    downtime on the same line.  DB records win because they carry
    operator-confirmed incident information.
    """
    if calculated_df.empty or db_df.empty:
        return calculated_df

    keep_mask = []
    for _, calc in calculated_df.iterrows():
        line_db = db_df[db_df["line_id"] == calc["line_id"]]
        overlaps = (
            (calc["start_time"] < line_db["end_time"])
            & (calc["end_time"] > line_db["start_time"])
        ).any()
        keep_mask.append(not overlaps)

    return calculated_df[keep_mask].reset_index(drop=True)


# ── Helpers ──────────────────────────────────────────────────────────

def _make_event(
    start: pd.Timestamp, end: pd.Timestamp, line_id: int
) -> dict:
    return {
        "start_time": start,
        "end_time": end,
        "duration": (end - start).total_seconds(),
        "reason_code": None,
        "line_id": line_id,
        "source": "calculated",
    }
