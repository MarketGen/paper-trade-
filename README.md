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
