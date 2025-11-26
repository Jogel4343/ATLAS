"""
Unified extractor for SEC XBRL filings.

This module now delegates to the new src.xbrl.loader module.
Maintained for backward compatibility.
"""

from src.xbrl.loader import load_xbrl_facts


def extract_xbrl(filing_dir: str, save_json: bool = True):
    """
    Unified extraction entrypoint.
    
    Delegates to src.xbrl.loader.load_xbrl_facts().
    Maintained for backward compatibility.
    
    Args:
        filing_dir: Path to filing directory
        save_json: Whether to save JSON (ignored, handled by loader)
        
    Returns:
        Dictionary with XBRL facts and contexts
    """
    return load_xbrl_facts(filing_dir, save_json=save_json)


if __name__ == "__main__":
    test_dir = "data/raw/msft_2025_10k"
    extract_xbrl(test_dir)
