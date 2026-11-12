import pandas as pd
from modules.data_loader import normalize_ohlcv
from modules.indicators import add_indicators
from modules.decision_engine import make_trading_decision

def test_pipeline():
    n=260
    dates=pd.bdate_range("2025-01-01",periods=n)
    close=pd.Series([100+i*0.1 for i in range(n)])
    raw=pd.DataFrame({"Date":dates,"Open":close,"High":close+1,"Low":close-1,
                      "Close":close,"Volume":[10000]*n,"Symbol":["TEST"]*n})
    data=normalize_ohlcv(raw)
    enriched=add_indicators(data)
    assert "RSI14" in enriched and "SMA200" in enriched
    decision=make_trading_decision(enriched)
    assert "decision" in decision
