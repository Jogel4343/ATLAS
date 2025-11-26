import sys
from src.atlas.atlas import Atlas


def usage():
    print("Usage:")
    print("  python3 test_atlas.py <ticker> <period> <concept>")
    print("")
    print("Examples:")
    print("  python3 test_atlas.py AAPL 2022_10k NetIncome")
    print("  python3 test_atlas.py MSFT 2021_10k Revenue")
    print("  python3 test_atlas.py TSLA 2020_10k FreeCashFlow")
    print("  python3 test_atlas.py NVDA 2023_10k OperatingIncome")
    sys.exit(1)


if len(sys.argv) != 4:
    usage()


ticker = sys.argv[1]
period = sys.argv[2]
concept = sys.argv[3]


print("\n=== ATLAS FACT TEST ===")
print(f"Ticker:   {ticker}")
print(f"Period:   {period}")
print(f"Concept:  {concept}\n")


atlas = Atlas(ticker, period)

# IMPORTANT: Load downloader, selector, parser, extractor
atlas.load()

# Retrieve canonical concept value
value = atlas.get(concept)


if value is None:
    print(f"[!] Concept '{concept}' not found or could not be extracted.")
else:
    print(f"{concept}: {value}")
