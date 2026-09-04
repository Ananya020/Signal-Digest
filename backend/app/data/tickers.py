"""Fixed ticker universe — hand-curated per PRODUCT.md, do not fetch sector
metadata from an external API. Bare NSE symbols here for readability; the
`.NS` suffix is appended once, consistently, at the DB-storage boundary
(see `to_nse_symbol`) — never stored bare anywhere.
"""

TICKER_SECTORS: dict[str, str] = {
    # Banking / Finance
    "HDFCBANK": "Banking/Finance",
    "ICICIBANK": "Banking/Finance",
    "SBIN": "Banking/Finance",
    "KOTAKBANK": "Banking/Finance",
    "AXISBANK": "Banking/Finance",
    "BAJFINANCE": "Banking/Finance",
    "BAJAJFINSV": "Banking/Finance",
    # IT
    "TCS": "IT",
    "INFY": "IT",
    "WIPRO": "IT",
    "HCLTECH": "IT",
    "TECHM": "IT",
    # Energy / Materials
    "RELIANCE": "Energy/Materials",
    "LT": "Energy/Materials",
    "ULTRACEMCO": "Energy/Materials",
    "ADANIENT": "Energy/Materials",
    "NTPC": "Energy/Materials",
    "POWERGRID": "Energy/Materials",
    "TATASTEEL": "Energy/Materials",
    # Consumer / FMCG
    "ITC": "Consumer/FMCG",
    "HINDUNILVR": "Consumer/FMCG",
    "NESTLEIND": "Consumer/FMCG",
    "TITAN": "Consumer/FMCG",
    "ASIANPAINT": "Consumer/FMCG",
    "TRENT": "Consumer/FMCG",
    # Auto
    "MARUTI": "Auto",
    "M&M": "Auto",
    "TATAMOTORS": "Auto",
    "BAJAJ-AUTO": "Auto",
    "EICHERMOT": "Auto",
    # Pharma / Healthcare
    "SUNPHARMA": "Pharma/Healthcare",
    "DRREDDY": "Pharma/Healthcare",
    "CIPLA": "Pharma/Healthcare",
    "APOLLOHOSP": "Pharma/Healthcare",
    "DIVISLAB": "Pharma/Healthcare",
}


def to_nse_symbol(bare_symbol: str) -> str:
    """The one place `.NS` is appended. Every DB write/read of a ticker
    identifier (tickers.ticker, price_ticks.ticker, baselines.ticker) must go
    through this suffixed form — never store the bare symbol."""
    return f"{bare_symbol}.NS"
