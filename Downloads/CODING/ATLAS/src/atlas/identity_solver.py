"""
Identity Solver for Unit Economics.
Invokes SymPy identities to enforce consistency and solve for missing values.
"""

from typing import Dict, Any, List
from .economic_identities import IDENTITIES, solve_identity, check_consistency, evaluate_identity

class IdentityError(Exception):
    """Raised when an identity constraint is violated."""
    pass

def solve_unit_identity(identity_name: str, inputs: Dict[str, float], solve_for: str) -> float:
    """
    Solve a specific identity for a target variable.
    """
    try:
        return solve_identity(identity_name, inputs, solve_for)
    except Exception as e:
        raise IdentityError(f"Failed to solve {identity_name} for {solve_for}: {str(e)}")

def enforce_all(ue_model: Dict[str, float], tolerance: float = 1e-2) -> None:
    """
    Check all relevant identities against the computed unit economics model.
    Raises IdentityError if any applicable identity is broken.
    
    The ue_model dict is expected to contain keys matching the SymPy symbols
    in economic_identities.py (e.g., 'Revenue', 'CAC', 'ROIC').
    """
    
    # Map of concept groups to check
    # We only check identities where we have all inputs (or enough inputs)
    
    checks = [
        ("CAC_Identity", ["CAC", "SalesMarketing", "RetentionMarketing", "GrossNewCustomers"]),
        ("ContributionMargin_Identity", ["ContributionMarginPerUnit", "Revenue", "COGS_variable", "VolumeDriver"]),
        ("UnitRevenue_Identity", ["RevenuePerUnit", "Revenue", "VolumeDriver"]),
        ("VariableCostPerUnit_Identity", ["VariableCostPerUnit", "COGS_variable", "VolumeDriver"]),
        ("ContributionMargin_Check", ["ContributionMarginPerUnit", "RevenuePerUnit", "VariableCostPerUnit"]),
        ("ROIC_Identity", ["ROIC", "NOPAT", "InvestedCapital"]),
        ("ReinvestmentRate_Identity", ["ReinvestmentRate", "Capex", "DeltaWorkingCapital", "RnD", "NOPAT"]),
    ]
    
    violations = []
    
    for name, required_keys in checks:
        # Check if we have data to verify this identity
        if all(k in ue_model and ue_model[k] is not None for k in required_keys):
            is_consistent = check_consistency(name, ue_model, tolerance)
            if not is_consistent:
                diff = evaluate_identity(name, ue_model)
                violations.append(f"{name} (diff={diff:.4f})")
                
    if violations:
        raise IdentityError(f"Identity violations detected: {', '.join(violations)}")

def solve_missing_values(ue_model: Dict[str, float]) -> Dict[str, float]:
    """
    Iteratively attempt to solve for missing values using identities.
    Returns updated dictionary.
    """
    updated = ue_model.copy()
    
    # List of potential solves: (identity, target, requires)
    solvers = [
        # CAC
        ("CAC_Identity", "CAC", ["SalesMarketing", "RetentionMarketing", "GrossNewCustomers"]),
        ("CAC_Identity", "GrossNewCustomers", ["SalesMarketing", "RetentionMarketing", "CAC"]),
        
        # Unit Economics
        ("UnitRevenue_Identity", "RevenuePerUnit", ["Revenue", "VolumeDriver"]),
        ("VariableCostPerUnit_Identity", "VariableCostPerUnit", ["COGS_variable", "VolumeDriver"]),
        ("ContributionMargin_Identity", "ContributionMarginPerUnit", ["Revenue", "COGS_variable", "VolumeDriver"]),
        ("ContributionMargin_Check", "ContributionMarginPerUnit", ["RevenuePerUnit", "VariableCostPerUnit"]),
        
        # ROIC
        ("NOPAT_Identity", "NOPAT", ["OperatingIncome", "TaxRate"]),
        ("ROIC_Identity", "ROIC", ["NOPAT", "InvestedCapital"]),
        
        # Reinvestment
        ("ReinvestmentRate_Identity", "ReinvestmentRate", ["Capex", "DeltaWorkingCapital", "RnD", "NOPAT"]),
    ]
    
    changed = True
    while changed:
        changed = False
        for name, target, requires in solvers:
            if updated.get(target) is None:
                # Check requirements
                if all(updated.get(req) is not None for req in requires):
                    try:
                        val = solve_unit_identity(name, updated, target)
                        updated[target] = val
                        changed = True
                    except:
                        pass
                        
    return updated

