from .atlas import Atlas

def load_universe(tickers):
    """
    Convenience wrapper: return list of Atlas instances for a list of tickers.
    """
    return [Atlas(t) for t in tickers]

