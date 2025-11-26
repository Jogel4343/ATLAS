
import re
import functools
import numpy as np

# Optional: lightweight local sentence-embedding model
# Cursor will substitute an internal embedding model automatically.
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

_model = None
def _load_model():
    global _model
    if _model is None:
        if SentenceTransformer:
            _model = SentenceTransformer("all-MiniLM-L6-v2")
        else:
            raise ImportError("sentence_transformers not installed")
    return _model

# --------------------------------------------------------------
# Canonical clusters of semantically identical accounting concepts
# --------------------------------------------------------------
CANONICAL_CLUSTERS = {
    "Revenue": [
        "RevenueFromContractWithCustomer",
        "SalesRevenueNet",
        "OperatingRevenue",
        "TotalRevenue",
        "Revenues",
        "us-gaap:RevenueFromContractWithCustomer",
        "ifrs-full:Revenue",
    ],
    "CostOfRevenue": [
        "CostOfRevenue",
        "CostOfGoodsSold",
        "CostOfGoodsAndServicesSold",
        "CostOfProductsSold",
        "COGS",
        "us-gaap:CostOfRevenue",
        "us-gaap:CostOfGoodsSold",
    ],
    "OperatingIncome": [
        "OperatingIncome",
        "OperatingProfit",
        "IncomeFromOperations",
        "OperatingLoss",
        "us-gaap:OperatingIncomeLoss",
        "EBIT",
        "EarningsBeforeInterestAndTaxes",
        "EarningsBeforeInterestTax",
        "EarningsBeforeInterestAndTax",
        "OperatingEarnings",
        "OperatingEarningsBeforeInterestAndTaxes",
        "IncomeBeforeInterestAndTaxes",
        "IncomeBeforeInterestTax",
        "us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxes",
    ],
    "NetIncome": [
        "NetIncome",
        "NetIncomeLoss",
        "ProfitLoss",
        "NetEarnings",
        "us-gaap:NetIncomeLoss",
        "ifrs-full:ProfitLoss",
    ],
    "R&D": [
        "ResearchAndDevelopmentExpense",
        "ResearchAndDevelopment",
        "RDExpense",
        "us-gaap:ResearchAndDevelopmentExpense",
    ],
    "SalesMarketing": [
        "SellingAndMarketingExpense",
        "MarketingExpense",
        "SalesAndMarketing",
        "us-gaap:SellingAndMarketingExpense",
    ],
    "GandA": [
        "SellingGeneralAndAdministrative",
        "GeneralAndAdministrative",
        "SG&A",
        "us-gaap:SellingGeneralAndAdministrativeExpense",
    ],
    "PPE": [
        "PropertyPlantAndEquipmentNet",
        "PropertyPlantEquipment",
        "FixedAssetsNet",
        "us-gaap:PropertyPlantAndEquipmentNet",
    ],
    "Goodwill": [
        "Goodwill",
        "us-gaap:Goodwill",
        "ifrs-full:Goodwill",
    ],
    "Intangibles": [
        "IntangibleAssetsNetExcludingGoodwill",
        "IntangibleAssetsNet",
        "IntangibleAssets",
        "us-gaap:IntangibleAssetsNetExcludingGoodwill",
    ],
    "Cash": [
        "CashAndCashEquivalents",
        "CashCashEquivalentsAndShortTermInvestments",
        "CashAndShortTermInvestments",
        "us-gaap:CashAndCashEquivalentsAtCarryingValue",
    ],
    "SharesOutstanding": [
        "WeightedAverageNumberOfSharesOutstandingBasic",
        "WeightedAverageSharesOutstanding",
        "CommonStockSharesOutstanding",
    ]
}

# Flatten index for quick mask
CANONICAL_LOOKUP = {alias: canonical 
    for canonical, aliases in CANONICAL_CLUSTERS.items() 
    for alias in aliases
}

PREFIX_RE = re.compile(r"^(us-gaap:|ifrs-full:)", re.IGNORECASE)

# ----------------------------------------------------------
# Utility: strip GAAP/IFRS prefixes
# ----------------------------------------------------------
def strip_prefix(concept):
    return PREFIX_RE.sub("", concept)

# ----------------------------------------------------------
# Fuzzy matching heuristic
# ----------------------------------------------------------
def _simple_similarity(a, b):
    a, b = a.lower(), b.lower()
    if a == b:
        return 1.0
    # partial overlap heuristic
    overlap = len(set(a.split()) & set(b.split()))
    return overlap / max(len(a.split()), 1)

# ----------------------------------------------------------
# Embedding similarity
# ----------------------------------------------------------
@functools.lru_cache(maxsize=4096)
def embed(text):
    model = _load_model()
    vec = model.encode([text])[0]
    return vec / np.linalg.norm(vec)

def embedding_similarity(a, b):
    va = embed(a)
    vb = embed(b)
    return float(np.dot(va, vb))

# ----------------------------------------------------------
# The main resolver (Stage 1: Alias Clusters)
# ----------------------------------------------------------
def resolve(concept: str):
    """
    Return the canonical concept name from alias clusters.
    If no match found, return the stripped base name.
    """
    raw = concept.strip()
    base = strip_prefix(raw)

    # 1. Exact alias match
    if raw in CANONICAL_LOOKUP:
        return CANONICAL_LOOKUP[raw]
    if base in CANONICAL_LOOKUP:
        return CANONICAL_LOOKUP[base]

    # 2. Cheap fuzzy
    best = None
    best_score = 0
    for alias, canonical in CANONICAL_LOOKUP.items():
        s = _simple_similarity(base, alias)
        if s > best_score:
            best_score, best = s, canonical

    if best_score >= 0.6:
        return best

    # 3. Embedding-based fallback (against aliases)
    try:
        best = None
        best_score = 0
        for alias, canonical in CANONICAL_LOOKUP.items():
            s = embedding_similarity(base, alias)
            if s > best_score:
                best_score, best = s, canonical

        if best_score >= 0.55:
            return best
    except Exception:
        pass

    # 4. Final fallback: return raw stripped name
    return base

# ----------------------------------------------------------
# Helpers for Hybrid Scoring
# ----------------------------------------------------------
def classify_concept(text):
    """Classify concept text into broad financial categories."""
    t = text.lower()
    if "tax" in t: 
        return "Tax"
    if "revenue" in t or "sales" in t: 
        return "Revenue"
    if "cost of" in t or "cogs" in t: 
        return "COGS"
    if "operating" in t or "ebit" in t: 
        return "Operating"
    if "interest" in t or "debt" in t: 
        return "Financing"
    if "share" in t or "eps" in t: 
        return "EPS"
    # Fallback for generic income/profit logic
    if "income" in t or "loss" in t or "profit" in t or "earnings" in t:
        return "Operating"
    return "Other"

def tokenize(text):
    """Split text by CamelCase and non-alphanumeric delimiters."""
    # [A-Z]?[a-z]+ matches standard words
    # [A-Z]+(?=[A-Z]|$) matches acronyms or consecutive caps
    return set(re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', text))

def keyword_overlap_score(query, fact_name):
    q_tokens = {t.lower() for t in tokenize(query)}
    f_tokens = {t.lower() for t in tokenize(fact_name)}
    if not q_tokens: 
        return 0.0
    intersection = q_tokens & f_tokens
    return len(intersection) / len(q_tokens)

# ----------------------------------------------------------
# Filing-specific fact resolver (Stage 2: Semantic Search)
# ----------------------------------------------------------
def resolve_to_fact(query: str, all_facts: list) -> str:
    """
    Uses embedding similarity + heuristic priors to find the closest actual fact['name']
    in the company's XBRL fact list.
    
    Scoring = 0.60*Cosine + 0.25*Overlap + 0.15*Category - Penalties
    """
    query_base = strip_prefix(query.strip())
    query_cat = classify_concept(query_base)
    q_low = query_base.lower()
    
    # Collect unique fact names from the filing
    unique_names = set()
    for f in all_facts:
        name = f.get("name") or f.get("tag")
        if name:
            unique_names.add(name)
            
    if not unique_names:
        return None

    best = None
    best_score = -float('inf')
    
    try:
        for name in unique_names:
            name_base = strip_prefix(name)
            fact_cat = classify_concept(name_base)
            n_low = name_base.lower()
            
            # 1. Cosine Similarity
            try:
                sim = embedding_similarity(query_base, name_base)
            except:
                sim = 0.0
                
            # 2. Keyword Overlap
            overlap = keyword_overlap_score(query_base, name_base)
            
            # 3. Category Prior
            cat_score = 0.0
            if query_cat == fact_cat and query_cat != "Other":
                cat_score = 0.15
            elif query_cat == "Operating" and fact_cat == "Tax":
                cat_score = -0.15
            elif query_cat == "Tax" and fact_cat == "Operating":
                cat_score = -0.15
                
            # 4. Negative Priors (Specific contradictions)
            penalty = 0.0
            if "operat" in q_low and "tax" in n_low:
                penalty += 0.20
            if "tax" in q_low and "operat" in n_low:
                penalty += 0.20
            # Avoid mixing Revenue and Net Income
            if "revenue" in q_low and "net income" in n_low:
                penalty += 0.10
            if "net income" in q_low and "revenue" in n_low:
                penalty += 0.10
                
            # Final Score Calculation
            final = (0.60 * sim) + (0.25 * overlap) + cat_score - penalty
            
            if final > best_score:
                best_score = final
                best = name
                
        # Threshold: use a safe floor
        if best_score >= 0.40:
            return best
            
    except Exception:
        pass
        
    return None
