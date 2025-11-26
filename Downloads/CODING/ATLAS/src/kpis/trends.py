"""
Trend helpers for KPIs across multiple filings.
"""

from __future__ import annotations

from src.atlas.bundle import AtlasBundle


def kpi_trend(bundle: AtlasBundle, field: str) -> dict[str, float | None]:
    return bundle.trend(field)
