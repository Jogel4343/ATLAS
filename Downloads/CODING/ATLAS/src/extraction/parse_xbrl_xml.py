"""
Module for parsing traditional XBRL XML instance documents from SEC filings.

Extracts XBRL facts, contexts, and units from standalone XBRL instance documents.
"""

import os
import json
from lxml import etree


def _normalize_number(value):
    """Normalize numeric strings from XBRL facts."""
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


def _extract_namespace_prefix(tag, root):
    """
    Extract namespace prefix from element tag.
    
    Args:
        tag: Element tag in format "{namespace}LocalName"
        root: Root element to get namespace map from
        
    Returns:
        Prefix string (e.g., "us-gaap", "dei") or empty string
    """
    if not tag or not tag.startswith("{"):
        return ""
    
    # Extract namespace URI
    namespace_uri = tag[1:tag.find("}")]
    
    # Get namespace map from root
    nsmap = root.nsmap
    
    # Find prefix for this namespace
    for prefix, uri in nsmap.items():
        if uri == namespace_uri:
            return prefix if prefix else ""
    
    return ""


def parse_xbrl_xml(xml_path, save_json=True):
    """
    Parse traditional XBRL XML instance document from SEC filing.
    
    Extracts contexts, units, and facts from XBRL instance documents.
    
    Args:
        xml_path: Local path to the XBRL instance XML file
        save_json: Whether to save results to JSON file (default: True)
        
    Returns:
        Dictionary containing:
        {
            "contexts": {context_id: {...context info...}},
            "units": {unit_id: {...unit info...}},
            "all_facts": [...],
            "num_facts": N
        }
    """
    if not os.path.exists(xml_path):
        print(f"Error: XML file not found: {xml_path}")
        return {
            "contexts": {},
            "units": {},
            "all_facts": [],
            "num_facts": 0
        }

    # Parse XML using lxml.etree
    try:
        tree = etree.parse(xml_path)
        root = tree.getroot()
        print(f"Parsed XBRL XML: {xml_path}")
    except Exception as e:
        print(f"XML parse error: {e}")
        return {
            "contexts": {},
            "units": {},
            "all_facts": [],
            "num_facts": 0
        }

    # Get namespace map
    nsmap = root.nsmap
    xbrli_ns = nsmap.get('xbrli') or 'http://www.xbrl.org/2003/instance'
    link_ns = nsmap.get('link') or 'http://www.xbrl.org/2003/linkbase'
    
    # Extract all xbrli:context nodes
    contexts = {}
    context_elements = root.xpath(f"//*[local-name()='context']", namespaces={'xbrli': xbrli_ns})
    
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
    
    print(f"Found {len(contexts)} contexts")
    
    # Extract all xbrli:unit nodes
    units = {}
    unit_elements = root.xpath(f"//*[local-name()='unit']", namespaces={'xbrli': xbrli_ns})
    
    for unit_elem in unit_elements:
        unit_id = unit_elem.get("id", "")
        if not unit_id:
            continue
        
        unit_info = {
            "id": unit_id,
            "measure": "",
            "divide_numerator": [],
            "divide_denominator": []
        }
        
        # Extract measure
        measure_elem = unit_elem.find(f".//{{{xbrli_ns}}}measure")
        if measure_elem is not None:
            unit_info["measure"] = measure_elem.text or ""
        
        # Check for divide (complex units)
        divide_elem = unit_elem.find(f".//{{{xbrli_ns}}}divide")
        if divide_elem is not None:
            numerator_elem = divide_elem.find(f".//{{{xbrli_ns}}}unitNumerator")
            if numerator_elem is not None:
                for measure in numerator_elem.findall(f".//{{{xbrli_ns}}}measure"):
                    if measure.text:
                        unit_info["divide_numerator"].append(measure.text)
            
            denominator_elem = divide_elem.find(f".//{{{xbrli_ns}}}unitDenominator")
            if denominator_elem is not None:
                for measure in denominator_elem.findall(f".//{{{xbrli_ns}}}measure"):
                    if measure.text:
                        unit_info["divide_denominator"].append(measure.text)
        
        units[unit_id] = unit_info
    
    print(f"Found {len(units)} units")
    
    # Extract all fact nodes (elements NOT in xbrli or link namespaces)
    all_facts = []
    
    # Get all elements, filter out xbrli and link namespace elements
    all_elements = root.xpath("//*")
    
    for elem in all_elements:
        tag = elem.tag
        
        # Skip if in xbrli namespace
        if tag.startswith(f"{{{xbrli_ns}}}"):
            continue
        
        # Skip if in link namespace
        if tag.startswith(f"{{{link_ns}}}"):
            continue
        
        # Skip if it's the root element (usually xbrli:xbrl)
        if elem == root:
            continue
        
        # Extract fact information
        context_ref = elem.get("contextRef", "") or ""
        unit_ref = elem.get("unitRef", "") or ""
        decimals = elem.get("decimals")
        fact_id = elem.get("id", "") or ""
        
        # Get tag with prefix
        tag_local = tag.split("}")[-1] if "}" in tag else tag
        tag_prefix = _extract_namespace_prefix(tag, root)
        tag_display = f"{tag_prefix}:{tag_local}" if tag_prefix else tag_local
        
        # Get raw text content
        raw_value = (elem.text or "").strip()
        
        # Try to normalize numeric value
        numeric_value = _normalize_number(raw_value)
        
        fact = {
            "tag": tag_display,
            "tag_full": tag,
            "contextRef": context_ref,
            "unitRef": unit_ref,
            "decimals": decimals,
            "id": fact_id,
            "raw_value": raw_value,
            "numeric_value": numeric_value
        }
        
        all_facts.append(fact)
    
    num_facts = len(all_facts)
    print(f"Found {num_facts} facts")
    
    # Prepare output structure
    result = {
        "contexts": contexts,
        "units": units,
        "all_facts": all_facts,
        "num_facts": num_facts
    }
    
    # Save to JSON if requested
    if save_json:
        # Determine save path based on XML file location
        xml_dir = os.path.dirname(os.path.abspath(xml_path))
        
        # If XML is in data/raw/<filing>/xbrl/, save to data/extracted/<filing>/
        if 'data/raw' in xml_dir:
            # Extract the filing directory name
            parts = xml_dir.split(os.sep)
            if 'xbrl' in parts:
                # Remove 'xbrl' from path and replace 'raw' with 'extracted'
                filing_idx = parts.index('raw')
                filing_parts = parts[filing_idx + 1:-1]  # Get parts after 'raw' but before 'xbrl'
                extracted_dir = os.path.join("data", "extracted", *filing_parts)
            else:
                extracted_dir = xml_dir.replace('data/raw', 'data/extracted')
        else:
            # Fallback: save to data/extracted relative to project root
            extracted_dir = os.path.join("data", "extracted", "xbrl_filing")
        
        os.makedirs(extracted_dir, exist_ok=True)
        save_path = os.path.join(extracted_dir, "xbrl_facts.json")
        
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"Saved XBRL facts → {save_path}")
    
    return result


if __name__ == "__main__":
    # Example usage
    test_path = "data/raw/msft_2025_10k/xbrl/msft-20250630.xml"
    if os.path.exists(test_path):
        result = parse_xbrl_xml(test_path)
        print(f"Parsed {result['num_facts']} XBRL facts")
    else:
        print(f"Test file not found: {test_path}")
