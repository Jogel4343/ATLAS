"""
Volume Driver Inference Module — Deterministic + Safe Version
"""

from typing import Dict, Optional
from src.xbrl.concept_resolver import resolve

# --------------------------
# Safe accessor
# --------------------------
def safe_get(atlas, concept):
    """Return atlas.get(resolve(concept)) safely; return None on any failure."""
    try:
        return atlas.get(resolve(concept))
    except Exception:
        return None

# --------------------------
# Industry → candidate drivers
# --------------------------
INDUSTRY_DRIVERS = {
    "SaaS": ["ARR", "MRR", "Subscribers", "MAUs"],
    "Marketplaces": ["GMV", "Orders", "ActiveBuyers"],
    "Social": ["MAUs", "DAUs", "Impressions"],
    "Ecommerce": ["Orders", "Shipments", "UnitsSold"],
    "Airlines": ["ASMs", "RPMs", "Passengers", "Routes"],
    "Semiconductors": ["WafersStarted", "DiePerWafer", "UnitsShipped"],
    "PaymentNetworks": ["TPV", "Transactions", "ActiveCards"],
    "Retail": ["SameStoreSales", "FootTraffic", "Baskets"],
    "Energy": ["Barrels", "BOE", "ProductionVolume"],
    "Manufacturing": ["UnitsProduced", "LineHours", "CapacityUtilization"],
}

# --------------------------
# Ticker → Industry mapping
# --------------------------
COMPANY_INDUSTRY_MAP = {
    "aapl": "Ecommerce",
    "amzn": "Ecommerce",
    "msft": "SaaS",
    "meta": "Social",
    "nflx": "SaaS",
    "uber": "Marketplaces",
    "cost": "Retail",
    "wmt": "Retail",
    "unh": "SaaS",
    "tsla": "Manufacturing",
    "tsm": "Semiconductors",
    "nvda": "Semiconductors",
    "amd": "Semiconductors",
    "jpm": "PaymentNetworks",
    "ma": "PaymentNetworks",
    "v": "PaymentNetworks",
    "pypl": "PaymentNetworks",
    "xom": "Energy",
    "cvx": "Energy",
    "hd": "Retail",
}

# --------------------------
# Main inference for segments
# --------------------------
def resolve_all_segments(atlas) -> Dict[str, str]:
    """
    Determine the company's volume driver (single‑segment assumption).
    Guaranteed to return *something*, finally "Revenue".
    """
    ticker = atlas.ticker.lower()
    industry = COMPANY_INDUSTRY_MAP.get(ticker, "SaaS")

    # Primary candidate list
    candidates = list(INDUSTRY_DRIVERS.get(industry, []))

    # Generic fallbacks
    candidates += ["UnitsSold", "Subscribers", "Customers", "Users"]

    found = None

    # Try deterministic driver search
    for driver in candidates:
        val = safe_get(atlas, driver)
        if isinstance(val, (int, float)) and val > 0:
            found = driver
            break

    # Correlation fallback
    if not found:
        found = _find_correlated_metric(atlas)

    # Final fallback
    if not found:
        found = "Revenue"

    return {"consolidated": found}

# --------------------------
# Correlation fallback
# --------------------------
def _find_correlated_metric(atlas) -> Optional[str]:
    """
    Find any metric correlated with Revenue.
    Returns None if nothing viable.
    """
    try:
        rev_series = atlas.series("Revenue", kind="raw")
        if not rev_series or len(rev_series) < 3:
            return None

        rev_dict = dict(rev_series)
        years = sorted(rev_dict.keys())

        # Build candidate list
        candidates = ["Employees", "Assets", "OpEx"]
        for drivers in INDUSTRY_DRIVERS.values():
            candidates.extend(drivers)

        best_metric = None
        best_corr = 0.0

        import statistics

        for metric in set(candidates):
            if metric == "Revenue":
                continue

            try:
                # atlas.series() implicitly calls resolve() inside build_concept_series
                series = atlas.series(metric, kind="raw")
            except Exception:
                series = None

            if not series or len(series) < 3:
                continue

            met_dict = dict(series)

            # Align series
            x = []
            y = []
            for yr in years:
                if yr in met_dict and met_dict[yr] is not None:
                    x.append(rev_dict[yr])
                    y.append(met_dict[yr])

            if len(x) < 3:
                continue
            if len(set(x)) == 1 or len(set(y)) == 1:
                continue

            try:
                corr = statistics.correlation(x, y)
                if abs(corr) > best_corr:
                    best_corr = abs(corr)
                    best_metric = metric
            except Exception:
                continue

        return best_metric

    except Exception:
        return None
