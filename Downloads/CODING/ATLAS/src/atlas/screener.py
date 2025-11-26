"""
Stock Screener Engine for ATLAS.

Consumes the KPI Engine and allows composing filters such as:
    ROIC_True_Improved > 12 AND 
    EPV_Per_Share > 30 AND 
    Revenue_Growth_3Y_CAGR > 5

This engine is intentionally simple and deterministic.
"""

from src.atlas.kpi_engine import KPI_DEFINITIONS

OPS = {
    ">":  lambda a, b: a is not None and a > b,
    ">=": lambda a, b: a is not None and a >= b,
    "<":  lambda a, b: a is not None and a < b,
    "<=": lambda a, b: a is not None and a <= b,
    "==": lambda a, b: a is not None and a == b,
    "!=": lambda a, b: a is not None and a != b,
}

class ScreenerEngine:
    def __init__(self, atlas_loader):
        """
        atlas_loader: callable like load_atlas(ticker)
        """
        self.atlas_loader = atlas_loader

    def run(self, tickers, filters: dict):
        """
        tickers: list of tickers
        filters: {
            "EPV_Per_Share": (">", 40),
            "ROIC_True_Improved": (">", 15),
            "VariableCostShare": ("<", 0.6)
        }

        Return list of:
        {
            "ticker": "AAPL",
            "passes": True/False,
            "kpis": {...}
        }
        """
        results = []

        for t in tickers:
            atlas = self.atlas_loader(t)
            kpis = atlas.kpi_engine.latest_all()

            passes = True
            for metric, (op, threshold) in filters.items():
                val = kpis.get(metric)
                comparator = OPS.get(op)

                if comparator is None:
                    passes = False
                    break

                if not comparator(val, threshold):
                    passes = False

            results.append({
                "ticker": t,
                "passes": passes,
                "kpis": kpis,
            })

        return results

    def compile_dsl(self, text: str):
        """
        Compile tiny DSL like:
            ROIC_True_Improved > 10 AND
            Revenue_Growth_3Y_CAGR > 5 AND
            EPV_Per_Share > 30

        into:
            {"ROIC_True_Improved": (">", 10), ...}
        """
        lines = text.replace("AND", "\n").split("\n")
        out = {}
        for line in lines:
            line = line.strip()
            if not line:
                continue

            parts = None
            for op in [">=", "<=", "!=", "==", ">", "<"]:
                if op in line:
                    parts = line.split(op)
                    left = parts[0].strip()
                    right = float(parts[1].strip())
                    out[left] = (op, right)
                    break

        return out

