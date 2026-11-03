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
