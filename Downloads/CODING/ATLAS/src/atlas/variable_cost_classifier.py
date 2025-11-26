"""
Variable Cost Classifier.
Deterministic rule-based classification of line items into Variable or Fixed buckets.
"""

from typing import Literal

CostType = Literal["variable", "fixed", "unknown"]

# Deterministic Rules
VARIABLE_KEYWORDS = [
    "payment processing",
    "processing fee",
    "transaction fee",
    "revenue share",
    "commission",
    "shipping",
    "freight",
    "delivery",
    "fulfillment",
    "packaging",
    "hosting",
    "cloud infrastructure", # Often variable with usage
    "cost of goods",
    "cost of revenue",
    "inventory",
    "sales commission",
    "customer acquisition cost", # debatable, but often treated as variable per unit in LTV/CAC
    "cac",
    "marketing", # Retention marketing is variable, brand is fixed. We default strictly.
]

FIXED_KEYWORDS = [
    "rent",
    "lease",
    "depreciation",
    "amortization",
    "stock-based compensation",
    "sbc",
    "share-based",
    "salaries", # General salaries are fixed in short run
    "wages",
    "general and administrative",
    "g&a",
    "overhead",
    "corporate",
    "research and development",
    "r&d",
    "engineering", # Usually fixed headcount
    "audit",
    "legal",
    "insurance",
]

def classify_cost(tag: str, facts: dict = None) -> CostType:
    """
    Classify a cost line item tag as 'variable' or 'fixed'.
    """
    normalized = tag.lower().replace("_", " ")
    
    # 1. Check Variable Rules
    for kw in VARIABLE_KEYWORDS:
        if kw in normalized:
            # Exception: Salaries in COGS? Handled by broad "cost of revenue" usually being variable
            # but "stock based compensation" is always fixed
            if "stock" in normalized or "share-based" in normalized:
                return "fixed"
            return "variable"
            
    # 2. Check Fixed Rules
    for kw in FIXED_KEYWORDS:
        if kw in normalized:
            return "fixed"
            
    # 3. Default behavior
    # GAAP Cost of Revenue is roughly Variable COGS
    if "costofrevenue" in normalized.replace(" ", ""):
        return "variable"
    if "costofgoodssold" in normalized.replace(" ", ""):
        return "variable"
        
    # OpEx is generally Fixed (unless Marketing)
    if "operatingexpense" in normalized.replace(" ", ""):
        return "fixed"
        
    return "fixed" # Conservative default for unit economics (don't overstate Contribution Margin)

def estimate_variable_portion(concept: str, value: float) -> float:
    """
    Return the estimated variable amount of a line item.
    1.0 if variable, 0.0 if fixed.
    """
    classification = classify_cost(concept)
    if classification == "variable":
        return value
    return 0.0

