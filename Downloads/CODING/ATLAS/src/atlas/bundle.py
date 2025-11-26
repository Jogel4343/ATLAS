"""
AtlasBundle: manage multiple filings for a ticker and aggregate KPIs.
"""

from __future__ import annotations

import os
import re
from typing import Dict, List

from src.atlas.atlas import Atlas
from src.kpis.generate_kpis import generate_kpis


class AtlasBundle:
    def __init__(self, ticker: str, periods: List[str] | None = None):
        self.ticker = ticker.lower()

        if periods is None:
            periods = self._discover_periods()

        self._periods = periods
        self.atlas_list = [Atlas(self.ticker, p) for p in periods]
        self.by_period: Dict[str, Atlas] = {
            p: atlas for p, atlas in zip(periods, self.atlas_list)
        }

    def _discover_periods(self) -> List[str]:
        base_dir = os.path.join("data", "raw")
        pattern = re.compile(rf"^{re.escape(self.ticker)}_(\d{{4}}_10k)$", re.IGNORECASE)
        periods = []
        if os.path.isdir(base_dir):
            for name in os.listdir(base_dir):
                match = pattern.match(name)
                if match:
                    periods.append(match.group(1))
        periods.sort(reverse=True)
        return periods

    def periods(self) -> List[str]:
        return list(self._periods)

    def atlas(self, period: str) -> Atlas:
        return self.by_period[period]

    def kpis(self, period: str) -> Dict:
        return generate_kpis(self.by_period[period])

    def all_kpis(self) -> Dict[str, Dict]:
        return {p: generate_kpis(self.by_period[p]) for p in self._periods}

    def trend(self, field: str) -> Dict[str, float | None]:
        trend_map: Dict[str, float | None] = {}
        for p in self._periods:
            kpi = generate_kpis(self.by_period[p])
            trend_map[p] = kpi.get(field)
        return trend_map

    def last(self, n: int):
        subset_periods = self._periods[:n]
        return AtlasBundle(self.ticker, subset_periods)

    def __getitem__(self, key):
        if isinstance(key, tuple):
            period = key[0]
            return self.by_period[period]
        if isinstance(key, str):
            if key in self.by_period:
                return self.by_period[key]
            return self.trend(key)
        raise KeyError(key)
