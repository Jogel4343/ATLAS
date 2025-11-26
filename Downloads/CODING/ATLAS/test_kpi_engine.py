import sys
from src.atlas.atlas import Atlas


def usage():
    print("Usage:")
    print("  python3 test_kpi_engine.py <ticker> <period> <metric>")
    print("")
    print("Examples:")
    print("  python3 test_kpi_engine.py PRDO 2023_10k ROIC")
    print("  python3 test_kpi_engine.py AAPL 2022_10k Revenue_Growth")
    print("  python3 test_kpi_engine.py MSFT 2021_10k FCF_Margin")
    print("")
    print("Available metrics:")
    print("  - Revenue_Growth")
    print("  - Revenue_Growth_3Y_CAGR")
    print("  - Revenue_Growth_Stability")
    print("  - ROIC")
    print("  - ReinvestmentRate")
    print("  - FCF_Margin")
    print("  - Operating_Leverage")
    print("  - Capex_Intensity")
    sys.exit(1)


if len(sys.argv) != 4:
    usage()


ticker = sys.argv[1]
period = sys.argv[2]
metric = sys.argv[3]


print("\n=== ATLAS KPI ENGINE TEST ===")
print(f"Ticker:   {ticker}")
print(f"Period:   {period}")
print(f"Metric:   {metric}\n")


atlas = Atlas(ticker, period)
atlas.load()

# Test latest value
latest_value = atlas.kpi.latest(metric)

if latest_value is None:
    print(f"[!] Metric '{metric}' not found or could not be computed.")
    from src.atlas.kpi_engine import KPI_DEFINITIONS
    print(f"[!] Available metrics: {list(KPI_DEFINITIONS.keys())}")
else:
    print(f"Latest {metric}: {latest_value}")

# Test series
series_data = atlas.kpi.series(metric)
if series_data:
    print(f"\n{metric} Series:")
    for year, value in series_data:
        print(f"  {year}: {value}")

