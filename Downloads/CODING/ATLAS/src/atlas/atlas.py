"""
High-level Fact Retrieval API for ATLAS.
"""

from __future__ import annotations

import os
import glob
from src.utils.edgar_download import download_filing
from src.xbrl.loader import load_xbrl_facts
from src.xbrl.fact_index import FactIndex, get_fact, get_numeric
from src.xbrl.fact_extractor import extract_facts, get_concept_value, build_concept_series
from src.xbrl.instance_selector import find_xbrl_instance
from src.kpi_engine import KPIEngine
from src.xbrl.concept_resolver import resolve
from src.pdf.pdf_extractor import extract_from_pdf


def _compute_yoy(series):
    """
    year-over-year growth: (v_t - v_t-1) / v_t-1
    Returns list [(year, yoy), ...] aligned to series except first.
    """
    out = []
    for i in range(1, len(series)):
        y_prev, v_prev = series[i-1]
        y_curr, v_curr = series[i]
        if v_prev is None or v_prev == 0:
            out.append((y_curr, None))
        else:
            out.append((y_curr, (v_curr - v_prev) / v_prev))
    return out


def _compute_cagr(series):
    """
    CAGR from first → last entry.
    Returns single float or None.
    """
    if len(series) < 2:
        return None
    y0, v0 = series[0]
    y1, v1 = series[-1]
    if v0 <= 0:
        return None
    years = y1 - y0
    if years <= 0:
        return None
    return (v1 / v0)**(1/years) - 1


def _compute_trend(series):
    """
    Normalized trend via z-score of last value relative to historical mean.
    Rough but useful.
    """
    vals = [v for _, v in series if v is not None]
    if len(vals) < 2:
        return None
    import statistics as stats
    mu = stats.mean(vals)
    sd = stats.stdev(vals)
    if sd == 0:
        return None
    return (vals[-1] - mu) / sd


def _compute_ttm(series):
    """
    TTM approximation using last 4 annual values.
    Only works if >=4 datapoints exist.
    """
    if len(series) < 4:
        return None
    vals = [v for _, v in series[-4:]]
    return sum(vals)


class Atlas:
    def __init__(self, ticker: str, period: str):
        self.ticker = ticker.lower()
        self.period = period.lower()

        # Ensure raw filing is present (download or cached)
        download_filing(self.ticker, self.period)

        # Filing directory matches loader expectations
        self.filing_dir = f"data/raw/{self.ticker}_{self.period}"

        # Universal XBRL extraction (selector-driven)
        self.data = load_xbrl_facts(self.filing_dir)
        
        # Create fact index for efficient lookups
        self.index = FactIndex(self.data)
        
        # Initialize facts as empty - will be populated by load()
        self.facts = []
        
        # Initialize caches
        self.marketcap = None
        self.pdf_cache = {}

    def load(self):
        """
        Load the filing completely:
          - ensure filing is downloaded
          - select the correct XBRL instance
          - parse facts using extract_facts()
        """

        # Step 1 — parse XBRL structures (existing functionality)
        instance_path = find_xbrl_instance(self.filing_dir)

        if not instance_path:
            print("[!] No XBRL instance found.")
            self.facts = []
            return

        # Step 2 — extract US GAAP facts
        self.facts = extract_facts(instance_path)

    def kpi(self):
        """
        Return a KPI engine instance for advanced financial analysis.
        """
        return KPIEngine(self)

    def fact(self, tag, period=None):
        """Get fact using unified fact index."""
        return self.index.get_fact(tag, period)

    def numeric(self, tag, period=None):
        """Get numeric value using unified fact index."""
        return self.index.get_numeric(tag, period)

    def latest(self, tag):
        """Get latest fact using unified fact index."""
        return self.index.get_latest(tag)

    def get_shares_outstanding(self, year=None):
        """
        Get shares outstanding from XBRL.
        Falls back to us-gaap:CommonStockSharesOutstanding if SharesOutstanding not in FACT_MAP.
        """
        # Try canonical concept first
        shares = get_concept_value("SharesOutstanding", self.facts, year)
        if shares is not None:
            return shares
        
        # Fallback: search for us-gaap:CommonStockSharesOutstanding directly
        from src.xbrl.fact_extractor import _extract_end_date_year
        for fact in self.facts:
            if "CommonStockSharesOutstanding" in fact["tag"] or "EntityCommonStockSharesOutstanding" in fact["tag"]:
                if year is not None:
                    fact_year = _extract_end_date_year(fact)
                    if fact_year == year:
                        try:
                            return float(fact["value"])
                        except:
                            continue
                else:
                    try:
                        return float(fact["value"])
                    except:
                        continue
        
        return None
    
    def load_marketcap(self):
        """Load market cap using yfinance (external data)."""
        try:
            import yfinance as yf
            ticker_obj = yf.Ticker(self.ticker.upper())
            info = ticker_obj.info
            market_cap = info.get("marketCap")
            if market_cap:
                self.marketcap = float(market_cap)
            else:
                self.marketcap = None
        except Exception as e:
            self.marketcap = None
    
    def get_marketcap(self, year=None):
        """Get market cap (cached or load from yfinance)."""
        if self.marketcap is not None:
            return self.marketcap
        self.load_marketcap()
        return self.marketcap
    
    def get_price(self):
        """Compute price = MarketCap / SharesOutstanding."""
        marketcap = self.get_marketcap()
        shares = self.get_shares_outstanding()
        if marketcap is None or shares is None or shares == 0:
            return None
        return marketcap / shares
    
    def get_enterprise_value(self, year=None):
        """
        Compute Enterprise Value = MarketCap + TotalDebt - CashAndShortTermInvestments.
        """
        marketcap = self.get_marketcap()
        if marketcap is None:
            return None
        
        # Get TotalDebt (approximate as TotalLiabilities)
        total_debt = get_concept_value("TotalLiabilities", self.facts, year)
        
        # Get CashAndShortTermInvestments (try multiple concepts)
        cash = get_concept_value("CashAndShortTermInvestments", self.facts, year)
        if cash is None:
            # Fallback to Cash and Cash Equivalents
            cash = get_concept_value("Cash", self.facts, year)
        
        ev = marketcap
        if total_debt is not None:
            ev += total_debt
        if cash is not None:
            ev -= cash
        
        return ev

    def unit_economics(self):
        """
        Compute deterministic unit economics using the identity engine.
        """
        from .unit_economics import compute_unit_economics
        return compute_unit_economics(self)
    
    def get(self, concept, year=None):
        """
        Retrieve a canonical financial concept using dynamic resolution.
        Automatically falls back to PDF extraction if XBRL is missing or invalid.
        """
        canonical = resolve(concept)

        # Handle valuation concepts
        if canonical == "MarketCap":
            return self.get_marketcap()
        if canonical == "Price":
            return self.get_price()
        if canonical == "EnterpriseValue":
            return self.get_enterprise_value(year)
        if canonical == "SharesOutstanding":
            return self.get_shares_outstanding(year)
        
        # 1. Try XBRL
        val = get_concept_value(canonical, self.facts, year)

        # 2. PDF Fallback Logic
        # Find PDF
        pdf_files = glob.glob(os.path.join(self.filing_dir, "*.pdf"))
        if not pdf_files:
            return val
            
        pdf_path = pdf_files[0]
        
        # Check PDF cache
        if canonical not in self.pdf_cache:
            # Extract fresh data
            self.pdf_cache[canonical] = extract_from_pdf(pdf_path, canonical)
            
        pdf_data = self.pdf_cache[canonical]
        if not pdf_data:
            return val
            
        # Determine target PDF value
        pdf_val = None
        if year is not None:
            pdf_val = pdf_data.get(year)
        else:
            # Default to latest year in PDF
            try:
                max_y = max(pdf_data.keys())
                pdf_val = pdf_data[max_y]
            except ValueError:
                pass
                
        # 3. Comparison / Override
        if pdf_val is not None:
            if val is None:
                print(f"  [PDF Fallback] Missing XBRL for {concept}, used PDF: {pdf_val}")
                return pdf_val
            
            if val != 0 and pdf_val != 0:
                diff = abs((val - pdf_val) / pdf_val)
                if diff > 0.7:
                    print(f"  [PDF Fallback] XBRL {val} vs PDF {pdf_val} (diff {diff:.1%}). Overriding.")
                    return pdf_val

        return val

    def series(self, concept, years=None, kind="raw"):
        """
        Retrieve full-year time series for a concept.
        
        kind:
            - 'raw'   : [(year, value), ...]
            - 'yoy'   : [(year, yoy_growth), ...]
            - 'cagr'  : single float
            - 'trend' : single float (z-score-like)
            - 'ttm'   : trailing twelve-month approx
        
        years:
            int or list — filters the returned periods
        """
        base = build_concept_series(concept, self.facts)

        if not base:
            return None

        # Optional filtering
        if years is not None:
            if isinstance(years, int):
                base = [p for p in base if p[0] == years]
            else:
                base = [p for p in base if p[0] in years]

        if not base:
            return None

        # Apply transformation
        if kind == "raw":
            return base
        if kind == "yoy":
            return _compute_yoy(base)
        if kind == "cagr":
            return _compute_cagr(base)
        if kind == "trend":
            return _compute_trend(base)
        if kind == "ttm":
            return _compute_ttm(base)

        raise ValueError(f"Unknown series kind '{kind}'")

    def __getitem__(self, key):
        if isinstance(key, tuple):
            tag, period = key
            return self.fact(tag, period)
        return self.fact(key, None)
