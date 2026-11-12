import pandas as pd
from .indicators import add_indicators
from .decision_engine import make_trading_decision

def analyze_symbol(frame, capital_vnd=100_000_000, risk_pct=1.0, max_alloc_pct=20.0,
                   lot_size=100, price_multiplier=1.0):
    enriched = add_indicators(frame)
    decision = make_trading_decision(enriched, capital_vnd, risk_pct, max_alloc_pct,
                                     lot_size, price_multiplier)
    return enriched, decision

def analyze_universe(data, **kwargs):
    results = {}
    for symbol, frame in data.groupby("symbol", sort=True):
        results[symbol] = analyze_symbol(frame, **kwargs)
    return results
