import pdfplumber
import re
from thefuzz import fuzz

SCALE_MULTIPLIERS = {
    "thousands": 1000,
    "millions": 1000000,
    "billions": 1000000000
}

def parse_value(val_str):
    """
    Normalize a financial number string.
    Handles:
    - Parentheses for negative: (123) -> -123
    - Commas: 1,234 -> 1234
    - Whitespace
    - Non-numeric cleanup
    """
    if not val_str:
        return None
    
    s = str(val_str).strip()
    if not s:
        return None
        
    is_negative = False
    if "(" in s and ")" in s:
        is_negative = True
        s = s.replace("(", "").replace(")", "")
    elif s.startswith("-"):
        # Check if it's just a dash (zero or nil)
        if s == "-":
            return 0.0
        is_negative = True
        s = s.replace("-", "")
    elif s == "—" or s == "–": # Em dash / En dash usually means 0
        return 0.0
        
    # Remove commas and currency symbols
    s = re.sub(r"[^\d\.]", "", s)
    
    if not s:
        return None
        
    try:
        val = float(s)
        if is_negative:
            val = -val
        return val
    except:
        return None

def detect_scale(text_lines):
    """
    Detect scale from text lines (e.g. header rows or page context).
    Returns multiplier (1, 1000, 1000000).
    """
    full_text = " ".join([str(x).lower() for x in text_lines if x]).replace("\n", " ")
    
    if "in millions" in full_text or "(millions)" in full_text:
        return 1000000
    if "in thousands" in full_text or "(thousands)" in full_text:
        return 1000
    if "in billions" in full_text or "(billions)" in full_text:
        return 1000000000
        
    return 1

def find_year_columns(header_row):
    """
    Identify columns that represent years.
    Returns dict: {col_index: year_int}
    """
    year_map = {}
    for idx, cell in enumerate(header_row):
        if not cell:
            continue
        # Look for 4-digit year 1990-2030
        # Matches "2023", "Dec 31, 2023", "FY 2023"
        matches = re.findall(r"\b(199\d|20[0-2]\d)\b", str(cell))
        if matches:
            # Take the last match (e.g. "Dec 31, 2023" -> 2023)
            try:
                y = int(matches[-1])
                year_map[idx] = y
            except:
                pass
    return year_map

def extract_from_pdf(pdf_path: str, query: str) -> dict:
    """
    Returns {year: value} for the requested row.
    Returns {} if nothing could be extracted.
    
    Strategy:
    1. Iterate through PDF pages.
    2. Extract tables.
    3. Detect years in header.
    4. Fuzzy match row labels to query.
    5. Return best match.
    """
    results = {}
    best_score = 0
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Optimization: Search mainly in the first 1/3 of pages or key financial sections?
            # 10-Ks are huge. Financials are usually Item 8. 
            # We'll just iterate. If slow, we can optimize later.
            
            for page in pdf.pages:
                # Check for tables
                tables = page.extract_tables()
                
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                        
                    # Analyze header (first few rows)
                    # Sometimes header is split across multiple rows. 
                    # We'll look at the first 3 rows for years.
                    year_map = {}
                    header_text = []
                    
                    start_row_idx = 0
                    for i in range(min(3, len(table))):
                        row = table[i]
                        ym = find_year_columns(row)
                        if ym:
                            year_map.update(ym)
                            # If we found years, this is likely the header area.
                            # Data starts after this row? Or is this the header?
                            # Usually data starts after the last header row.
                            start_row_idx = i + 1
                        header_text.extend([str(c) for c in row if c])
                    
                    if not year_map:
                        continue
                        
                    # Detect scale from header text
                    scale = detect_scale(header_text)
                    
                    # Iterate data rows
                    for i in range(start_row_idx, len(table)):
                        row = table[i]
                        # Label is usually first non-empty column
                        label = None
                        for cell in row:
                            if cell and str(cell).strip():
                                label = str(cell).strip().replace("\n", " ")
                                break
                        
                        if not label:
                            continue
                            
                        # Fuzzy match query
                        # Partial ratio handles "Operating income (loss)" vs "Operating Income"
                        score = fuzz.partial_ratio(query.lower(), label.lower())
                        
                        # Boost score for exact containment matching if identifying words present
                        # e.g. "Total Operating Income" vs "Operating Income"
                        
                        if score > 80 and score > best_score:
                            # Extract values for mapped years
                            row_vals = {}
                            valid_row = False
                            
                            for col_idx, year in year_map.items():
                                if col_idx < len(row):
                                    val = parse_value(row[col_idx])
                                    if val is not None:
                                        row_vals[year] = val * scale
                                        valid_row = True
                                        
                            if valid_row:
                                results = row_vals
                                best_score = score
                                
            # If we found a very good match (>90), return it.
            # If we found a decent match (>80), return it.
            # The loop updates 'results' only if score > best_score.
            
    except Exception as e:
        print(f"PDF Extraction Error: {e}")
        return {}
        
    return results if best_score > 80 else {}

