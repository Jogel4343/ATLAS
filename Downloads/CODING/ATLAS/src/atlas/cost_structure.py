import math

class CostStructureEngine:
    def __init__(self, atlas):
        self.atlas = atlas

    # === Helper methods ===

    def _get_series(self, metric: str):
        """
        Return chronological list of (period, value) using atlas.series(metric, kind="raw").
        If not sorted, sort by period key lexicographically.
        Return [] if missing.
        """
        series = self.atlas.series(metric, kind="raw")
        if not series:
            return []
        # Sort by year/period. Assuming period is first element of tuple.
        # atlas.series returns [(year, value), ...]. year can be int or str?
        # Standardize sorting.
        return sorted(series, key=lambda x: x[0])

    def _latest(self, series):
        """Return last value or None."""
        if not series:
            return None
        return series[-1][1]

    def _pct_changes(self, series):
        """
        Return aligned list of %Δ values for periods[1:].
        If prev or curr is None/0 → return None for that index.
        """
        if len(series) < 2:
            return []
        
        changes = []
        # Start from 1
        for i in range(1, len(series)):
            prev_val = series[i-1][1]
            curr_val = series[i][1]
            
            if prev_val is None or prev_val == 0 or curr_val is None:
                changes.append(None)
            else:
                pct = (curr_val - prev_val) / prev_val
                changes.append(pct)
        return changes

    def _ema(self, values, half_life=3):
        """
        EMA applied in chronological order.
        alpha = 1 - exp(-ln(2)/half_life).
        Ignore None values (carry forward previous EMA).
        """
        if not values:
            return []
            
        alpha = 1.0 - math.exp(-math.log(2) / half_life)
        ema_series = []
        current_ema = None
        
        for v in values:
            if v is not None:
                if current_ema is None:
                    current_ema = v
                else:
                    current_ema = alpha * v + (1 - alpha) * current_ema
            ema_series.append(current_ema)
            
        return ema_series

    def _safe_div(self, num, den):
        """Return None if invalid or den == 0."""
        if num is None or den is None or den == 0:
            return None
        return num / den

    # === Core methods ===

    def compute_cost_buckets(self):
        """
        Fetch per-period series for cost buckets.
        Return dict of {bucket: {period: value}}
        """
        # Mapping: internal bucket name -> atlas concept
        bucket_map = {
            "COGS": "CostOfRevenue",
            "RnD": "ResearchAndDevelopmentExpense",
            "SalesMarketing": "SellingAndMarketingExpense",
            "GandA": "SellingGeneralAndAdministrative"
        }
        
        buckets = {}
        for bucket, concept in bucket_map.items():
            series = self._get_series(concept)
            # If series is missing, try alternative for COGS
            if bucket == "COGS" and not series:
                series = self._get_series("CostOfGoodsAndServicesSold")
                
            # Convert to dict {period: value}
            buckets[bucket] = {p: v for p, v in series} if series else {}
            
        return buckets

    def estimate_elasticities(self, buckets):
        """
        Compute elasticity per bucket per period.
        Return (elasticities_dict, volume_proxy_series, volume_proxy_name)
        """
        # 1) Try unit economics driver
        try:
            ue = self.atlas.unit_economics()
            driver_name = ue.get("consolidated", {}).get("volume_driver")
        except:
            driver_name = None
            
        volume_series = []
        if driver_name:
            volume_series = self._get_series(driver_name)
            
        # 2) Else → use Revenue series
        if not volume_series:
            driver_name = "Revenue"
            volume_series = self._get_series("Revenue")
            
        if not volume_series:
            return {}, [], "Unknown"

        # Compute % change for volume
        # We need aligned periods.
        # Let's find common periods across all buckets and volume
        # But simpler: just iterate periods present in volume series (except first)
        
        elasticities = {b: {} for b in buckets}
        
        # Pre-compute volume pct changes
        # volume_series is sorted [(p1, v1), (p2, v2), ...]
        
        for i in range(1, len(volume_series)):
            curr_p, curr_vol = volume_series[i]
            prev_p, prev_vol = volume_series[i-1]
            
            # Calculate vol % change
            if prev_vol and prev_vol != 0 and curr_vol is not None:
                vol_pct = (curr_vol - prev_vol) / prev_vol
            else:
                vol_pct = None
                
            # Iterate buckets
            for bucket, data in buckets.items():
                # Check if we have cost data for these periods
                curr_cost = data.get(curr_p)
                prev_cost = data.get(prev_p)
                
                if curr_cost is not None and prev_cost is not None and prev_cost != 0 and vol_pct is not None and vol_pct != 0:
                    cost_pct = (curr_cost - prev_cost) / prev_cost
                    elasticity = cost_pct / vol_pct
                    elasticities[bucket][curr_p] = elasticity
                else:
                    # Cannot compute elasticity
                    elasticities[bucket][curr_p] = None
                    
        return elasticities, volume_series, driver_name

    def compute_fixed_variable_split(self, buckets, elasticities, volume_series):
        """
        Compute variable/fixed split per period based on elasticities.
        """
        # Structure to hold per-period results
        # We need to iterate over all periods present in buckets/volume
        
        # Collect all periods
        periods = set()
        for b in buckets.values():
            periods.update(b.keys())
        sorted_periods = sorted(list(periods))
        
        results = {
            "variable_cost": {},
            "fixed_cost": {},
            "variable_share": {},
            "total": {}
        }
        
        # Default classifications if elasticity missing
        default_shares = {
            "COGS": 1.0, # Assume variable
            "RnD": 0.0,  # Assume fixed
            "SalesMarketing": 0.5, # Semi
            "GandA": 0.0 # Fixed
        }
        
        # To smooth elasticity, we can use EMA of elasticity? 
        # The prompt says "Apply EMA smoothing to variable_share per bucket and for total" in compute_all.
        # Here we compute raw share.
        
        bucket_variable_shares = {b: {} for b in buckets}
        
        for p in sorted_periods:
            total_cost = 0.0
            total_variable = 0.0
            
            for bucket, data in buckets.items():
                cost = data.get(p)
                if cost is None:
                    continue
                
                total_cost += cost
                
                # Determine elasticity
                # If p is in elasticities, use it. Else use default?
                # Elasticity is computed from delta, so period p has elasticity (relative to p-1).
                # For p=0 (first period), we have no elasticity. 
                
                elas = elasticities.get(bucket, {}).get(p)
                
                share = 0.0
                if elas is not None:
                    # Clamp elasticity 0 to 1 to get share?
                    # Prompt: variable_share = clamp(elasticity, 0, 1)
                    share = max(0.0, min(elas, 1.0))
                    
                    # Classification logic (just for reference, share is used for calc)
                    # <0.3 fixed, >0.7 variable.
                    # The prompt implies the share IS the clamped elasticity.
                else:
                    # Fallback
                    share = default_shares.get(bucket, 0.0)
                
                bucket_variable_shares[bucket][p] = share
                total_variable += cost * share
                
            results["total"][p] = total_cost
            results["variable_cost"][p] = total_variable
            results["fixed_cost"][p] = total_cost - total_variable
            results["variable_share"][p] = self._safe_div(total_variable, total_cost)
            
        return results, bucket_variable_shares

    def compute_marginal_costs(self, variable_costs, volume_series):
        """
        marginal_cost = variable_cost / volume_proxy
        """
        vol_dict = dict(volume_series)
        mc = {}
        for p, vc in variable_costs.items():
            vol = vol_dict.get(p)
            mc[p] = self._safe_div(vc, vol)
        return mc

    def compute_contribution_margin(self, variable_costs, revenue_series):
        """
        contribution = 1 - variable_cost / Revenue
        """
        rev_dict = dict(revenue_series)
        cm = {}
        for p, vc in variable_costs.items():
            rev = rev_dict.get(p)
            val = self._safe_div(vc, rev)
            if val is not None:
                cm[p] = 1.0 - val
            else:
                cm[p] = None
        return cm

    def compute_break_even(self, fixed_costs, contribution_margins):
        """
        BE = fixed_cost / contribution_margin
        Using latest valid.
        """
        # Sort periods descending
        periods = sorted(fixed_costs.keys(), reverse=True)
        for p in periods:
            fc = fixed_costs.get(p)
            cm = contribution_margins.get(p)
            
            if fc is not None and cm is not None and cm > 0:
                return fc / cm
        return None

    def compute_all(self):
        """
        Orchestrate all steps.
        """
        # 1. Buckets
        buckets = self.compute_cost_buckets()
        
        # 2. Elasticities
        elasticities, volume_series, vol_proxy_name = self.estimate_elasticities(buckets)
        
        # 3. Split
        split_res, bucket_shares = self.compute_fixed_variable_split(buckets, elasticities, volume_series)
        
        # 4. Marginal Costs
        mc_series = self.compute_marginal_costs(split_res["variable_cost"], volume_series)
        
        # 5. Contribution Margin
        # Need Revenue series
        revenue_series = self._get_series("Revenue")
        cm_series = self.compute_contribution_margin(split_res["variable_cost"], revenue_series)
        
        # 6. Break Even
        be = self.compute_break_even(split_res["fixed_cost"], cm_series)
        
        # 7. Smoothing variable shares
        # For total variable share
        # Sort split_res["variable_share"] by period
        periods = sorted(split_res["variable_share"].keys())
        shares = [split_res["variable_share"][p] for p in periods]
        smoothed_shares = self._ema(shares)
        smoothed_share_dict = {periods[i]: smoothed_shares[i] for i in range(len(periods))}
        
        # Latest values
        latest_p = periods[-1] if periods else None
        
        result = {
            "COGS": buckets.get("COGS", {}),
            "RnD": buckets.get("RnD", {}),
            "SalesMarketing": buckets.get("SalesMarketing", {}),
            "GandA": buckets.get("GandA", {}),
            "elasticities": elasticities,
            "variable_shares": {
                "per_period": split_res["variable_share"],
                "smoothed": smoothed_share_dict,
                "latest": smoothed_share_dict.get(latest_p) if latest_p else None
            },
            "marginal_cost": {
                "per_period": mc_series,
                "latest": mc_series.get(latest_p) if latest_p else None
            },
            "contribution_margin": {
                "per_period": cm_series,
                "latest": cm_series.get(latest_p) if latest_p else None
            },
            "break_even_revenue": be,
            "metadata": {
                "volume_proxy": vol_proxy_name,
                "periods": periods
            }
        }
        
        return result
