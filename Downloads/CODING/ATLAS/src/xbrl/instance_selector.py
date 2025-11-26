import os
import lxml.etree as ET

IXBRL_TAGS = ["{http://www.xbrl.org/2013/inlineXBRL}", "{http://www.xbrl.org/2014/inlineXBRL}", "ix:"]


# Files to exclude (linkbases + summaries)
BAD_KEYWORDS = ["cal", "def", "lab", "pre", "rfs", "summary"]


def score_instance_candidate(path):
    score = 0
    lower = os.path.basename(path).lower()

    # Hard penalties for known non-instance files
    if any(bad in lower for bad in BAD_KEYWORDS):
        return -1000

    size_kb = os.path.getsize(path) / 1024

    # Small XML → penalize hard
    if size_kb < 5:
        score -= 20

    # Reward larger files (cap at +10)
    score += min(size_kb / 10, 10)

    try:
        tree = ET.parse(path)
        root = tree.getroot()
        nsmap = list(root.nsmap.values())
    except Exception:
        # unreadable or broken XML → drop score
        return score - 50

    # XBRL instance namespace
    if "http://www.xbrl.org/2003/instance" in nsmap:
        score += 50

    # Inline XBRL detection
    root_tag = ET.QName(root).namespace or ""
    if any(tag in root_tag for tag in IXBRL_TAGS):
        score += 40
        # Count ix:nonFraction or ix:nonNumeric elements
        try:
            ix_count = sum(
                1 for elem in tree.iter()
                if ("nonfraction" in elem.tag.lower() or "nonnumeric" in elem.tag.lower())
            )
            if ix_count > 10:
                score += 25
        except:
            pass

    # GAAP taxonomy present
    if any(str(ns).startswith("http://fasb.org/us-gaap/") for ns in nsmap if ns):
        score += 30

    # Filename hint
    if "instance" in lower:
        score += 10

    # Accession-like filename (leading digits)
    if any(char.isdigit() for char in lower[:8]):
        score += 5

    # Count facts — strong signal
    try:
        fact_count = sum(
            1 for elem in tree.iter()
            if elem.tag.startswith("{http://fasb.org/us-gaap/}")
        )
        if fact_count > 20:
            score += 25
    except:
        pass

    return score


def find_xbrl_instance(filing_dir):
    xbrl_dir = os.path.join(filing_dir, "xbrl")
    search_root = xbrl_dir if os.path.isdir(xbrl_dir) else filing_dir

    candidates = []

    # Collect all XML/HTML files
    for root, _, files in os.walk(search_root):
        for f in files:
            lower = f.lower()
            if lower.endswith(".xml") or lower.endswith(".htm") or lower.endswith(".html"):
                candidates.append(os.path.join(root, f))

    if not candidates:
        return None

    # Score all candidates
    scored = [(score_instance_candidate(path), path) for path in candidates]

    # Tier 1: pick best HTML iXBRL
    ix_html_candidates = []
    for _, path in scored:
        if path.lower().endswith(('.htm', '.html')):
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                # Quick check for inlineXBRL namespaces or ix: tags
                if ('http://www.xbrl.org/2013/inlineXBRL' in content or
                    'http://www.xbrl.org/2014/inlineXBRL' in content or
                    'ix:' in content):
                    ix_html_candidates.append(path)
            except Exception:
                continue
    if ix_html_candidates:
        # Return the largest iXBRL HTML file
        best_html = max(ix_html_candidates, key=lambda p: os.path.getsize(p))
        return best_html

    # Tier 2: XML instance candidates with XBRL instance namespace
    xml_instance_candidates = []
    for _, path in scored:
        if path.lower().endswith('.xml'):
            try:
                tree = ET.parse(path)
                root = tree.getroot()
                nsmap = list(root.nsmap.values())
                if "http://www.xbrl.org/2003/instance" in nsmap:
                    xml_instance_candidates.append(path)
            except Exception:
                continue
    if xml_instance_candidates:
        # Return the largest XML instance file
        best_xml = max(xml_instance_candidates, key=lambda p: os.path.getsize(p))
        return best_xml

    # Tier 3: fallback to file with high fact_count (>20)
    high_fact_candidates = []
    for _, path in scored:
        try:
            tree = ET.parse(path)
            fact_count = sum(
                1 for elem in tree.iter()
                if elem.tag.startswith("{http://fasb.org/us-gaap/}")
            )
            if fact_count > 20:
                high_fact_candidates.append((fact_count, path))
        except Exception:
            continue
    if high_fact_candidates:
        # Return file with highest fact count
        _, best_fact_path = max(high_fact_candidates, key=lambda x: x[0])
        return best_fact_path

    return None
