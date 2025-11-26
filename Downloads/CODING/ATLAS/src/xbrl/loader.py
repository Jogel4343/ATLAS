"""
Unified XBRL loader with caching support.

Loads XBRL facts from the standardized instance.xml file location.
"""

import os
from typing import Dict, Any, Optional, Tuple

from src.storage.cache import load_parsed, parsed_exists, save_parsed
from .xml_extractor import extract_xml_xbrl
from .instance_selector import find_xbrl_instance


def _infer_cache_key(filing_dir: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Infer ticker and period from filing directory name.
    
    Args:
        filing_dir: Path to filing directory (e.g., "data/raw/msft_2025_10k")
        
    Returns:
        Tuple of (ticker, period) or (None, None) if cannot infer
    """
    base = os.path.basename(os.path.normpath(filing_dir))
    if "_" in base:
        ticker, period = base.split("_", 1)
        return ticker.lower(), period.lower()
    return None, None


def load_xbrl_facts(filing_dir: str, save_json: bool = True) -> Dict[str, Any]:
    """
    Unified XBRL extraction entrypoint with caching.
    
    Loads XBRL facts from the standardized xbrl/instance.xml location.
    
    Args:
        filing_dir: Path to filing directory containing xbrl/instance.xml
        save_json: Whether to save extracted data to JSON (default: True, ignored)
        
    Returns:
        Dictionary containing:
        {
            "contexts": {...},
            "all_facts": [...],
            "num_facts": N,
            "units": {...}
        }
    """
    if not os.path.exists(filing_dir):
        raise FileNotFoundError(f"Directory not found: {filing_dir}")

    ticker, period = _infer_cache_key(filing_dir)
    
    # Check cache first
    if ticker and period and parsed_exists(ticker, period):
        print(f"✔ Using cached parsed XBRL for {ticker.upper()} {period}")
        return load_parsed(ticker, period)

    # Select the best XBRL instance using selector logic
    instance = find_xbrl_instance(filing_dir)

    if not instance:
        raise FileNotFoundError("No valid XBRL instance found via selector")

    print(f"Using selected XBRL instance: {instance}")

    data = extract_xml_xbrl(instance)

    # cache
    if ticker and period:
        save_parsed(ticker, period, data)

    return data

