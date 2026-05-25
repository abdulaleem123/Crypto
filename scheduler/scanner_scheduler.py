"""
scheduler/scanner_scheduler.py
Streamlit Cloud compatible version — uses threading.Thread instead of
APScheduler BackgroundScheduler which dies on serverless platforms.
"""

import time
import threading
import numpy as np
from typing import List, Optional
from loguru import logger

from config import scanner_config
from models.token import Token
from exchanges.token_universe import TokenUniverse
from data.ohlcv_fetcher import OHLCVFetcher
from data.cache_manager import CacheManager
from analysis.order_block_detector import OrderBlockDetector
from analysis.fvg_detector import FVGDetector
from analysis.supply_zone_detector import SupplyZoneDetector
from analysis.proximity_checker import ProximityChecker
from analysis.scoring_engine import ScoringEngine
from notifications.whatsapp_notifier import WhatsAppNotifier


class ScannerScheduler:

    def __init__(self):
        self.universe = TokenUniverse()
        self.cache = CacheManager()
        self.fetcher = OHLCVFetcher(self.universe.binance, self.universe.mexc, self.cache)
        self.ob_detector = OrderBlockDetector()
        self.fvg_detector = FVGDetector()
        self.supply_detector = SupplyZoneDetector()
        self.proximity_checker = ProximityChecker()
        self.scoring_engine = ScoringEngine()
        self.notifier = WhatsAppNotifier()

        self.results: List[Token] = []
        self.last_scan_time: Optional[float] = None
        self.is_running: bool = False
        self.scan_count: int = 0
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self.godzilla_btc: dict = {
            "direction": None,
            "imbalance": None,
            "volatility": None,
            "spread": None,
            "max_leverage": None,
            "current_price": None,
        }

    def start(self) -> None:
        """Start the background scan loop in a daemon thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("Scanner thread started")

    def _loop(self) -> None:
        """Main loop: scan once, then repeat every scan_interval_minutes."""
        while not self._stop_event.is_set():
            try:
                self.run_scan()
            except Exception as e:
                logger.exception(f"Loop scan error: {e}")
            # Wait for next interval (check stop every 5s)
            interval = scanner_config.scan_interval_minutes * 60
            waited = 0
            while waited < interval and not self._stop_event.is_set():
                time.sleep(5)
                waited += 5

    def stop(self) -> None:
        self._stop_event.set()

    def refresh_live_prices(self) -> None:
        if not self.results:
            return
        for token in self.results:
            try:
                live = self.fetcher.fetch_live_price(token)
                if live and live > 0:
                    token.current_price = live
            except Exception:
                pass

    def run_scan(self) -> List[Token]:
        if self.is_running:
            return self.results

        self.is_running = True
        start_time = time.time()
        self.scan_count += 1
        logger.info(f"━━━ Scan #{self.scan_count} starting ━━━")

        try:
            tokens = self.universe.build()
            logger.info(f"Token universe: {len(tokens)} tokens")

            analyzed = []
            for i, token in enumerate(tokens):
                try:
                    live = self.fetcher.fetch_live_price(token)
                    if live and live > 0:
                        token.current_price = live

                    token = self._analyze_token(token)

                    if token.symbol == "BTCUSDT":
                        htf_data = self.fetcher.fetch_all_timeframes(token)
                        self._run_godzilla(token, htf_data)

                    analyzed.append(token)
                except Exception as e:
                    logger.error(f"Error analyzing {token.symbol}: {e}")
                    continue

                if (i + 1) % 10 == 0:
                    logger.info(f"Progress: {i+1}/{len(tokens)}")

            scored = self.scoring_engine.score_all(analyzed)
            self.results = scored
            self.last_scan_time = time.time()

            near = sum(1 for t in scored if t.near_ob_zone or t.near_fvg_zone)
            elapsed = time.time() - start_time
            logger.info(f"━━━ Scan #{self.scan_count} done in {elapsed:.1f}s | {near} near zones ━━━")

        except Exception as e:
            logger.exception(f"Scan failed: {e}")
        finally:
            self.is_running = False

        return self.results

    def _analyze_token(self, token: Token) -> Token:
        htf_data = self.fetcher.fetch_all_timeframes(token)
        tp_data = self.fetcher.fetch_tp_timeframes(token)
        token.order_blocks = self.ob_detector.detect_all_timeframes(
            token.symbol, htf_data, token.current_price, ob_type="bullish"
        )
        token.fvgs = self.fvg_detector.detect_all_timeframes(
            token.symbol, htf_data, token.current_price, fvg_type="bullish"
        )
        token.supply_zones = self.supply_detector.detect(
            token.symbol, tp_data, token.current_price
        )
        token = self.proximity_checker.check_token(token)
        return token

    def _run_godzilla(self, token: Token, htf_data: dict) -> None:
        try:
            df = htf_data.get("4h") or htf_data.get("1d")
            if df is None or df.empty or len(df) < 20:
                return

            closes  = df["close"].astype(float).values
            highs   = df["high"].astype(float).values
            lows    = df["low"].astype(float).values
            volumes = df["volume"].astype(float).values

            P_t = float(closes[-1])
            log_returns = np.diff(np.log(closes[-21:]))
            sigma_t = float(np.std(log_returns))

            opens_last  = df["open"].astype(float).values[-10:]
            closes_last = closes[-10:]
            vols_last   = volumes[-10:]

            v_bid = float(np.sum(vols_last[closes_last >= opens_last]))
            v_ask = float(np.sum(vols_last[closes_last < opens_last]))

            denom = v_bid + v_ask
            I_t   = (v_bid - v_ask) / denom if denom > 0 else 0.0

            S_t   = float(highs[-1]) - float(lows[-1])
            phi_t = S_t / P_t if P_t > 0 else 0.0

            vol_scalar   = 1.0 / (1.0 + sigma_t * 100)
            max_leverage = max(1.0, min((1.0 + phi_t) * vol_scalar, 20.0))
            direction    = "LONG" if I_t > 0 else "SHORT"

            self.godzilla_btc = {
                "direction":     direction,
                "imbalance":     round(I_t, 6),
                "volatility":    round(sigma_t, 6),
                "spread":        round(phi_t, 6),
                "max_leverage":  round(max_leverage, 2),
                "current_price": P_t,
                "v_bid":         round(v_bid, 2),
                "v_ask":         round(v_ask, 2),
            }
            token.godzilla_price     = P_t
            token.godzilla_direction = direction

        except Exception as e:
            logger.error(f"Godzilla calculation error: {e}")

    @property
    def status(self) -> dict:
        import datetime
        last_scan = (
            datetime.datetime.fromtimestamp(self.last_scan_time).strftime("%H:%M:%S")
            if self.last_scan_time else "Never"
        )
        return {
            "scan_count":       self.scan_count,
            "last_scan":        last_scan,
            "is_running":       self.is_running,
            "total_tokens":     len(self.results),
            "near_zone_tokens": sum(1 for t in self.results if t.near_ob_zone or t.near_fvg_zone),
            "cache_stats":      self.cache.stats(),
            "godzilla":         self.godzilla_btc,
        }