"""
Local cache helpers for SEC filings and parsed XBRL extractions.
"""

from __future__ import annotations

import json
import os
from typing import Dict


BASE_RAW = os.path.join("data", "raw")
BASE_EXTRACTED = os.path.join("data", "extracted")


def _key_dir(base_dir: str, ticker: str, period: str) -> str:
    name = f"{ticker.lower()}_{period.lower()}"
    return os.path.abspath(os.path.join(base_dir, name))


def raw_exists(ticker: str, period: str) -> bool:
    """
    True when the raw filing directory exists and is non-empty.
    """
    path = raw_dir(ticker, period)
    return os.path.isdir(path) and bool(os.listdir(path))


def raw_dir(ticker: str, period: str) -> str:
    """
    Absolute path to the raw filing directory (not created).
    """
    return _key_dir(BASE_RAW, ticker, period)


def ensure_raw_dir(ticker: str, period: str) -> str:
    """
    Ensure the raw filing directory exists and return its path.
    """
    path = raw_dir(ticker, period)
    os.makedirs(path, exist_ok=True)
    return path


def parsed_path(ticker: str, period: str) -> str:
    """
    Absolute path to the cached parsed JSON (no creation).
    """
    dir_path = _key_dir(BASE_EXTRACTED, ticker, period)
    return os.path.join(dir_path, "xbrl_facts.json")


def parsed_exists(ticker: str, period: str) -> bool:
    """
    True when the parsed XBRL JSON file exists.
    """
    return os.path.isfile(parsed_path(ticker, period))


def load_parsed(ticker: str, period: str) -> Dict:
    """
    Load parsed XBRL JSON and return its contents.
    """
    path = parsed_path(ticker, period)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_parsed(ticker: str, period: str, data: Dict) -> None:
    """
    Persist parsed XBRL JSON to disk, ensuring parent directory exists.
    """
    path = parsed_path(ticker, period)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

