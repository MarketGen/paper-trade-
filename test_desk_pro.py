import unittest
from desk_pro import Candle, Config, PaperBacktester, demo_candles


class PaperBacktesterTests(unittest.TestCase):
    def test_starts_with_ten_dollars_and_stays_paper_only(self):
        report = PaperBacktester(Config()).run(demo_candles())
        self.assertEqual(report["mode"], "PAPER_ONLY")
        self.assertEqual(report["starting_cash"], 10.0)
        self.assertTrue(all(t["side"] in {"BUY", "SELL"} for t in report["trades"]))
        self.assertGreaterEqual(report["ending_cash"], -1e-8)

    def test_empty_data_rejected(self):
        with self.assertRaises(ValueError):
            PaperBacktester().run([])

    def test_bad_ohlc_rejected(self):
        candles = [Candle("bad", 10, 9, 8, 10)]
        with self.assertRaises(ValueError):
            PaperBacktester().run(candles)

    def test_delay_does_not_fill_on_same_bar(self):
        cfg = Config(fast_window=2, slow_window=3, fill_delay_bars=1)
        bt = PaperBacktester(cfg)
        report = bt.run(demo_candles())
        self.assertEqual(len(report["equity_curve"]), len(demo_candles()))
        self.assertTrue(all(t["timestamp"] != "0" for t in report["trades"]))

    def test_no_negative_units(self):
        report = PaperBacktester().run(demo_candles())
        self.assertGreaterEqual(report["ending_units"], 0)


if __name__ == "__main__":
    unittest.main()
