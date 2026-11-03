#!/usr/bin/env python3
"""Live public-market observer for Kalshi-style BTC 15-minute contracts. PAPER ONLY."""
import argparse, json, math, time
from collections import deque
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.parse import urlencode

KALSHI="https://external-api.kalshi.com/trade-api/v2"
SPOT="https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"

def get(url):
    req=Request(url,headers={"User-Agent":"DESK-PRO-paper-only/1.0","Accept":"application/json"})
    with urlopen(req,timeout=8) as r: return json.loads(r.read().decode())

def val(x,*keys,default=None):
    for k in keys:
        try:
            if x.get(k) is not None: return float(x[k])
        except (TypeError,ValueError): pass
    return default

def ts(m, now):
    # Kalshi commonly supplies ISO-8601 close_time; accept epoch fields too.
    n=val(m,"close_time_ts","close_ts")
    if n is not None: return n
    raw=m.get("close_time") or m.get("expiration_time")
    if raw:
        try: return datetime.fromisoformat(raw.replace("Z","+00:00")).timestamp()
        except (ValueError,TypeError): pass
    return now+900

def markets():
    u=KALSHI+"/markets?"+urlencode({"series_ticker":"KXBTC15M","status":"open","limit":20})
    return get(u).get("markets",[])

def book(ticker):
    b=get(KALSHI+"/markets/"+ticker+"/orderbook").get("orderbook",{})
    yes=b.get("yes",[]) or []; no=b.get("no",[]) or []
    yb=max((float(x[0]) for x in yes if len(x)>1 and float(x[1])>0),default=None)
    nb=max((float(x[0]) for x in no if len(x)>1 and float(x[1])>0),default=None)
    return {"yes_bid":yb,"yes_ask":100-nb if nb is not None else None,
            "no_bid":nb,"no_ask":100-yb if yb is not None else None}

def decide(prices,b,left):
    yb,ya=b["yes_bid"],b["yes_ask"]
    if len(prices)<7 or yb is None or ya is None:
        return ("NO TRADE",0,"Need more live samples and a two-sided order book.")
    r=[(prices[i]/prices[i-1]-1)*10000 for i in range(1,len(prices))]
    momentum=sum(r[-3:])/3-sum(r[-6:-3])/3
    spread=ya-yb; direction="UP" if momentum>0.15 else "DOWN" if momentum < -0.15 else None
    confidence=min(.90,.50+abs(momentum)*.7)
    if direction is None: return ("NO TRADE",confidence,"Short-term momentum is weak or mixed.")
    if spread>5: return ("NO TRADE",confidence,"Spread exceeds 5 cents.")
    if left<25: return ("NO TRADE",confidence,"Too close to expiry.")
    ask=ya if direction=="UP" else b["no_ask"]
    if ask is None: return ("NO TRADE",confidence,"No executable-side quote.")
    if confidence-ask/100<.08:
        return ("NO TRADE",confidence,"Heuristic edge below 8 percentage points after quote price.")
    return (direction,confidence,f"Momentum {momentum:+.2f} bp; spread {spread:.1f}¢; heuristic edge {confidence-ask/100:.1%}.")

class Wallet:
    def __init__(self,cash=10,fee_rate=.07,slip=.5):
        self.start=cash; self.cash=cash; self.fee_rate=fee_rate; self.slip=slip; self.pos=None; self.events=[]; self.peak=cash; self.maxdd=0
    def enter(self,side,ask,ticker,reason,confidence):
        if self.pos or ask is None: return "NO FILL: position open or missing ask"
        price=min(99.9,ask+self.slip); fee_per=self.fee_rate*(price/100)*(1-price/100)
        cost=price/100+fee_per; qty=math.floor((min(self.cash,self.cash*.20)/cost)*100)/100
        if qty<1: return "NO FILL: 20% risk cap and $10 balance cannot fund one contract"
        self.cash-=qty*cost
        self.pos={"ticker":ticker,"side":side,"qty":qty,"entry":price,"entry_fee":qty*fee_per,"reason":reason,"confidence":confidence}
        self.events.append({"type":"PAPER_BUY","ticker":ticker,"side":side,"qty":qty,"entry_cents":round(price,3)})
        return f"PAPER BUY {side} x{qty:g} at {price:.2f}¢"
    def mark(self,b):
        mark=b["yes_bid"] if self.pos and self.pos["side"]=="UP" else b["no_bid"]
        eq=self.cash+(self.pos["qty"]*mark/100 if self.pos and mark is not None else 0)
        self.peak=max(self.peak,eq); dd=(self.peak-eq)/self.peak if self.peak else 0; self.maxdd=max(dd,self.maxdd)
        return eq
    def settle(self,result):
        if not self.pos:return "No open paper position to settle."
        p=self.pos; win=(result=="yes" and p["side"]=="UP") or (result=="no" and p["side"]=="DOWN")
        payout=p["qty"] if win else 0; pnl=payout-p["qty"]*p["entry"]/100-p["entry_fee"]
        self.cash+=payout; self.events.append({"type":"PAPER_SETTLEMENT","ticker":p["ticker"],"result":result,"net_pnl":round(pnl,4)})
        self.pos=None; return f"SETTLEMENT {result.upper()} | net P/L {pnl:+.4f} | cash {self.cash:.4f}"

def main():
    ap=argparse.ArgumentParser(description="Live Kalshi 15-minute paper simulator")
    ap.add_argument("--cash",type=float,default=10); ap.add_argument("--poll",type=int,default=5); ap.add_argument("--once",action="store_true")
    ap.add_argument("--fee-rate",type=float,default=.07,help="estimated fee coefficient; check current market fee schedule")
    a=ap.parse_args()
    if a.cash<=0: ap.error("--cash must be positive")
    prices=deque(maxlen=30); w=Wallet(a.cash,a.fee_rate); print("DESK PRO | LIVE PUBLIC DATA | PAPER ONLY — no order submission")
    while True:
        try:
            spot=float(get(SPOT)["price"]); prices.append(spot); ms=markets()
            if not ms: raise RuntimeError("No open KXBTC15M markets returned by public API.")
            now=time.time(); ms.sort(key=lambda m:abs(ts(m,now)-now))
            m=ms[0]; ticker=m["ticker"]
            # If the prior window closed, ask the public market endpoint for its final result.
            if w.pos and w.pos["ticker"] != ticker:
                try:
                    old=get(KALSHI+"/markets/"+w.pos["ticker"]).get("market",{})
                    result=str(old.get("result","")).lower()
                    if result in ("yes","no"):
                        print(w.settle(result))
                except Exception as settle_error:
                    print("Prior market not settled/available yet:",str(settle_error))
            b=book(ticker)
            close=ts(m,now); left=max(0,int(close-now))
            action,conf,reason=decide(list(prices),b,left)
            print("\n"+datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")+" | "+str(m.get("title",ticker)))
            print("Market:",ticker,"| remaining %02d:%02d"%(left//60,left%60),"| BTC spot reference: $%.2f"%spot)
            print("UP bid/ask:",b["yes_bid"],"/",b["yes_ask"],"cents | DOWN bid/ask:",b["no_bid"],"/",b["no_ask"],"cents")
            print("AI-style decision:",action,"| heuristic confidence %.0f%%"%(conf*100),"|",reason)
            if not w.pos and action in ("UP","DOWN") and conf>=.62:
                print(w.enter(action,b["yes_ask"] if action=="UP" else b["no_ask"],ticker,reason,conf))
            equity=w.mark(b); print("Paper cash: %.4f | marked equity: %.4f | max drawdown: %.2f%%"%(w.cash,equity,w.maxdd*100))
            print("Position:",w.pos or "none")
            print("IMPORTANT: BTC spot is not the CF Benchmarks index used by Kalshi settlement.")
            if a.once: break
            time.sleep(max(3,a.poll))
        except KeyboardInterrupt: break
        except Exception as e:
            print("Data error:",str(e),"| retrying")
            if a.once: break
            time.sleep(max(3,a.poll))
    print("\nPaper summary:",json.dumps({"start":w.start,"cash":round(w.cash,4),"position":w.pos,"max_drawdown_pct":round(w.maxdd*100,3),"events":w.events,
        "limitations":["Transparent momentum heuristic, not trained or validated AI.","Spot reference differs from official contract settlement index.","Estimated fees; no true queue position or partial fills.","No real order route or account connection."]},indent=2))
if __name__=="__main__": main()
