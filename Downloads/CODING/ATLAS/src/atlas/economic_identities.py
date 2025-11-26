"""
Canonical algebraic identities for ATLAS Unit Economics Engine.
Uses SymPy for symbolic validation and solving.
"""

from sympy import symbols, Eq, solve
from typing import Dict, Optional, List

# Define symbolic variables
# Volume and Revenue
Revenue, COGS_variable, ContributionMargin, VolumeDriver = symbols('Revenue COGS_variable ContributionMargin VolumeDriver')
ContributionMarginPerUnit, RevenuePerUnit, VariableCostPerUnit = symbols('ContributionMarginPerUnit RevenuePerUnit VariableCostPerUnit')

# CAC
CAC, SalesMarketing, RetentionMarketing, GrossNewCustomers = symbols('CAC SalesMarketing RetentionMarketing GrossNewCustomers')
DeltaCustomers, ChurnedCustomers, Customers_start, ChurnRate = symbols('DeltaCustomers ChurnedCustomers Customers_start ChurnRate')

# Reinvestment
ReinvestmentRate, Capex, DeltaWorkingCapital, RnD, NOPAT = symbols('ReinvestmentRate Capex DeltaWorkingCapital RnD NOPAT')

# ROIC
ROIC, OperatingIncome, TaxRate, InvestedCapital = symbols('ROIC OperatingIncome TaxRate InvestedCapital')
PPE, NetWorkingCapital, Goodwill, AcquiredIntangibles = symbols('PPE NetWorkingCapital Goodwill AcquiredIntangibles')

# Elasticities (for constraints)
ElasticityRevenue, ElasticityNewUnits, ElasticityRevShare = symbols('ElasticityRevenue ElasticityNewUnits ElasticityRevShare')
SalesCommissions, PaymentProcessing = symbols('SalesCommissions PaymentProcessing')


# Define Identities
IDENTITIES = {
    "CAC_Identity": Eq(CAC, (SalesMarketing - RetentionMarketing) / GrossNewCustomers),
    "GrossNewCustomers_Identity": Eq(GrossNewCustomers, DeltaCustomers + ChurnedCustomers),
    "ChurnedCustomers_Identity": Eq(ChurnedCustomers, Customers_start * ChurnRate),
    
    "ContributionMargin_Identity": Eq(ContributionMarginPerUnit, (Revenue - COGS_variable) / VolumeDriver),
    "UnitRevenue_Identity": Eq(RevenuePerUnit, Revenue / VolumeDriver),
    "VariableCostPerUnit_Identity": Eq(VariableCostPerUnit, COGS_variable / VolumeDriver),
    "ContributionMargin_Check": Eq(ContributionMarginPerUnit, RevenuePerUnit - VariableCostPerUnit),

    "ReinvestmentRate_Identity": Eq(ReinvestmentRate, (Capex + DeltaWorkingCapital + RnD) / NOPAT),
    
    "NOPAT_Identity": Eq(NOPAT, OperatingIncome * (1 - TaxRate)),
    "InvestedCapital_Identity": Eq(InvestedCapital, PPE + NetWorkingCapital + Goodwill + AcquiredIntangibles),
    "ROIC_Identity": Eq(ROIC, NOPAT / InvestedCapital),
    
    # Elasticity Constraints (Linear approximations)
    "COGS_Variable_Constraint": Eq(COGS_variable, ElasticityRevenue * Revenue),
    "SalesCommissions_Constraint": Eq(SalesCommissions, ElasticityNewUnits * GrossNewCustomers),
    "PaymentProcessing_Constraint": Eq(PaymentProcessing, ElasticityRevShare * Revenue),
}

def evaluate_identity(name: str, inputs: Dict[str, float]) -> float:
    """
    Evaluate an identity to check if it holds true given inputs.
    Returns the difference (lhs - rhs). Ideally should be close to 0.
    """
    if name not in IDENTITIES:
        raise ValueError(f"Unknown identity: {name}")
    
    expr = IDENTITIES[name]
    # Substitute values
    # We need to match string keys to SymPy symbols.
    # Creating a mapping from symbol name to symbol
    sym_map = {s.name: s for s in expr.free_symbols}
    
    subs_dict = {}
    for k, v in inputs.items():
        if k in sym_map:
            subs_dict[sym_map[k]] = v
            
    # Evaluate lhs and rhs
    lhs_val = expr.lhs.evalf(subs=subs_dict)
    rhs_val = expr.rhs.evalf(subs=subs_dict)
    
    if lhs_val.is_Number and rhs_val.is_Number:
        return float(lhs_val - rhs_val)
    
    # If not fully numerical, return NaN or raise error?
    # For evaluation, we expect full inputs usually, or we can return symbolic diff
    return float(lhs_val - rhs_val) # This might fail if symbolic

def check_consistency(name: str, inputs: Dict[str, float], tolerance: float = 1e-3) -> bool:
    """
    Check if an identity is consistent within a tolerance.
    """
    try:
        diff = evaluate_identity(name, inputs)
        return abs(diff) < tolerance
    except Exception:
        return False

def solve_identity(name: str, knowns: Dict[str, float], solve_for: str) -> float:
    """
    Solve for a specific variable in an identity.
    """
    if name not in IDENTITIES:
        raise ValueError(f"Unknown identity: {name}")
        
    equation = IDENTITIES[name]
    target_sym = None
    
    # Find the target symbol
    for sym in equation.free_symbols:
        if sym.name == solve_for:
            target_sym = sym
            break
            
    if not target_sym:
        raise ValueError(f"Variable {solve_for} not found in identity {name}")
        
    # Substitute knowns
    sym_map = {s.name: s for s in equation.free_symbols}
    subs_dict = {}
    for k, v in knowns.items():
        if k in sym_map:
            subs_dict[sym_map[k]] = v
            
    # Solve
    # solve returns a list of solutions
    solutions = solve(equation.subs(subs_dict), target_sym)
    
    if not solutions:
        raise ValueError(f"No solution found for {solve_for}")
        
    # Return the first float solution
    for sol in solutions:
        if sol.is_real:
            return float(sol)
            
    raise ValueError(f"No real solution found for {solve_for}")

