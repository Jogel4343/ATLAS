"""
Master Deterministic Unit Economics Module.
Orchestrates volume drivers, cost classification, and identity solving.
"""

from typing import Dict, Any, Optional
from .volume_drivers import resolve_all_segments
from .variable_cost_classifier import classify_cost
from .identity_solver import solve_missing_values, enforce_all, IdentityError
from .cost_structure import CostStructureEngine
from src.xbrl.concept_resolver import resolve

def compute_unit_economics(atlas) -> Dict[str, Any]:
    """
    Compute deterministic unit economics for the entity loaded in Atlas.
    """
    # Ensure cost structure engine is attached
    if not hasattr(atlas, "cost_structure"):
        atlas.cost_structure = CostStructureEngine(atlas)

    # 1. Resolve volume driver
    drivers_map = resolve_all_segments(atlas)
    volume_driver_name = drivers_map.get("consolidated")
    
    # Get current year facts
    # We use the latest year available in the filing
    # Assuming atlas.facts is populated
    
    # Build base inputs dictionary (mapping Atlas concepts to Identity symbols)
    inputs = {}
    
    # Basic P&L
    inputs["Revenue"] = atlas.get(resolve("Revenue"))
    inputs["OperatingIncome"] = atlas.get(resolve("OperatingIncome"))
    inputs["TaxRate"] = 0.21 # Standard US Corp Tax Rate assumption if not explicit
    # Ideally we compute effective tax rate: TaxProvision / PreTaxIncome
    tax_provision = atlas.get(resolve("IncomeTaxExpenseBenefit"))
    pre_tax = atlas.get(resolve("IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"))
    if tax_provision and pre_tax and pre_tax > 0:
        inputs["TaxRate"] = max(0.0, min(tax_provision / pre_tax, 0.5))
        
    # Volume
    if volume_driver_name:
        inputs["VolumeDriver"] = atlas.get(resolve(volume_driver_name))
        
    # 3. Classify variable vs fixed cost buckets
    # We need to iterate over all operating expenses and COGS
    # Atlas might not have granular line items indexed easily as a list.
    # We will approximate COGS_variable using the 'CostOfRevenue' concept if available,
    # or sum up known variable components if we had granular ledger data.
    # For this implementation, we assume CostOfRevenue is primarily variable (classic unit econ).
    
    cogs = atlas.get(resolve("CostOfRevenue"))
    if cogs is None:
        cogs = atlas.get(resolve("CostOfGoodsAndServicesSold")) # Alternative tag
        
    if cogs:
        inputs["COGS_variable"] = cogs * 1.0 # Assume 100% variable for now per classifier default
    else:
        inputs["COGS_variable"] = 0.0
        
    # 4. Apply contribution margin identity inputs
    # (Solved in step 8 via solve_missing_values)
    
    # 5. Solve CAC identity
    # We need SalesMarketing and RetentionMarketing
    # Often only "SellingAndMarketingExpense" is available
    sales_marketing = atlas.get(resolve("SellingAndMarketingExpense"))
    if sales_marketing:
        # Crude assumption: 80% acquisition, 20% retention if not broken out
        inputs["SalesMarketing"] = sales_marketing * 0.8
        inputs["RetentionMarketing"] = sales_marketing * 0.2
    else:
        # Try SG&A proxy?
        sga = atlas.get(resolve("SellingGeneralAndAdministrative"))
        if sga:
            inputs["SalesMarketing"] = sga * 0.4 # High level proxy
            inputs["RetentionMarketing"] = sga * 0.1
            
    # Gross New Customers?
    # Hard to get from XBRL usually. We check if "GrossNewCustomers" or similar exists (custom tag)
    # Or derive from delta volume if churn is known.
    # For now, we leave it None and let solver try (it will likely fail to solve CAC without it).
    
    # 6. Compute Reinvestment Rate inputs
    inputs["Capex"] = atlas.get(resolve("CapitalExpenditures"))
    inputs["RnD"] = atlas.get(resolve("ResearchAndDevelopmentExpense"))
    if inputs["RnD"] is None:
        inputs["RnD"] = 0.0
        
    # Delta Working Capital
    wc_curr = atlas.get(resolve("WorkingCapital"))
    # We need previous year WC. Atlas.get(concept, year) is robust?
    # We need to know the current year.
    # Let's try to find the latest year in facts.
    from src.xbrl.fact_extractor import _extract_end_date_year
    years = sorted(list(set(_extract_end_date_year(f) for f in atlas.facts if _extract_end_date_year(f))))
    if years:
        latest_year = years[-1]
        prev_year = latest_year - 1
        inputs["DeltaWorkingCapital"] = 0.0
        
        wc_curr = atlas.get(resolve("WorkingCapital"), year=latest_year)
        wc_prev = atlas.get(resolve("WorkingCapital"), year=prev_year)
        
        if wc_curr is not None and wc_prev is not None:
            inputs["DeltaWorkingCapital"] = wc_curr - wc_prev
            
    # Maintenance Capex (Option B: Depreciation - ΔPPE)
    depr = atlas.get(resolve("DepreciationAmortization"))
    ppe_curr = atlas.get(resolve("PropertyPlantAndEquipmentNet"))
    ppe_prev = atlas.get(resolve("PropertyPlantAndEquipmentNet"), year=prev_year) if years else None

    maintenance_capex = None
    if depr is not None and ppe_curr is not None and ppe_prev is not None:
        maintenance_capex = max(0.0, depr - (ppe_curr - ppe_prev))

    inputs["MaintenanceCapex"] = maintenance_capex

    # 7. Compute ROIC decomposition inputs
    inputs["PPE"] = atlas.get(resolve("PropertyPlantAndEquipmentNet"))
    inputs["Goodwill"] = atlas.get(resolve("Goodwill"))
    inputs["AcquiredIntangibles"] = atlas.get(resolve("IntangibleAssetsNetExcludingGoodwill"))
    
    # Net Working Capital (Current Assets - Current Liabs - Cash?)
    # Simplified: Use WorkingCapital - Cash
    wc = atlas.get(resolve("WorkingCapital"))
    cash = atlas.get(resolve("CashAndCashEquivalents"))
    if wc and cash:
        inputs["NetWorkingCapital"] = wc - cash
    else:
        inputs["NetWorkingCapital"] = 0.0
        
    # Fill Nones with 0.0 for additive fields to allow solving
    for k in ["PPE", "Goodwill", "AcquiredIntangibles", "Capex", "RnD", "DeltaWorkingCapital"]:
        if inputs.get(k) is None:
            inputs[k] = 0.0

    # 8. Validate and Solve
    try:
        solved_model = solve_missing_values(inputs)
        # enforce_all(solved_model) # Optional: Enforce strictness. Might fail if data is messy.
    except Exception as e:
        print(f"Warning: Unit economics solving incomplete: {e}")
        solved_model = inputs

    # --- Compute true NOPAT (after maintenance capex) ---
    operating_income = solved_model.get("OperatingIncome") or inputs.get("OperatingIncome")
    tax_rate = solved_model.get("TaxRate") or inputs.get("TaxRate")
    nopat_true = None
    if operating_income is not None:
        nopat_true = operating_income * (1 - (tax_rate or 0.21))
        if maintenance_capex is not None:
            nopat_true -= maintenance_capex

    # Store for downstream use (EPV, True ROIC, etc.)
    solved_model["NOPAT_True"] = nopat_true

    # Compute cost structure
    cs = atlas.cost_structure.compute_all()

    # 9. Store Result
    result = {
        "consolidated": {
            "volume_driver": volume_driver_name,
            "revenue_per_unit": solved_model.get("RevenuePerUnit"),
            "variable_cost_per_unit": solved_model.get("VariableCostPerUnit"),
            "contribution_margin_per_unit": solved_model.get("ContributionMarginPerUnit"),
            "fixed_costs": None, # Todo: calc fixed costs
            "cac": solved_model.get("CAC"),
            "churn_rate": solved_model.get("ChurnRate"),
            "roic": solved_model.get("ROIC"),
            "reinvestment_rate": solved_model.get("ReinvestmentRate"),
            
            "variable_cost_share": cs["variable_shares"]["latest"],
            "fixed_cost_share": (
                1 - cs["variable_shares"]["latest"]
                if cs["variable_shares"]["latest"] is not None
                else None
            ),
            "marginal_cost": cs["marginal_cost"]["latest"],
            "break_even_revenue": cs["break_even_revenue"],
            "contribution_margin_true": cs["contribution_margin"]["latest"],

            "nopat_true": nopat_true,
            "maintenance_capex": maintenance_capex,

            # Raw model for debugging
            "_model": solved_model,
        }
    }
    
    return result
