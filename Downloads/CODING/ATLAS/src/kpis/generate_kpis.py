"""
Generate standardized KPIs from an Atlas instance.
"""

from __future__ import annotations

from src.extraction.semantic_resolver import (
    resolve_revenue,
    resolve_operating_income,
    resolve_net_income,
    resolve_gross_profit,
    resolve_assets,
    resolve_liabilities,
    resolve_equity,
    resolve_eps_basic,
    resolve_eps_diluted,
)
from src.xbrl.fact_index import get_numeric
from src.marketdata.market_cap import get_market_cap


def _numeric(fact):
    if fact is None:
        return None
    return fact.get("numeric_value")


def generate_kpis(atlas):
    """
    Generate a standardized KPI dictionary from an Atlas instance.
    
    Uses the unified fact index from atlas.index for efficient lookups.
    """
    revenue = _numeric(resolve_revenue(atlas.data))
    operating_income = _numeric(resolve_operating_income(atlas.data))
    net_income = _numeric(resolve_net_income(atlas.data))
    gross_profit = _numeric(resolve_gross_profit(atlas.data))

    eps_basic = _numeric(resolve_eps_basic(atlas.data))
    eps_diluted = _numeric(resolve_eps_diluted(atlas.data))

    assets = _numeric(resolve_assets(atlas.data))
    liabilities = _numeric(resolve_liabilities(atlas.data))
    equity = _numeric(resolve_equity(atlas.data))

    # Use unified fact index for lookups
    op_cash = atlas.index.get_numeric(
        "us-gaap:NetCashProvidedByUsedInOperatingActivities", "FY2025"
    )
    capex = atlas.index.get_numeric(
        "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment", "FY2025"
    )
    free_cash_flow = op_cash - capex if op_cash is not None and capex is not None else None

    depreciation = atlas.index.get_numeric(
        "us-gaap:DepreciationDepletionAndAmortization"
    )
    amortization = atlas.index.get_numeric(
        "us-gaap:AmortizationOfIntangibleAssets"
    )
    if operating_income is not None:
        ebitda = (
            operating_income
            + (depreciation or 0)
            + (amortization or 0)
        )
    else:
        ebitda = None

    roe = net_income / equity if net_income is not None and equity else None
    roa = net_income / assets if net_income is not None and assets else None

    operating_margin = (
        operating_income / revenue if operating_income is not None and revenue else None
    )
    net_margin = net_income / revenue if net_income is not None and revenue else None

    market_cap = get_market_cap(atlas.ticker)
    fcf_yield = (
        free_cash_flow / market_cap if free_cash_flow is not None and market_cap else None
    )

    return {
        "revenue": revenue,
        "operating_income": operating_income,
        "net_income": net_income,
        "gross_profit": gross_profit,
        "eps_basic": eps_basic,
        "eps_diluted": eps_diluted,
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "free_cash_flow": free_cash_flow,
        "ebitda": ebitda,
        "roe": roe,
        "roa": roa,
        "operating_margin": operating_margin,
        "net_margin": net_margin,
        "market_cap": market_cap,
        "fcf_yield": fcf_yield,
    }
