# DESK PRO — Paper Trading Engine

A reproducible, **paper-only** OHLCV backtester. It starts with $10 virtual cash by default, generates decisions using a moving-average trend rule, and models commissions, slippage, delayed fills, stop-losses, partial take-profit exits, cash/position accounting, and drawdown limits.

## Requirements
Python 3.10+; no third-party packages required.

## Run immediately
```bash
python desk_pro.py
```
Runs a deterministic built-in demo dataset offline and writes `backtest_results.json`.

## Use historical candles
CSV headers: `timestamp,open,high,low,close` (timestamp optional).
```bash
python desk_pro.py --csv candles.csv --output results.json
```

## Tests
```bash
python -m unittest -v
```

## Strategy and defaults
- Fast 5-bar and slow 12-bar simple moving averages.
- Queues entries while the fast average is above the slow average; queues exits on reversal.
- Default fees: 0.10%; slippage: 0.05%; fill delay: one bar.
- Entry sizing is capped by available cash, a 25% equity allocation, and a 1% stop-risk budget.
- Default stop loss: 2%; take profit: 3%, requesting a partial exit.
- Drawdown limit: 20%; after a halt, new buys are blocked while sell orders remain eligible.

## Safety and limitations
- **Paper-only by design:** no broker API, wallet, exchange connection, live-order function, or credential handling.
- Synthetic demo prices are only to confirm execution, not evidence of profitability.
- Candle data cannot establish the exact order of intrabar stop/target events; delayed execution may materially change results.
- No order-book depth, queue position, market impact, exchange outages, or taxes are modeled.
- Historical results do not predict future performance. Use clean, realistic historical data and evaluate out-of-sample before drawing conclusions.
# DESK PRO — Browser Paper Trading Lab

**Runs in a web browser. No Python installation is required.** Open `index.html` on a computer or publish the repository with GitHub Pages.

## What it does
- Starts with **$10 in virtual cash**.
- Automatically generates demo candles and makes rule-based BUY / SELL / HOLD decisions.
- Uses EMA trend, RSI momentum filtering, and a breakout confirmation.
- Simulates per-side fees, slippage, delayed fills, position sizing, stop-losses, partial take-profit exits, and a drawdown circuit breaker.
- Displays simulated equity, drawdown, positions, execution journal, and trade history.
- Lets you start/pause the simulator, run one bar at a time, adjust risk settings, and reset the virtual account.

## Start now
1. Open `index.html` in a modern browser.
2. Press **Start auto** or **Run 1 bar**.
3. Review the execution journal and trade history.
4. Press **Reset $10** to restart the demo account.

To make a public web link, enable GitHub Pages in the repository settings and choose the `main` branch and `/(root)` folder if your repository/account supports Pages. Until Pages is enabled, the file can still be opened locally from a downloaded repository.

## Safety and limitations
- **Paper-only by design.** There is no broker API, exchange connection, wallet, real-money order route, or API-key collection.
- The built-in prices are randomly generated demo data, **not live prices** and not a valid test of market profitability.
- The strategy is a transparent rule-based simulator, not a trained AI model or a promise of profit.
- Delayed fills and costs are simplified; market depth, queue priority, outages, taxes, and realistic order-book liquidity are not modeled.
- Browser refreshes reset the session; this version does not promise persistent account storage.
- Use real historical candles and out-of-sample tests before interpreting any results. This is educational software, not financial advice.


## Live Kalshi-style 15-minute simulator (paper-only)

Run `python kalshi_live.py` to poll public Kalshi KXBTC15M market quotes and a public BTC spot reference. It starts with $10 virtual cash and prints UP / DOWN / NO TRADE decisions. Use `python kalshi_live.py --once` for a single update. It does not connect to an account or submit orders.

This is a transparent momentum heuristic, not a trained or validated AI. BTC spot is only a reference; Kalshi contract settlement follows its own stated index and averaging rules. Fees are estimates, and true queue position / partial fills are not represented. Keep the system paper-only.
