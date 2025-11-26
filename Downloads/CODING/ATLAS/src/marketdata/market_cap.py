"""
Market data helpers for retrieving market capitalization with local caching.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from urllib.request import urlopen

import yfinance as yf

try:
    from src.storage.cache import MARKET_CACHE_DIR  # type: ignore
except Exception:
    MARKET_CACHE_DIR = os.path.join("data", "market")

__all__ = ["get_market_cap"]

os.makedirs(MARKET_CACHE_DIR, exist_ok=True)


def _cache_path(ticker: str) -> str:
    return os.path.join(MARKET_CACHE_DIR, f"{ticker.lower()}_marketcap.json")


def _load_cache(ticker: str) -> dict | None:
    path = _cache_path(ticker)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_cache(ticker: str, data: dict):
    payload = dict(data)
    payload["timestamp"] = datetime.utcnow().isoformat()
    path = _cache_path(ticker)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _is_fresh(cache: dict) -> bool:
    ts = cache.get("timestamp")
    if not ts:
        return False
    try:
        cached_at = datetime.fromisoformat(ts.replace("Z", ""))
    except Exception:
        return False
    return datetime.utcnow() - cached_at < timedelta(days=7)


def get_market_cap(ticker: str) -> float | None:
    ticker = ticker.lower()

    cache = _load_cache(ticker)
    if cache and _is_fresh(cache):
        cached_cap = cache.get("market_cap")
        if isinstance(cached_cap, (int, float)):
            return float(cached_cap)

    try:
        cap = yf.Ticker(ticker).info.get("marketCap")
    except Exception:
        cap = None

    if isinstance(cap, (int, float)):
        _save_cache(ticker, {"market_cap": float(cap)})
        return float(cap)

    api_key = os.getenv("FINNHUB_API_KEY")
    if api_key:
        url = f"https://finnhub.io/api/v1/stock/profile2?symbol={ticker}&token={api_key}"
        try:
            with urlopen(url) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                mc = data.get("marketCapitalization")
                if isinstance(mc, (int, float)):
                    cap = float(mc) * 1e6
                    _save_cache(ticker, {"market_cap": cap})
                    return cap
        except Exception:
            pass

    return None
