"""
CIK lookup with local caching.
"""

from __future__ import annotations

import json
import os
import time
from datetime import timedelta
from urllib.request import urlopen

CACHE_DIR = os.path.join("data", "sec")
CACHE_PATH = os.path.join(CACHE_DIR, "cik_map.json")
REMOTE_URL = "https://www.sec.gov/files/company_tickers.json"


def _is_fresh(path: str, max_age_days: int = 30) -> bool:
    if not os.path.isfile(path):
        return False
    age_seconds = time.time() - os.path.getmtime(path)
    return age_seconds < timedelta(days=max_age_days).total_seconds()


def _load_cache() -> dict[str, str]:
    if os.path.isfile(CACHE_PATH):
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_cache(data: dict[str, str]) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _download_mapping() -> dict[str, str]:
    import requests

    headers = {
        "User-Agent": "ATLAS/1.0 (jackvogel4343@gmail.com)",
        "Accept-Encoding": "gzip, deflate",
    }

    resp = requests.get(REMOTE_URL, headers=headers)
    resp.raise_for_status()
    raw = resp.json()

    mapping: dict[str, str] = {}
    for entry in raw.values():
        ticker = entry.get("ticker", "").lower()
        cik = entry.get("cik_str")
        if ticker and cik is not None:
            mapping[ticker] = str(cik).zfill(10)

    _save_cache(mapping)
    return mapping


def get_cik(ticker: str) -> str:
    ticker = ticker.lower()
    if not _is_fresh(CACHE_PATH):
        mapping = _download_mapping()
    else:
        mapping = _load_cache()
        if not mapping:
            mapping = _download_mapping()
    if ticker not in mapping:
        raise ValueError(f"CIK not found for ticker: {ticker}")
    return mapping[ticker]
