import lxml.etree as ET
from src.xbrl.concept_resolver import resolve, resolve_to_fact


def _extract_end_date_year(fact):
    """
    Given a fact dict, extract the endDate year from its context.
    Returns int year or None.
    """
    raw = fact["raw"]
    ctx = raw.attrib.get("contextRef")
    if ctx is None:
        return None

    try:
        context = raw.getroottree().find(f".//{{*}}context[@id='{ctx}']")
        if context is None:
            return None

        end = context.find(".//{*}endDate")
        if end is None:
            return None

        return int(end.text.split("-")[0])
    except:
        return None


def extract_facts(instance_path):
    """Parse all US GAAP facts from an XBRL instance document."""
    tree = ET.parse(instance_path)
    root = tree.getroot()

    facts = []

    for elem in root.iter():
        tag = elem.tag
        # Accept ANY us-gaap taxonomy namespace (versioned or unversioned)
        if "us-gaap" not in tag.lower() and "ifrs" not in tag.lower():
            continue

        if "}" in tag:
            qname = tag.split("}")[1]
        else:
            qname = tag

        full_tag = tag # Store raw tag or constructed?
        if "us-gaap" in tag.lower():
            full_tag = "us-gaap:" + qname
        elif "ifrs" in tag.lower():
            full_tag = "ifrs-full:" + qname
        else:
            full_tag = qname

        context = elem.attrib.get("contextRef")
        unit = elem.attrib.get("unitRef")
        value = elem.text

        if value is None:
            continue

        facts.append({
            "tag": full_tag,
            "name": qname,
            "value": value,
            "context": context,
            "unit": unit,
            "raw": elem
        })

    return facts


def get_concept_value(concept, all_facts, year=None):
    """
    Extract the latest value for a canonical concept.
    Uses dynamic concept resolution with filing-specific semantic fallback.
    """
    canonical = resolve(concept)
    
    # Collect all matching facts
    matches = []
    
    # Stage 1: Canonical Alias Match
    for f in all_facts:
        fname = f.get("name")
        if not fname:
            continue
            
        if resolve(fname) == canonical:
            matches.append(f)

    # Stage 2: Filing-Specific Semantic Fallback
    if not matches:
        # Use ORIGINAL query 'concept' for semantic search
        best_fact_name = resolve_to_fact(concept, all_facts)
        if best_fact_name:
            for f in all_facts:
                fname = f.get("name") or f.get("tag")
                # Check if this fact matches the resolved best name
                if fname == best_fact_name:
                    matches.append(f)

    if not matches:
        return None

    # --- Period matching ---
    dated = []
    for f in matches:
        y = _extract_end_date_year(f)
        if y is not None:
            dated.append((y, f))
            
    if year is not None:
        # Exact match
        exact = [f for (y, f) in dated if y == year]
        if exact:
            try:
                return float(exact[-1]["value"])
            except:
                pass

        # Fallback: nearest year by |year - target|
        if dated:
            dated.sort(key=lambda x: abs(x[0] - year))
            try:
                return float(dated[0][1]["value"])
            except:
                pass
                
    # --- Default: return latest year fact ---
    if dated:
        dated.sort(key=lambda x: x[0])  # ascending year
        try:
            return float(dated[-1][1]["value"])
        except:
            pass

    return None


def build_concept_series(concept, all_facts):
    """
    Return list of (year, value) pairs for a given canonical concept.
    Sorted ascending by year, deduped.
    """
    canonical = resolve(concept)
    
    raw_matches = []
    
    # Stage 1: Canonical Alias Match
    for f in all_facts:
        fname = f.get("name")
        if not fname:
            continue
            
        if resolve(fname) == canonical:
            y = _extract_end_date_year(f)
            if y is not None:
                raw_matches.append((y, f))

    # Stage 2: Filing-Specific Semantic Fallback
    if not raw_matches:
        best_fact_name = resolve_to_fact(concept, all_facts)
        if best_fact_name:
            for f in all_facts:
                fname = f.get("name") or f.get("tag")
                if fname == best_fact_name:
                    y = _extract_end_date_year(f)
                    if y is not None:
                        raw_matches.append((y, f))

    # Dedup logic
    dedup = {}
    for y, f in raw_matches:
        try:
            dedup[y] = float(f["value"])
        except:
            continue

    series = sorted(dedup.items(), key=lambda x: x[0])
    return series
