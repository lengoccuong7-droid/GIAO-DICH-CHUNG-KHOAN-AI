import pandas as pd

def find_support_resistance(df: pd.DataFrame, window=20):
    if df is None or len(df) < window:
        return {"support": None, "resistance": None, "note": f"Cần ít nhất {window} phiên."}
    recent = df.tail(window)
    support = float(recent['low'].min())
    resistance = float(recent['high'].max())
    return {"support": support, "resistance": resistance,
            "method": f"Min Low / Max High của {window} phiên gần nhất"}
