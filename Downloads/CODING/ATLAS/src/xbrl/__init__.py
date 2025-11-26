"""
Universal XBRL extraction module for ATLAS.

Supports both inline XBRL (iXBRL) in HTML files and traditional XBRL XML instance documents.
"""

from .loader import load_xbrl_facts
from .fact_index import FactIndex, get_fact, get_numeric

__all__ = [
    "load_xbrl_facts",
    "FactIndex",
    "get_fact",
    "get_numeric",
]

