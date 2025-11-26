"""
KPI Engine for ATLAS.

Computes derived financial metrics from canonical concepts.
"""

import statistics
from src.xbrl.fact_extractor import _extract_end_date_year
from src.atlas.cost_structure import CostStructureEngine

def _compute_yoy_growth(series):
    """Compute year-over-year growth percentages."""
    if len(series) < 2:
        return []
    out = []
    for i in range(1, len(series)):
        y_prev, v_prev = series[i-1]
        y_curr, v_curr = series[i]
        if v_prev is None or v_prev == 0:
            out.append((y_curr, None))
        else:
            growth = (v_curr - v_prev) / v_prev * 100  # as percentage
            out.append((y_curr, growth))
    return out


def _compute_3yr_cagr(series):
    """Compute 3-year CAGR from the last 3 years of data."""
    if len(series) < 3:
        return None
    # Get last 3 years
    last_3 = series[-3:]
    y0, v0 = last_3[0]
    y1, v1 = last_3[-1]
    if v0 <= 0:
        return None
    years = y1 - y0
    if years <= 0:
        return None
    return ((v1 / v0) ** (1 / years) - 1) * 100  # as percentage


def _compute_roic(nopat, invested_capital):
    """Compute ROIC: NOPAT / Invested Capital."""
    if invested_capital is None or invested_capital == 0:
        return None
    if nopat is None:
        return None
    return (nopat / invested_capital) * 100  # as percentage


def _compute_reinvestment_rate(fcf, nopat):
    """Compute Reinvestment Rate: (FCF - NOPAT) / NOPAT or similar."""
    if nopat is None or nopat == 0:
        return None
    if fcf is None:
        return None
    # Reinvestment = NOPAT - FCF (simplified)
    reinvestment = nopat - fcf
    return (reinvestment / nopat) * 100  # as percentage


def _compute_fcf_margin(fcf, revenue):
    """Compute FCF Margin: FCF / Revenue."""
    if revenue is None or revenue == 0:
        return None
    if fcf is None:
        return None
    return (fcf / revenue) * 100  # as percentage


def _compute_revenue_growth_stability(series):
    """Compute standard deviation of YoY revenue growth."""
    yoy = _compute_yoy_growth(series)
    if len(yoy) < 2:
        return None
    growth_rates = [g for _, g in yoy if g is not None]
    if len(growth_rates) < 2:
        return None
    return statistics.stdev(growth_rates)


def _compute_operating_leverage(operating_income_series, revenue_series):
    """Compute Operating Leverage: %ΔOperatingIncome / %ΔRevenue."""
    if len(operating_income_series) < 2 or len(revenue_series) < 2:
        return None
    
    # Get YoY changes for both
    oi_yoy = _compute_yoy_growth(operating_income_series)
    rev_yoy = _compute_yoy_growth(revenue_series)
    
    if not oi_yoy or not rev_yoy:
        return None
    
    # Match by year and compute leverage
    oi_dict = {y: g for y, g in oi_yoy}
    rev_dict = {y: g for y, g in rev_yoy}
    
    leverages = []
    for year in oi_dict:
        if year in rev_dict:
            oi_growth = oi_dict[year]
            rev_growth = rev_dict[year]
            if rev_growth is not None and rev_growth != 0 and oi_growth is not None:
                leverage = oi_growth / rev_growth
                leverages.append(leverage)
    
    if not leverages:
        return None
    
    # Return average operating leverage
    return statistics.mean(leverages)


def _compute_capex_intensity(capex, revenue):
    """Compute Capex Intensity: Capex / Revenue."""
    if revenue is None or revenue == 0:
        return None
    if capex is None:
        return None
    return (abs(capex) / revenue) * 100  # as percentage (use abs for capex which is negative)


def _compute_fcf_yield(fcf, marketcap):
    """Compute FCF Yield: (FCF / MarketCap) * 100."""
    if fcf is None or marketcap is None or marketcap == 0:
        return None
    return (fcf / marketcap) * 100


def _compute_earnings_yield(ni, marketcap):
    """Compute Earnings Yield: (NetIncome / MarketCap) * 100."""
    if ni is None or marketcap is None or marketcap == 0:
        return None
    return (ni / marketcap) * 100


def _compute_operating_margin(operating_income, revenue):
    """Compute Operating Margin: (OperatingIncome / Revenue) * 100."""
    if operating_income is None or revenue is None or revenue == 0:
        return None
    return (operating_income / revenue) * 100


def _compute_net_margin(net_income, revenue):
    """Compute Net Margin: (NetIncome / Revenue) * 100."""
    if net_income is None or revenue is None or revenue == 0:
        return None
    return (net_income / revenue) * 100


def _compute_gross_margin(gross_profit, revenue):
    """Compute Gross Margin: (GrossProfit / Revenue) * 100."""
    if gross_profit is None or revenue is None or revenue == 0:
        return None
    return (gross_profit / revenue) * 100


def _compute_incremental_margin(opinc_yoy, rev_yoy):
    """Compute Incremental Margin as average of ΔOperatingIncome% / ΔRevenue%."""
    if not opinc_yoy or not rev_yoy:
        return None
    opinc_dict = dict(opinc_yoy)
    rev_dict = dict(rev_yoy)
    margins = []
    for year in opinc_dict:
        if year in rev_dict:
            opinc_growth = opinc_dict[year]
            rev_growth = rev_dict[year]
            if opinc_growth is not None and rev_growth is not None and rev_growth != 0:
                margins.append(opinc_growth / rev_growth)
    if not margins:
        return None
    return statistics.mean(margins)


def _compute_fcf_conversion(fcf, net_income):
    """Compute FCF Conversion: FCF / NetIncome."""
    if fcf is None or net_income is None or net_income == 0:
        return None
    return fcf / net_income


def _compute_leverage_ratio(liabilities, equity):
    """Compute Leverage Ratio: TotalLiabilities / ShareholdersEquity."""
    if liabilities is None or equity is None or equity == 0:
        return None
    return liabilities / equity


def _compute_debt_to_fcf(debt, fcf):
    """Compute Debt to FCF: TotalLiabilities / FreeCashFlow."""
    if debt is None or fcf is None or fcf == 0:
        return None
    return debt / fcf


def _compute_return_on_equity(net_income, equity):
    """Compute Return on Equity: NetIncome / ShareholdersEquity."""
    if net_income is None or equity is None or equity == 0:
        return None
    return net_income / equity


def _compute_return_on_assets(net_income, assets):
    """Compute Return on Assets: NetIncome / TotalAssets."""
    if net_income is None or assets is None or assets == 0:
        return None
    return net_income / assets


def _compute_ebit_growth(series):
    """Compute EBIT Growth as YoY growth of OperatingIncome."""
    return _compute_yoy_growth(series)


def _compute_ebitda_multiple(ebitda, enterprise_value):
    """Compute EBITDA Multiple: EnterpriseValue / EBITDA."""
    if ebitda is None or enterprise_value is None or ebitda == 0:
        return None
    return enterprise_value / ebitda


def _compute_reinvestment_rate_for_year(atlas, year):
    """Compute Reinvestment Rate for a specific year using CAPEX + ΔWorkingCapital / NOPAT."""
    capex = atlas.get("CapitalExpenditures", year=year)
    nopat = atlas.get("OperatingIncome", year=year)
    if nopat is None or nopat == 0:
        return None
    wc_curr = atlas.get("WorkingCapital", year=year)
    wc_prev = atlas.get("WorkingCapital", year=year-1)
    if capex is None:
        return None
    delta_wc = None
    if wc_curr is not None and wc_prev is not None:
        delta_wc = wc_curr - wc_prev
    reinvestment = capex
    if delta_wc is not None:
        reinvestment += delta_wc
    return (reinvestment / nopat) * 100


def _compute_capex_intensity(capex, revenue):
    """Compute Capex Intensity: Capex / Revenue."""
    if revenue is None or revenue == 0:
        return None
    if capex is None:
        return None
    return (abs(capex) / revenue) * 100  # as percentage (use abs for capex which is negative)


def _compute_revenue_growth_series(atlas):
    """Compute Revenue_Growth as a series."""
    revenue_series = atlas.series("Revenue", kind="raw")
    if not revenue_series:
        return None
    return _compute_yoy_growth(revenue_series)


def _compute_roic_for_year(atlas, year):
    """Compute ROIC for a specific year."""
    # NOPAT approximation: OperatingIncome * (1 - tax_rate)
    # For simplicity, use OperatingIncome as NOPAT approximation
    nopat = atlas.get("OperatingIncome", year=year)
    
    # Invested Capital = ShareholdersEquity + TotalLiabilities (simplified)
    equity = atlas.get("ShareholdersEquity", year=year)
    liabilities = atlas.get("TotalLiabilities", year=year)
    invested_capital = None
    if equity is not None and liabilities is not None:
        invested_capital = equity + liabilities
    elif equity is not None:
        invested_capital = equity
    elif liabilities is not None:
        invested_capital = liabilities
    
    return _compute_roic(nopat, invested_capital)


def _compute_reinvestment_rate_for_year(atlas, year):
    """Compute Reinvestment Rate for a specific year."""
    fcf = atlas.get("FreeCashFlow", year=year)
    # NOPAT approximation: OperatingIncome
    nopat = atlas.get("OperatingIncome", year=year)
    return _compute_reinvestment_rate(fcf, nopat)


def _compute_fcf_margin_for_year(atlas, year):
    """Compute FCF Margin for a specific year."""
    fcf = atlas.get("FreeCashFlow", year=year)
    revenue = atlas.get("Revenue", year=year)
    return _compute_fcf_margin(fcf, revenue)


def _compute_capex_intensity_for_year(atlas, year):
    """Compute Capex Intensity for a specific year."""
    capex = atlas.get("CapitalExpenditures", year=year)
    revenue = atlas.get("Revenue", year=year)
    return _compute_capex_intensity(capex, revenue)

# --- Unit Economics Helpers ---
def _get_unit_metric(atlas, key):
    """Retrieve a metric from the deterministic unit economics engine."""
    try:
        ue = atlas.unit_economics()
        return ue["consolidated"].get(key)
    except:
        return None

# KPI Definitions Registry
KPI_DEFINITIONS = {
    "Revenue_Growth": {
        "requires": ["Revenue"],
        "fn": _compute_revenue_growth_series,
        "is_series": True
    },
    "Revenue_Growth_3Y_CAGR": {
        "requires": ["Revenue"],
        "fn": lambda atlas: _compute_3yr_cagr(atlas.series("Revenue", kind="raw")),
        "is_series": False
    },
    "Revenue_Growth_Stability": {
        "requires": ["Revenue"],
        "fn": lambda atlas: _compute_revenue_growth_stability(atlas.series("Revenue", kind="raw")),
        "is_series": False
    },
    "ROIC": {
        "requires": ["OperatingIncome", "ShareholdersEquity", "TotalLiabilities"],
        "fn": _compute_roic_for_year,
        "is_series": False
    },
    "ReinvestmentRate": {
        "requires": ["CapitalExpenditures", "WorkingCapital", "OperatingIncome"],
        "fn": _compute_reinvestment_rate_for_year,
        "is_series": False
    },
    "FCF_Margin": {
        "requires": ["FreeCashFlow", "Revenue"],
        "fn": _compute_fcf_margin_for_year,
        "is_series": False
    },
    "Operating_Leverage": {
        "requires": ["OperatingIncome", "Revenue"],
        "fn": lambda atlas: _compute_operating_leverage(
            atlas.series("OperatingIncome", kind="raw"),
            atlas.series("Revenue", kind="raw")
        ),
        "is_series": False
    },
    "Capex_Intensity": {
        "requires": ["CapitalExpenditures", "Revenue"],
        "fn": _compute_capex_intensity_for_year,
        "is_series": False
    },
    "FCF_Yield": {
        "requires": ["FreeCashFlow", "MarketCap"],
        "fn": lambda atlas, year: _compute_fcf_yield(atlas.get("FreeCashFlow", year=year), atlas.get("MarketCap")),
        "is_series": False
    },
    "Earnings_Yield": {
        "requires": ["NetIncome", "MarketCap"],
        "fn": lambda atlas, year: _compute_earnings_yield(atlas.get("NetIncome", year=year), atlas.get("MarketCap")),
        "is_series": False
    },
    "Operating_Margin": {
        "requires": ["OperatingIncome", "Revenue"],
        "fn": lambda atlas, year: _compute_operating_margin(atlas.get("OperatingIncome", year=year), atlas.get("Revenue", year=year)),
        "is_series": False
    },
    "Net_Margin": {
        "requires": ["NetIncome", "Revenue"],
        "fn": lambda atlas, year: _compute_net_margin(atlas.get("NetIncome", year=year), atlas.get("Revenue", year=year)),
        "is_series": False
    },
    "Gross_Margin": {
        "requires": ["GrossProfit", "Revenue"],
        "fn": lambda atlas, year: _compute_gross_margin(atlas.get("GrossProfit", year=year), atlas.get("Revenue", year=year)),
        "is_series": False
    },
    "Incremental_Margin": {
        "requires": ["OperatingIncome", "Revenue"],
        "fn": lambda atlas: _compute_incremental_margin(
            _compute_yoy_growth(atlas.series("OperatingIncome", kind="raw")),
            _compute_yoy_growth(atlas.series("Revenue", kind="raw"))
        ),
        "is_series": False
    },
    "FCF_Conversion": {
        "requires": ["FreeCashFlow", "NetIncome"],
        "fn": lambda atlas, year: _compute_fcf_conversion(atlas.get("FreeCashFlow", year=year), atlas.get("NetIncome", year=year)),
        "is_series": False
    },
    "Leverage_Ratio": {
        "requires": ["TotalLiabilities", "ShareholdersEquity"],
        "fn": lambda atlas, year: _compute_leverage_ratio(atlas.get("TotalLiabilities", year=year), atlas.get("ShareholdersEquity", year=year)),
        "is_series": False
    },
    "Debt_to_FCF": {
        "requires": ["TotalLiabilities", "FreeCashFlow"],
        "fn": lambda atlas, year: _compute_debt_to_fcf(atlas.get("TotalLiabilities", year=year), atlas.get("FreeCashFlow", year=year)),
        "is_series": False
    },
    "ROE": {
        "requires": ["NetIncome", "ShareholdersEquity"],
        "fn": lambda atlas, year: _compute_return_on_equity(atlas.get("NetIncome", year=year), atlas.get("ShareholdersEquity", year=year)),
        "is_series": False
    },
    "ROA": {
        "requires": ["NetIncome", "TotalAssets"],
        "fn": lambda atlas, year: _compute_return_on_assets(atlas.get("NetIncome", year=year), atlas.get("TotalAssets", year=year)),
        "is_series": False
    },
    "EBIT_Growth": {
        "requires": ["OperatingIncome"],
        "fn": lambda atlas: _compute_ebit_growth(atlas.series("OperatingIncome", kind="raw")),
        "is_series": False
    },
    "EBITDA_Multiple": {
        "requires": ["EBITDA", "EnterpriseValue"],
        "fn": lambda atlas, year: _compute_ebitda_multiple(atlas.get("EBITDA", year=year), atlas.get("EnterpriseValue", year=year)),
        "is_series": False
    },
    "EV_EBIT": {
        "requires": ["EnterpriseValue", "OperatingIncome"],
        "fn": lambda atlas, year: (
            atlas.get("EnterpriseValue", year=year) / atlas.get("OperatingIncome", year=year)
            if atlas.get("OperatingIncome", year=year) and atlas.get("OperatingIncome", year=year) != 0
            else None
        ),
        "is_series": False
    },
    "EV_EBITDA": {
        "requires": ["EnterpriseValue", "EBITDA"],
        "fn": lambda atlas, year: (
            atlas.get("EnterpriseValue", year=year) / atlas.get("EBITDA", year=year)
            if atlas.get("EBITDA", year=year) and atlas.get("EBITDA", year=year) != 0
            else None
        ),
        "is_series": False
    },
    "EV_FCF": {
        "requires": ["EnterpriseValue", "FreeCashFlow"],
        "fn": lambda atlas, year: (
            atlas.get("EnterpriseValue", year=year) / atlas.get("FreeCashFlow", year=year)
            if atlas.get("FreeCashFlow", year=year) and atlas.get("FreeCashFlow", year=year) != 0
            else None
        ),
        "is_series": False
    },
    "PE_Ratio": {
        "requires": ["Price", "EPSBasic"],
        "fn": lambda atlas, year: (
            atlas.get("Price") / atlas.get("EPSBasic", year=year)
            if atlas.get("EPSBasic", year=year) and atlas.get("EPSBasic", year=year) != 0
            else None
        ),
        "is_series": False
    },
    "PS_Ratio": {
        "requires": ["MarketCap", "Revenue"],
        "fn": lambda atlas, year: (
            atlas.get("MarketCap") / atlas.get("Revenue", year=year)
            if atlas.get("Revenue", year=year) and atlas.get("Revenue", year=year) != 0
            else None
        ),
        "is_series": False
    },
    # --- Unit Economics KPIs ---
    "RevenuePerUnit": {
        "requires": [],
        "fn": lambda atlas: _get_unit_metric(atlas, "revenue_per_unit"),
        "is_series": False
    },
    "COGSPerUnit": {
        "requires": [],
        "fn": lambda atlas: _get_unit_metric(atlas, "variable_cost_per_unit"), # approx for COGS/Unit if mainly variable
        "is_series": False
    },
    "VariableCostRatio": {
        "requires": [],
        "fn": lambda atlas: (
            _get_unit_metric(atlas, "variable_cost_per_unit") / _get_unit_metric(atlas, "revenue_per_unit")
            if _get_unit_metric(atlas, "revenue_per_unit") else None
        ),
        "is_series": False
    },
    "ContributionMargin": {
        "requires": [],
        "fn": lambda atlas: _get_unit_metric(atlas, "contribution_margin_per_unit"),
        "is_series": False
    },
    "CAC": {
        "requires": [],
        "fn": lambda atlas: _get_unit_metric(atlas, "cac"),
        "is_series": False
    },
    "ChurnRate": {
        "requires": [],
        "fn": lambda atlas: _get_unit_metric(atlas, "churn_rate"),
        "is_series": False
    },
    "ROIC_True": {
        "requires": [],
        "fn": lambda atlas: _get_unit_metric(atlas, "roic"),
        "is_series": False
    },
    "ReinvestmentRate_Deterministic": {
        "requires": [],
        "fn": lambda atlas: _get_unit_metric(atlas, "reinvestment_rate"),
        "is_series": False
    },
    "VariableCostShare": {
        "requires": [],
        "fn": lambda atlas: atlas.cost_structure.compute_all()["variable_shares"]["latest"],
        "is_series": False
    },
    "FixedCostShare": {
        "requires": [],
        "fn": lambda atlas: (
            1 - atlas.cost_structure.compute_all()["variable_shares"]["latest"]
            if atlas.cost_structure.compute_all()["variable_shares"]["latest"] is not None
            else None
        ),
        "is_series": False
    },
    "MarginalCost": {
        "requires": [],
        "fn": lambda atlas: atlas.cost_structure.compute_all()["marginal_cost"]["latest"],
        "is_series": False
    },
    "BreakEvenRevenue": {
        "requires": [],
        "fn": lambda atlas: atlas.cost_structure.compute_all()["break_even_revenue"],
        "is_series": False
    },
    "ContributionMargin_True": {
        "requires": [],
        "fn": lambda atlas: atlas.cost_structure.compute_all()["contribution_margin"]["latest"],
        "is_series": False
    },
    "NOPAT_True": {
        "requires": [],
        "fn": lambda atlas: atlas.unit_economics()["consolidated"].get("nopat_true"),
        "is_series": False
    },
    "ROIC_True_Improved": {
        "requires": [],
        "fn": lambda atlas: (
            lambda ue=atlas.unit_economics()["consolidated"]: (
                (ue["nopat_true"] / (
                    (atlas.get("PropertyPlantAndEquipmentNet") or 0) +
                    (atlas.get("WorkingCapital") or 0) -
                    (atlas.get("CashAndCashEquivalents") or 0) +
                    (atlas.get("Goodwill") or 0) +
                    (atlas.get("IntangibleAssetsNetExcludingGoodwill") or 0)
                )) * 100 if ue["nopat_true"] is not None else None
            )()
        ),
        "is_series": False
    },
    "ReinvestmentRate_True": {
        "requires": [],
        "fn": lambda atlas: (
            lambda ue=atlas.unit_economics()["consolidated"]: (
                (
                    ((ue["maintenance_capex"] or 0)
                    + (ue["_model"].get("DeltaWorkingCapital") or 0)
                    + (ue["_model"].get("RnD") or 0))
                / ue["nopat_true"]) * 100
                if ue["nopat_true"] not in (None, 0)
                else None
            )()
        ),
        "is_series": False
    },
    "EPV": {
        "requires": [],
        "fn": lambda atlas: (
            lambda ue=atlas.unit_economics()["consolidated"], w=atlas.get("WACC") or 0.08: (
                ue["nopat_true"] / w if (ue["nopat_true"] and w) else None
            )
        )(),
        "is_series": False
    },
    "EPV_Per_Share": {
        "requires": [],
        "fn": lambda atlas: (
            lambda epv=(
                lambda ue=atlas.unit_economics()["consolidated"], w=atlas.get("WACC") or 0.08:
                    ue["nopat_true"] / w if (ue["nopat_true"] and w) else None
            )(),
            shares=atlas.get("SharesOutstanding")
            : (epv / shares if (epv and shares) else None)
        )(),
        "is_series": False
    },
}


class KPIEngine:
    """Engine for computing derived financial KPIs from Atlas data."""
    
    def __init__(self, atlas):
        self.atlas = atlas
        self.facts = atlas.facts
        
        # Ensure cost structure engine is attached (fulfill "Inside Atlas.__init__" requirement)
        if not hasattr(self.atlas, "cost_structure"):
            self.atlas.cost_structure = CostStructureEngine(self.atlas)
    
    def latest_all(self):
        """
        Return {metric: latest_value} for all KPI_DEFINITIONS.
        """
        out = {}
        for name in KPI_DEFINITIONS:
            try:
                out[name] = self.latest(name)
            except Exception:
                out[name] = None
        return out

    def series(self, metric):
        """
        Returns multi-year time series for that metric.
        
        Returns:
            List of (year, value) tuples, or None if metric not found
        """
        if metric not in KPI_DEFINITIONS:
            return None
        
        definition = KPI_DEFINITIONS[metric]
        
        # For series-based metrics (like Revenue_Growth)
        if definition.get("is_series", False):
            try:
                result = definition["fn"](self.atlas)
                return result if result else None
            except Exception:
                return None
        
        # For year-based metrics, compute for each available year
        revenue_series = self.atlas.series("Revenue", kind="raw")
        if not revenue_series:
            return None
        
        years = [y for y, _ in revenue_series]
        series_data = []
        
        for year in years:
            value = self.compute(metric, year)
            if value is not None:
                series_data.append((year, value))
        
        return series_data if series_data else None
    
    def latest(self, metric):
        """
        Returns most recent value for a metric.
        
        Returns:
            float or None
        """
        # If metric uses unit economics, calling series might fail if logic only supports single (current) year.
        # But our _get_unit_metric wrapper calls atlas.unit_economics(), which uses the latest year.
        # So it returns the same value for all years if we iterated, or we can just call it once.
        
        definition = KPI_DEFINITIONS.get(metric)
        if definition and definition.get("is_series") is False:
            # If the function takes only atlas, it's likely a single value derived from unit economics
            # check signature or specific logic
            import inspect
            sig = inspect.signature(definition["fn"])
            if "year" not in sig.parameters and len(sig.parameters) == 1:
                 # It's a single value function (like our unit econ ones)
                 try:
                     return definition["fn"](self.atlas)
                 except:
                     pass
        
        series_data = self.series(metric)
        if not series_data:
            return None
        return series_data[-1][1]  # Return value from last (most recent) year
    
    def compute(self, metric, year):
        """
        Compute metric for specific year.
        
        Args:
            metric: KPI metric name (e.g., "Revenue_Growth", "ROIC")
            year: Year to compute for
            
        Returns:
            float or None
        """
        if metric not in KPI_DEFINITIONS:
            return None
        
        definition = KPI_DEFINITIONS[metric]
        
        # For series-based metrics, return the value for the specific year
        if definition.get("is_series", False):
            series_data = self.series(metric)
            if series_data:
                for y, value in series_data:
                    if y == year:
                        return value
            return None
        
        # Check if all required concepts are available
        for req in definition["requires"]:
            # Some metrics need series data, not single year values
            if req in ["OperatingIncome", "Revenue"]:
                series = self.atlas.series(req, kind="raw")
                if not series:
                    return None
            else:
                if self.atlas.get(req, year=year) is None:
                    # Allow fallback for unit economics which don't require granular data if we just want to try
                    if "PerUnit" in metric or "True" in metric or "Deterministic" in metric or "Contribution" in metric or "CAC" in metric or "Churn" in metric:
                        pass
                    else:
                        return None
        
        try:
            # Check function signature to determine if it needs year parameter
            import inspect
            sig = inspect.signature(definition["fn"])
            params = list(sig.parameters.keys())
            
            if len(params) >= 2 and params[1] == "year":
                # Function takes (atlas, year)
                result = definition["fn"](self.atlas, year)
            else:
                # Function takes only (atlas) - for aggregate metrics or unit econ
                result = definition["fn"](self.atlas)
            return result
        except Exception as e:
            return None
