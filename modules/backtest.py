import pandas as pd
from .indicators import add_indicators

def simple_swing_backtest(frame, fee_pct=0.15, slippage_pct=0.10):
    """Long-only demonstration: signal at close, enter next session open, exit on SMA20 loss.
    No future data is used for a signal. Costs are percentage inputs; returns are approximate.
    """
    x=add_indicators(frame).reset_index(drop=True)
    if len(x)<25:
        return {"error":"Cần ít nhất 25 phiên để chạy mô phỏng."}
    cash=1.0; position=0.0; entry=None; trades=[]; equity=[]
    for i in range(len(x)-1):
        row=x.iloc[i]; nxt=x.iloc[i+1]
        valid=pd.notna(row.get("SMA20")) and pd.notna(row.get("RSI14")) and pd.notna(row.get("MACD_HIST"))
        if not valid: 
            equity.append(cash + position*float(row.close)); continue
        buy_signal = row.close>row.SMA20 and row.RSI14>=50 and row.MACD_HIST>0
        sell_signal = row.close<row.SMA20 or row.RSI14<45
        if position==0 and buy_signal:
            px=float(nxt.open)*(1+slippage_pct/100)
            position=cash/(1+fee_pct/100)/px
            cash=0; entry=px
        elif position>0 and sell_signal:
            px=float(nxt.open)*(1-slippage_pct/100)
            cash=position*px*(1-fee_pct/100)
            trades.append({"entry":entry,"exit":px,"return_pct":(px/entry-1)*100})
            position=0; entry=None
        equity.append(cash+position*float(row.close))
    final=float(x.iloc[-1].close)
    total=(cash+position*final-1)*100
    wins=sum(t["return_pct"]>0 for t in trades)
    return {"total_return_pct":total,"closed_trades":len(trades),
            "win_rate_pct":(wins/len(trades)*100 if trades else None),
            "trades":trades,"equity_curve":equity,
            "note":"Mô phỏng cơ bản, chưa bao gồm giới hạn thanh khoản, thuế/phí thực tế và corporate actions."}
