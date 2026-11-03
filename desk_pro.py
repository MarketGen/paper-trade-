#!/usr/bin/env python3
"""DESK PRO: deterministic, paper-only OHLCV backtester.

No broker clients, network calls, credentials, or live-order routes are implemented.
Input CSV columns: timestamp,open,high,low,close (volume optional).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Candle:
    timestamp: str
    open: float
    high: float
    low: float
    close: float


@dataclass
class Trade:
    timestamp: str
    side: str
    units: float
    price: float
    fee: float
    slippage: float
    reason: str
    realized_pnl: float = 0.0


@dataclass
class Config:
    starting_cash: float = 10.0
    fee_rate: float = 0.001
    slippage_rate: float = 0.0005
    fill_delay_bars: int = 1
    fast_window: int = 5
    slow_window: int = 12
    max_position_fraction: float = 0.25
    risk_fraction: float = 0.01
    stop_loss_fraction: float = 0.02
    take_profit_fraction: float = 0.03
    partial_exit_fraction: float = 0.5
    max_drawdown_fraction: float = 0.20
    min_order_value: float = 0.25


class PaperBacktester:
    def __init__(self, config: Config = Config()):
        if config.starting_cash <= 0:
            raise ValueError("starting_cash must be positive")
        if config.fast_window < 1 or config.slow_window <= config.fast_window:
            raise ValueError("slow_window must be greater than fast_window")
        if not 0 <= config.fee_rate < 1 or not 0 <= config.slippage_rate < 1:
            raise ValueError("fee and slippage rates must be between 0 and 1")
        if not 0 < config.max_position_fraction <= 1:
            raise ValueError("max_position_fraction must be in (0, 1]")
        self.cfg = config
        self.cash = config.starting_cash
        self.units = 0.0
        self.avg_entry = 0.0
        self.entry_fee_remaining = 0.0
        self.partial_taken = False
        self.pending: Optional[dict] = None
        self.trades: list[Trade] = []
        self.equity_curve: list[dict] = []
        self.peak_equity = config.starting_cash
        self.max_drawdown = 0.0
        self.halted = False
        self.realized_pnl = 0.0
        self.wins = 0
        self.losses = 0

    @staticmethod
    def _sma(values: list[float], window: int) -> Optional[float]:
        if len(values) < window:
            return None
        return sum(values[-window:]) / window

    def _equity(self, price: float) -> float:
        return self.cash + self.units * price

    def _queue(self, side: str, reason: str, bar_index: int, fraction: float = 1.0):
        if self.pending is None and not self.halted:
            self.pending = {"side": side, "reason": reason,
                            "execute_at": bar_index + self.cfg.fill_delay_bars,
                            "fraction": fraction}

    def _execute(self, candle: Candle):
        order, self.pending = self.pending, None
        if not order or self.halted:
            return
        side, reason = order["side"], order["reason"]
        raw_price = candle.open
        price = raw_price * (1 + self.cfg.slippage_rate if side == "BUY"
                             else 1 - self.cfg.slippage_rate)
        if price <= 0 or not math.isfinite(price):
            return
        if side == "BUY":
            equity = self._equity(price)
            cap = min(self.cash, equity * self.cfg.max_position_fraction)
            # Position size is bounded by both an equity allocation cap and a stop-risk budget.
            risk_budget = equity * self.cfg.risk_fraction
            stop_distance = price * self.cfg.stop_loss_fraction
            risk_units = risk_budget / stop_distance if stop_distance > 0 else 0
            units = min(cap / (price * (1 + self.cfg.fee_rate)),
                        risk_units)
            if units * price < self.cfg.min_order_value:
                return
            notional = units * price
            fee = notional * self.cfg.fee_rate
            total = notional + fee
            if total > self.cash:
                units = self.cash / (price * (1 + self.cfg.fee_rate))
                notional, fee, total = units * price, units * price * self.cfg.fee_rate, units * price * (1 + self.cfg.fee_rate)
            if units <= 0:
                return
            old_units = self.units
            self.avg_entry = ((self.avg_entry * old_units) + price * units) / (old_units + units) if old_units else price
            self.units += units
            self.cash -= total
            self.entry_fee_remaining += fee
            self.partial_taken = False
            self.trades.append(Trade(candle.timestamp, side, units, price, fee,
                                     abs(price - raw_price) * units, reason))
        elif side == "SELL" and self.units > 0:
            fraction = min(1.0, max(0.0, float(order.get("fraction", 1.0))))
            units = self.units * fraction
            if units <= 0:
                return
            notional = units * price
            fee = notional * self.cfg.fee_rate
            allocated_entry_fee = self.entry_fee_remaining * (units / self.units)
            pnl = (price - self.avg_entry) * units - fee - allocated_entry_fee
            self.cash += notional - fee
            self.units -= units
            self.entry_fee_remaining -= allocated_entry_fee
            self.realized_pnl += pnl
            if pnl > 0:
                self.wins += 1
            elif pnl < 0:
                self.losses += 1
            self.trades.append(Trade(candle.timestamp, side, units, price, fee,
                                     abs(price - raw_price) * units, reason, pnl))
            if self.units < 1e-12:
                self.units = 0.0
                self.avg_entry = 0.0
                self.entry_fee_remaining = 0.0
                self.partial_taken = False

    def run(self, candles: list[Candle]) -> dict:
        if not candles:
            raise ValueError("No candles supplied")
        closes: list[float] = []
        for i, candle in enumerate(candles):
            if not all(math.isfinite(x) and x > 0 for x in (candle.open, candle.high, candle.low, candle.close)):
                raise ValueError(f"Invalid OHLC price at row {i + 1}")
            if candle.high < max(candle.open, candle.close) or candle.low > min(candle.open, candle.close) or candle.low > candle.high:
                raise ValueError(f"Inconsistent OHLC values at row {i + 1}")

            # Orders queued on earlier bars execute at this bar's open, with slippage.
            if self.pending and i >= self.pending["execute_at"]:
                self._execute(candle)

            closes.append(candle.close)
            fast = self._sma(closes, self.cfg.fast_window)
            slow = self._sma(closes, self.cfg.slow_window)
            equity = self._equity(candle.close)
            self.peak_equity = max(self.peak_equity, equity)
            drawdown = (self.peak_equity - equity) / self.peak_equity if self.peak_equity else 0
            self.max_drawdown = max(self.max_drawdown, drawdown)
            if drawdown >= self.cfg.max_drawdown_fraction:
                self.halted = True
                self.pending = None
                if self.units > 0:
                    # Queue a risk exit; the halt blocks new buys, not this liquidation.
                    self.halted = False
                    self._queue("SELL", "drawdown_limit", i)
                    self.halted = True
            if self.units > 0:
                if candle.low <= self.avg_entry * (1 - self.cfg.stop_loss_fraction):
                    self._queue("SELL", "stop_loss", i)
                elif not self.partial_taken and candle.high >= self.avg_entry * (1 + self.cfg.take_profit_fraction):
                    self._queue("SELL", "partial_take_profit", i, self.cfg.partial_exit_fraction)
                    self.partial_taken = True
                elif fast is not None and slow is not None and fast < slow:
                    self._queue("SELL", "trend_reversal", i)
            elif not self.halted and fast is not None and slow is not None and fast > slow:
                self._queue("BUY", "moving_average_crossover_or_trend", i)

            self.equity_curve.append({"timestamp": candle.timestamp,
                                      "cash": round(self.cash, 8),
                                      "units": round(self.units, 10),
                                      "close": candle.close,
                                      "equity": round(self._equity(candle.close), 8),
                                      "drawdown": round(drawdown, 8),
                                      "decision": ("HALT" if self.halted else
                                                   self.pending["side"] if self.pending else
                                                   "HOLD")})
        # Cancel unfilled delayed order at end of dataset; do not invent a fill.
        self.pending = None
        final_price = candles[-1].close
        final_equity = self._equity(final_price)
        # Backtest reports unrealized holdings at mark-to-market; no forced final sale.
        return {
            "mode": "PAPER_ONLY",
            "starting_cash": self.cfg.starting_cash,
            "ending_cash": round(self.cash, 8),
            "ending_units": round(self.units, 10),
            "final_mark_price": final_price,
            "final_equity": round(final_equity, 8),
            "net_pnl": round(final_equity - self.cfg.starting_cash, 8),
            "return_pct": round((final_equity / self.cfg.starting_cash - 1) * 100, 4),
            "realized_pnl": round(self.realized_pnl, 8),
            "unrealized_pnl": round((final_price - self.avg_entry) * self.units if self.units else 0, 8),
            "max_drawdown_pct": round(self.max_drawdown * 100, 4),
            "trade_count": len(self.trades),
            "winning_exits": self.wins,
            "losing_exits": self.losses,
            "halted_by_drawdown": self.halted,
            "config": asdict(self.cfg),
            "trades": [asdict(t) for t in self.trades],
            "equity_curve": self.equity_curve,
            "limitations": [
                "Synthetic or supplied candles only; results depend on data quality.",
                "Delayed fills execute at a later bar open; intrabar stop/target order is ambiguous.",
                "No market impact, queue position, liquidity depth, exchange outages, or taxes.",
                "Moving-average strategy is illustrative, not a claim of profitability.",
                "This program contains no live-trading integration."
            ]
        }


def load_csv(path: str) -> list[Candle]:
    candles = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required = {"open", "high", "low", "close"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError("CSV must contain open, high, low, close columns; timestamp is optional")
        for i, row in enumerate(reader, start=2):
            try:
                candles.append(Candle(str(row.get("timestamp") or i),
                                      float(row["open"]), float(row["high"]),
                                      float(row["low"]), float(row["close"])))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid CSV row {i}: {exc}") from exc
    return candles


def demo_candles() -> list[Candle]:
    # Deterministic price series so first run works without external data or network access.
    prices = [100, 99, 98, 97, 96, 97, 98, 99, 101, 103, 105, 107,
              108, 106, 104, 102, 100, 98, 96, 95, 96, 98, 101, 104,
              107, 110, 112, 111, 109, 106, 103, 101, 102, 104, 107, 110]
    result = []
    for i, p in enumerate(prices):
        prev = prices[i - 1] if i else p
        o = prev
        result.append(Candle(str(i), o, max(o, p) * 1.002,
                             min(o, p) * 0.998, float(p)))
    return result


def main():
    parser = argparse.ArgumentParser(description="DESK PRO paper-only $10 backtester")
    parser.add_argument("--csv", help="OHLC CSV file; omit to run the built-in demo")
    parser.add_argument("--output", default="backtest_results.json", help="JSON output path")
    parser.add_argument("--cash", type=float, default=10.0, help="Starting virtual cash")
    args = parser.parse_args()
    cfg = Config(starting_cash=args.cash)
    candles = load_csv(args.csv) if args.csv else demo_candles()
    report = PaperBacktester(cfg).run(candles)
    Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    summary = {k: report[k] for k in (
        "mode", "starting_cash", "ending_cash", "final_equity", "net_pnl",
        "return_pct", "max_drawdown_pct", "trade_count", "halted_by_drawdown")}
    print(json.dumps(summary, indent=2))
    print(f"Full report: {args.output}")


if __name__ == "__main__":
    main()
