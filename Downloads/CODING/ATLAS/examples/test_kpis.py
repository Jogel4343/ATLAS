from src.atlas.atlas import Atlas

def run_kpi_test():
    print("Loading Atlas for AAPL 2024_10-K...")
    try:
        atlas = Atlas("AAPL", "2024_10-K")
        atlas.load()
    except Exception as e:
        print(f"Failed to load Atlas: {e}")
        return

    kpi = atlas.kpi()
    
    # Attempt to detect latest year from facts if possible, or hardcode
    # AAPL FY ends Sep.
    year = 2024
    
    print(f"\n=== KPI Report for AAPL {year} ===")
    
    metrics = [
        ("Revenue", kpi.revenue(year)),
        ("Gross Profit", kpi.gross_profit(year)),
        ("Operating Income", kpi.operating_income(year)),
        ("Net Income", kpi.net_income(year)),
        ("Free Cash Flow", kpi.fcf(year)),
        ("EBIT", kpi.ebit(year)),
    ]
    
    for name, val in metrics:
        fmt = f"{val:,.0f}" if val is not None else "None"
        print(f"{name:<20} : {fmt}")
        
    print("\n--- Margins ---")
    margins = [
        ("Gross Margin", kpi.gross_margin(year)),
        ("Operating Margin", kpi.operating_margin(year)),
        ("Net Margin", kpi.net_margin(year)),
        ("FCF Margin", kpi.fcf_margin(year)),
    ]
    for name, val in margins:
        fmt = f"{val:.1%}" if val is not None else "None"
        print(f"{name:<20} : {fmt}")

    print("\n--- Growth (YoY) ---")
    growth = [
        ("Revenue Growth", kpi.revenue_growth(year)),
        ("Op Income Growth", kpi.operating_income_growth(year)),
        ("Net Income Growth", kpi.net_income_growth(year)),
        ("FCF Growth", kpi.fcf_growth(year)),
    ]
    for name, val in growth:
        fmt = f"{val:.1%}" if val is not None else "None"
        print(f"{name:<20} : {fmt}")

    print("\n--- Capital & Returns ---")
    capital = [
        ("Working Capital", kpi.working_capital(year)),
        ("Invested Capital", kpi.invested_capital(year)),
        ("Reinvestment", kpi.reinvestment(year)),
        ("NOPAT", kpi.nopat(year)),
        ("ROIC", kpi.roic(year)),
        ("CROCI", kpi.croci(year)),
        ("Reinvestment Rate", kpi.reinvestment_rate(year)),
    ]
    for name, val in capital:
        if "Rate" in name or "ROIC" in name or "CROCI" in name:
             fmt = f"{val:.1%}" if val is not None else "None"
        else:
             fmt = f"{val:,.0f}" if val is not None else "None"
        print(f"{name:<20} : {fmt}")

if __name__ == "__main__":
    run_kpi_test()

