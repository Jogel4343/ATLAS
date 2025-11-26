
class KPIEngine:
    def __init__(self, atlas):
        self.atlas = atlas

    # ---------------------------------------------------------
    # Helper: Safe Division & Extraction
    # ---------------------------------------------------------
    def _get(self, concept, year):
        return self.atlas.get(concept, year)

    def _div(self, num, den):
        if num is None or den is None or den == 0:
            return None
        return num / den

    def _growth(self, concept, year):
        if year is None:
            return None
        current = self._get(concept, year)
        previous = self._get(concept, year - 1)
        
        if current is None or previous is None or previous == 0:
            return None
        return (current - previous) / abs(previous)

    # ---------------------------------------------------------
    # 1. Basic Metrics
    # ---------------------------------------------------------
    def revenue(self, year):
        return self._get("Revenue", year)

    def cogs(self, year):
        val = self._get("CostOfRevenue", year)
        if val is None:
            val = self._get("CostOfGoodsSold", year)
        return val

    def gross_profit(self, year):
        # Try direct
        val = self._get("GrossProfit", year)
        if val is not None:
            return val
        # Derived
        rev = self.revenue(year)
        cogs_val = self.cogs(year)
        if rev is not None and cogs_val is not None:
            return rev - cogs_val
        return None

    def operating_income(self, year):
        return self._get("OperatingIncome", year)

    def ebit(self, year):
        # Try EBIT explicit
        val = self._get("EBIT", year)
        if val is not None:
            return val
        # Fallback to Operating Income
        return self.operating_income(year)

    def net_income(self, year):
        return self._get("NetIncome", year)

    def fcf(self, year):
        # Try FreeCashFlow explicit
        val = self._get("FreeCashFlow", year)
        if val is not None:
            return val
        # Derived: OperatingCashFlow - Capex
        ocf = self._get("OperatingCashFlow", year)
        capex = self.capex(year)
        if ocf is not None and capex is not None:
            return ocf - capex
        return None

    # ---------------------------------------------------------
    # 2. Margins
    # ---------------------------------------------------------
    def gross_margin(self, year):
        return self._div(self.gross_profit(year), self.revenue(year))

    def operating_margin(self, year):
        return self._div(self.operating_income(year), self.revenue(year))

    def ebit_margin(self, year):
        return self._div(self.ebit(year), self.revenue(year))

    def net_margin(self, year):
        return self._div(self.net_income(year), self.revenue(year))

    def fcf_margin(self, year):
        return self._div(self.fcf(year), self.revenue(year))

    # ---------------------------------------------------------
    # 3. Growth Rates (YoY)
    # ---------------------------------------------------------
    def revenue_growth(self, year):
        return self._growth("Revenue", year)

    def operating_income_growth(self, year):
        return self._growth("OperatingIncome", year)

    def net_income_growth(self, year):
        return self._growth("NetIncome", year)

    def ebit_growth(self, year):
        # Need to handle derived EBIT manually?
        # _growth uses _get which calls atlas.get
        # atlas.get("EBIT") might fail if EBIT not in facts but derived
        # So I should implement explicit calc
        if year is None: return None
        curr = self.ebit(year)
        prev = self.ebit(year - 1)
        if curr is None or prev is None or prev == 0:
            return None
        return (curr - prev) / abs(prev)

    def fcf_growth(self, year):
        if year is None: return None
        curr = self.fcf(year)
        prev = self.fcf(year - 1)
        if curr is None or prev is None or prev == 0:
            return None
        return (curr - prev) / abs(prev)

    # ---------------------------------------------------------
    # 4. Working Capital Modeling
    # ---------------------------------------------------------
    def working_capital(self, year):
        # Try explicit WorkingCapital
        val = self._get("WorkingCapital", year)
        if val is not None:
            return val
            
        # Component build-up
        ar = self._get("AccountsReceivable", year) or 0
        inv = self._get("Inventory", year) or 0
        other_ca = self._get("OtherCurrentAssets", year) or 0
        
        ap = self._get("AccountsPayable", year) or 0
        accrued = self._get("AccruedLiabilities", year) or 0
        other_cl = self._get("OtherCurrentLiabilities", year) or 0
        
        # If we have at least AR/AP, we assume valid partial WC
        if ar == 0 and ap == 0:
            return None
            
        current_assets = ar + inv + other_ca
        current_liabs = ap + accrued + other_cl
        return current_assets - current_liabs

    def delta_working_capital(self, year):
        curr = self.working_capital(year)
        prev = self.working_capital(year - 1)
        if curr is not None and prev is not None:
            return curr - prev
        return None

    # ---------------------------------------------------------
    # 5. Reinvestment Analysis
    # ---------------------------------------------------------
    def capex(self, year):
        # CapitalExpenditures or PaymentsToAcquirePropertyPlantAndEquipment
        return self._get("CapitalExpenditures", year)

    def depreciation(self, year):
        return self._get("Depreciation", year) or self._get("DepreciationAndAmortization", year)

    def reinvestment(self, year):
        # capex + delta_working_capital + R&D
        capex = self.capex(year) or 0
        dwc = self.delta_working_capital(year) or 0
        rnd = self._get("ResearchAndDevelopment", year) or 0
        
        # If all zero, likely missing data
        if capex == 0 and dwc == 0 and rnd == 0:
            return None
            
        return capex + dwc + rnd

    def reinvestment_rate(self, year):
        return self._div(self.reinvestment(year), self.nopat(year))

    # ---------------------------------------------------------
    # 6. ROIC & Incremental ROIC
    # ---------------------------------------------------------
    def nopat(self, year):
        ebit_val = self.ebit(year)
        if ebit_val is None:
            return None
            
        # Tax Rate
        # Try Effective Tax Rate: TaxProvision / PretaxIncome
        tax_prov = self._get("IncomeTaxExpenseBenefit", year)
        pretax = self._get("IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest", year)
        
        tax_rate = 0.21
        if tax_prov is not None and pretax is not None and pretax > 0:
            computed_rate = tax_prov / pretax
            # Clamp to reasonable bounds (0% to 50%)
            if 0.0 <= computed_rate <= 0.5:
                tax_rate = computed_rate
                
        return ebit_val * (1 - tax_rate)

    def invested_capital(self, year):
        # working_capital + PPE + intangibles + goodwill
        wc = self.working_capital(year) or 0
        ppe = self._get("PropertyPlantAndEquipmentNet", year) or 0
        intangibles = self._get("IntangibleAssetsNetExcludingGoodwill", year) or 0
        goodwill = self._get("Goodwill", year) or 0
        
        if ppe == 0 and wc == 0:
            return None
            
        return wc + ppe + intangibles + goodwill

    def roic(self, year):
        return self._div(self.nopat(year), self.invested_capital(year))

    def incremental_roic(self, start_year, end_year):
        # ΔNOPAT / reinvestment_sum? Or ΔNOPAT / ΔInvestedCapital?
        # Prompt says: ΔNOPAT / reinvestment
        # Reinvestment is a flow. Should be sum of reinvestment over period?
        # Or just (NOPAT_end - NOPAT_start) / Reinvestment_end?
        # Standard: (NOPAT_t - NOPAT_t-1) / Reinvestment_t-1.
        # Prompt doesn't specify aggregation.
        # I'll assume point-to-point: (NOPAT_end - NOPAT_start) / Sum(Reinvestment start..end-1)
        # Or simplified: (NOPAT_end - NOPAT_start) / (InvestedCapital_end - InvestedCapital_start)?
        # Prompt explicitly says: ΔNOPAT / reinvestment
        # I'll use Reinvestment of the end_year (or start_year?).
        # Ideally it's Cumulative Reinvestment.
        # Given "reinvestment(year)" is requested, I'll sum it if possible, or just use single year if range is 1 year.
        # But without range logic, I'll just implement for single year step?
        # "incremental_roic(start_year, end_year)".
        # I'll calculate Delta NOPAT and Sum of Reinvestment between start (inclusive) and end (exclusive).
        
        nopat_end = self.nopat(end_year)
        nopat_start = self.nopat(start_year)
        
        if nopat_end is None or nopat_start is None:
            return None
            
        delta_nopat = nopat_end - nopat_start
        
        # Sum reinvestment from start_year to end_year-1
        total_reinv = 0.0
        count = 0
        for y in range(start_year, end_year):
            r = self.reinvestment(y)
            if r is not None:
                total_reinv += r
                count += 1
        
        if count == 0 or total_reinv == 0:
            return None
            
        return delta_nopat / total_reinv

    # ---------------------------------------------------------
    # 7. CROCI
    # ---------------------------------------------------------
    def croci(self, year):
        # (operating_cash_flow - maintenance_capex) / invested_capital
        ocf = self._get("OperatingCashFlow", year)
        if ocf is None:
            return None
            
        # Maintenance Capex ~ Depreciation
        m_capex = self.depreciation(year) or 0
        
        ic = self.invested_capital(year)
        
        return self._div(ocf - m_capex, ic)

    # ---------------------------------------------------------
    # 8. Operating Leverage
    # ---------------------------------------------------------
    def operating_leverage(self, year1, year2):
        # %ΔOperatingIncome / %ΔRevenue
        op_inc1 = self.operating_income(year1)
        op_inc2 = self.operating_income(year2)
        rev1 = self.revenue(year1)
        rev2 = self.revenue(year2)
        
        if None in (op_inc1, op_inc2, rev1, rev2):
            return None
        if op_inc1 == 0 or rev1 == 0:
            return None
            
        pct_delta_op = (op_inc2 - op_inc1) / abs(op_inc1)
        pct_delta_rev = (rev2 - rev1) / abs(rev1)
        
        return self._div(pct_delta_op, pct_delta_rev)

    # ---------------------------------------------------------
    # 9. Unit Economics (generic)
    # ---------------------------------------------------------
    def revenue_per_unit(self, year, units):
        return self._div(self.revenue(year), units)

    def variable_cost_per_unit(self, year, units):
        # Needs Variable Costs.
        # Approx: COGS + some portion of Opex?
        # Prompt didn't specify VC calculation.
        # I'll assume COGS is variable.
        vc = self.cogs(year)
        return self._div(vc, units)

    def contribution_margin_per_unit(self, year, units):
        rev_u = self.revenue_per_unit(year, units)
        vc_u = self.variable_cost_per_unit(year, units)
        if rev_u is None or vc_u is None:
            return None
        return rev_u - vc_u

    def ltv(self, cac, churn):
        # LTV = CAC / Churn? No, LTV = CM / Churn usually.
        # But prompt says: ltv(cac, churn).
        # Maybe they mean Input args are arbitrary?
        # Usually LTV = (ARPU * Margin) / Churn.
        # If input is just cac and churn, maybe they mean "Break even LTV"?
        # Or maybe `ltv` method just CALCULATES it from available data?
        # The signature is `ltv(cac, churn)`.
        # This implies it DOES NOT look up data, just computes?
        # But LTV formula needs Contribution Margin.
        # Wait, if LTV/CAC = 3, then LTV = 3 * CAC.
        # Maybe `ltv` is `contribution_margin / churn`?
        # And `cac` is just passed in?
        # I'll assume standard: LTV = ContributionMarginPerUser / Churn.
        # But the method signature provided in prompt is `ltv(cac, churn)`.
        # This is weird. `cac` is cost. `churn` is rate.
        # Unless it meant `ltv(cm, churn)`?
        # Or maybe it's a helper method?
        # I'll implement `ltv(cm, churn)` logic but handle args names?
        # No, I'll stick to prompt signature `ltv(cac, churn)`?
        # Maybe it meant `ltv(arpu, margin, churn)`?
        # I will assume it's a helper: `ltv(margin, churn)`.
        # But prompt says "ltv(cac, churn)". This might be a typo in prompt or a specific formula I'm unaware of (LTV based on CAC recovery?).
        # Actually, LTV is independent of CAC.
        # I'll assume the prompt meant `ltv(contribution_margin, churn)`.
        # But since I must follow instructions, I will implement:
        # `def ltv(self, margin, churn): return margin / churn if churn else None`
        # And assume the first arg is margin.
        # Wait, `ltv_to_cac(ltv, cac)` is next.
        # So `ltv` must return value.
        
        # I will add `unit_economics` method to Atlas that calls these?
        # The prompt lists these as methods of KPIEngine.
        # `revenue_per_unit(year, units)` needs `units`.
        # User provides `units`.
        
        # I'll implement `ltv(cm, churn)` assuming first arg is Contribution Margin.
        # And rename arg to `cm` for clarity, or keep `cac` if prompt insisted?
        # "ltv(cac, churn)" is definitely odd.
        # I'll use `value, churn` -> `value / churn`.
        
        if churn is None or churn == 0:
            return None
        # Assuming first arg is Contribution Margin (value per period)
        return cac / churn 

    def ltv_to_cac(self, ltv, cac):
        return self._div(ltv, cac)

