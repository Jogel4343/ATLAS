import os
import json
from lxml import html


def _normalize_number(value):
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


def parse_ixbrl(html_path, save_json=True):
    """Extract inline XBRL (iXBRL) facts from SEC HTML filings using lxml."""

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

    # Inline XBRL facts: ix:nonNumeric or ix:nonFraction
    facts = root.xpath(
        "//*[local-name()='nonNumeric' or local-name()='nonFraction']"
    )

    if not facts:
        print("Warning: No inline XBRL facts found.")
        return {"contexts": {}, "all_facts": [], "num_facts": 0}

    all_facts = []
    contexts = {}

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

        fact = {
            "tag_type": tag_type,
            "name":    name,
            "context": context_ref,
            "unit":    unit_ref,
            "decimals": decimals,
            "fact_id": fact_id,
            "raw_value": raw,
            "numeric_value": numeric,
        }

        all_facts.append(fact)

        if context_ref:
            contexts.setdefault(context_ref, []).append(fact)

    result = {
        "contexts": contexts,
        "all_facts": all_facts,
        "num_facts": len(all_facts),
    }

    # Save output
    if save_json:
        base_dir = html_path.split("data/raw/")[-1]
        extracted_dir = os.path.join("data", "extracted", base_dir)
        extracted_dir = extracted_dir.replace(".html", "")
        os.makedirs(extracted_dir, exist_ok=True)

        save_path = os.path.join(extracted_dir, "ixbrl_facts.json")
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        print(f"Saved iXBRL facts → {save_path}")

    print(f"Found {len(all_facts)} iXBRL facts across {len(contexts)} contexts.")
    return result


if __name__ == "__main__":
    test_path = "data/raw/msft_2025_10k/msft_2025_10k.html"
    if os.path.exists(test_path):
        parse_ixbrl(test_path)
    else:
        print("Test file not found.")
