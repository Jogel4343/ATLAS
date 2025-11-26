"""
Extract inline XBRL (iXBRL) facts from SEC HTML filings.
"""

import os
from typing import Dict, Any
from lxml import html


def _normalize_number(value: str) -> float | None:
    """Normalize numeric strings from iXBRL facts."""
    if not value or not isinstance(value, str):
        return None

    v = value.replace(",", "").replace(" ", "").strip()

    # (123) → -123
    if v.startswith("(") and v.endswith(")"):
        v = "-" + v[1:-1]

    try:
        return float(v)
    except:
        return None


def extract_inline_xbrl(html_path: str) -> Dict[str, Any]:
    """
    Extract inline XBRL (iXBRL) facts from SEC HTML filings using lxml.
    
    Args:
        html_path: Path to HTML file containing iXBRL
        
    Returns:
        Dictionary containing:
        {
            "contexts": {context_id: [facts...]},
            "all_facts": [...],
            "num_facts": N
        }
    """
    if not os.path.exists(html_path):
        print(f"Error: HTML file not found: {html_path}")
        return {"contexts": {}, "all_facts": [], "num_facts": 0}

    # Parse HTML using robust browser-style parser
    try:
        parser = html.HTMLParser(recover=True, remove_comments=False)
        tree = html.parse(html_path, parser)
        root = tree.getroot()
        print("Parsed using lxml.html HTMLParser")
    except Exception as e:
        print(f"HTML parse error: {e}")
        return {"contexts": {}, "all_facts": [], "num_facts": 0}

    # Extract xbrli:context elements for context metadata
    context_elements = root.xpath("//*[local-name()='context']")
    contexts = {}
    
    # Get namespace for xbrli
    nsmap = root.nsmap
    xbrli_ns = nsmap.get('xbrli') or 'http://www.xbrl.org/2003/instance'
    
    for context_elem in context_elements:
        context_id = context_elem.get("id", "")
        if not context_id:
            continue
        
        context_info = {
            "id": context_id,
            "entity_identifier": "",
            "entity_scheme": "",
            "period_type": "",
            "period_start": "",
            "period_end": "",
            "period_instant": ""
        }
        
        # Extract entity identifier
        entity_elem = context_elem.find(f".//{{{xbrli_ns}}}entity")
        if entity_elem is not None:
            identifier_elem = entity_elem.find(f".//{{{xbrli_ns}}}identifier")
            if identifier_elem is not None:
                context_info["entity_identifier"] = identifier_elem.text or ""
                context_info["entity_scheme"] = identifier_elem.get("scheme", "") or ""
        
        # Extract period information
        period_elem = context_elem.find(f".//{{{xbrli_ns}}}period")
        if period_elem is not None:
            # Check for instant (point in time)
            instant_elem = period_elem.find(f".//{{{xbrli_ns}}}instant")
            if instant_elem is not None:
                context_info["period_type"] = "instant"
                context_info["period_instant"] = instant_elem.text or ""
            else:
                # Check for start/end (duration)
                start_elem = period_elem.find(f".//{{{xbrli_ns}}}startDate")
                end_elem = period_elem.find(f".//{{{xbrli_ns}}}endDate")
                if start_elem is not None or end_elem is not None:
                    context_info["period_type"] = "duration"
                if start_elem is not None:
                    context_info["period_start"] = start_elem.text or ""
                if end_elem is not None:
                    context_info["period_end"] = end_elem.text or ""
        
        contexts[context_id] = context_info
    
    # Inline XBRL facts: ix:nonNumeric or ix:nonFraction
    facts = root.xpath(
        "//*[local-name()='nonNumeric' or local-name()='nonFraction']"
    )

    if not facts:
        print("Warning: No inline XBRL facts found.")
        return {"contexts": contexts, "all_facts": [], "num_facts": 0}

    all_facts = []

    for tag in facts:
        tag_type = (
            "nonFraction"
            if tag.tag.lower().endswith("nonfraction")
            else "nonNumeric"
        )

        name = tag.get("name") or ""
        context_ref = tag.get("contextRef") or tag.get("contextref") or ""
        unit_ref = tag.get("unitRef") or tag.get("unitref") or ""
        decimals = tag.get("decimals")
        fact_id = (
            tag.get("id")
            or tag.get("{http://www.w3.org/XML/1998/namespace}id")
            or ""
        )

        raw = (tag.text or "").strip()
        numeric = _normalize_number(raw) if tag_type == "nonFraction" else None

        # Use name as tag (iXBRL name attribute is already qualified like "us-gaap:Revenue")
        # Fallback to empty string if name is missing
        tag_display = name if name else ""
        
        fact = {
            "tag": tag_display,
            "tag_type": tag_type,
            "name": name,  # Keep for backward compatibility
            "contextRef": context_ref,
            "context": context_ref,  # Keep for backward compatibility
            "unitRef": unit_ref,
            "unit": unit_ref,  # Keep for backward compatibility
            "decimals": decimals,
            "id": fact_id,
            "fact_id": fact_id,  # Keep for backward compatibility
            "raw_value": raw,
            "numeric_value": numeric,
        }

        all_facts.append(fact)
        
        # Ensure context exists in contexts dict (create minimal entry if not found)
        if context_ref and context_ref not in contexts:
            contexts[context_ref] = {
                "id": context_ref,
                "entity_identifier": "",
                "entity_scheme": "",
                "period_type": "",
                "period_start": "",
                "period_end": "",
                "period_instant": ""
            }

    result = {
        "contexts": contexts,
        "all_facts": all_facts,
        "num_facts": len(all_facts),
    }

    print(f"Found {len(all_facts)} iXBRL facts across {len(contexts)} contexts.")
    return result

