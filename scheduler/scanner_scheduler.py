# """
# scheduler/scanner_scheduler.py
# ────────────────────────────────
# Full scan pipeline with live price refresh.
# """

# import time
# import pandas as pd
# from typing import List, Optional
# from loguru import logger
# from apscheduler.schedulers.background import BackgroundScheduler
# from apscheduler.triggers.interval import IntervalTrigger

# from config import scanner_config, notification_config
# from models.token import Token
# from exchanges.token_universe import TokenUniverse
# from data.ohlcv_fetcher import OHLCVFetcher
# from data.cache_manager import CacheManager
# from analysis.order_block_detector import OrderBlockDetector
# from analysis.fvg_detector import FVGDetector
# from analysis.supply_zone_detector import SupplyZoneDetector
# from analysis.proximity_checker import ProximityChecker
# from analysis.scoring_engine import ScoringEngine
# from notifications.whatsapp_notifier import WhatsAppNotifier


# class ScannerScheduler:

#     def __init__(self):
#         self.universe = TokenUniverse()
#         self.cache = CacheManager()
#         self.fetcher = OHLCVFetcher(
#             self.universe.binance,
#             self.universe.mexc,
#             self.cache,
#         )
#         self.ob_detector = OrderBlockDetector()
#         self.fvg_detector = FVGDetector()
#         self.supply_detector = SupplyZoneDetector()
#         self.proximity_checker = ProximityChecker()
#         self.scoring_engine = ScoringEngine()
#         self.notifier = WhatsAppNotifier()

#         self.results: List[Token] = []
#         self.last_scan_time: Optional[float] = None
#         self.is_running: bool = False
#         self.scan_count: int = 0
#         self.scheduler = BackgroundScheduler()

#     def start(self) -> None:
#         logger.info(f"Starting scanner — interval: {scanner_config.scan_interval_minutes} min")
#         self.run_scan()
#         self.scheduler.add_job(
#             self.run_scan,
#             trigger=IntervalTrigger(minutes=scanner_config.scan_interval_minutes),
#             id="full_scan",
#             replace_existing=True,
#         )
#         # Separate job: refresh live prices every 30 seconds
#         self.scheduler.add_job(
#             self.refresh_live_prices,
#             trigger=IntervalTrigger(seconds=30),
#             id="price_refresh",
#             replace_existing=True,
#         )
#         self.scheduler.start()
#         logger.info("Scanner scheduler started")

#     def stop(self) -> None:
#         self.scheduler.shutdown(wait=False)
#         logger.info("Scanner scheduler stopped")

#     def refresh_live_prices(self) -> None:
#         """
#         Refresh current prices for all tokens every 30 seconds.
#         Does NOT re-run OB/FVG analysis — just updates prices.
#         """
#         if not self.results:
#             return
#         logger.info(f"Refreshing live prices for {len(self.results)} tokens...")
#         for token in self.results:
#             try:
#                 live_price = self.fetcher.fetch_live_price(token)
#                 if live_price and live_price > 0:
#                     token.current_price = live_price
#             except Exception as e:
#                 logger.debug(f"Price refresh failed {token.symbol}: {e}")
#         logger.info("Live prices refreshed")

#     def run_scan(self) -> List[Token]:
#         if self.is_running:
#             logger.warning("Scan already in progress — skipping")
#             return self.results

#         self.is_running = True
#         start_time = time.time()
#         self.scan_count += 1
#         logger.info(f"━━━ Scan #{self.scan_count} starting ━━━")

#         try:
#             tokens = self.universe.build()
#             logger.info(f"Token universe: {len(tokens)} tokens")

#             analyzed_tokens = []
#             for i, token in enumerate(tokens):
#                 try:
#                     # Always get live price first
#                     live_price = self.fetcher.fetch_live_price(token)
#                     if live_price and live_price > 0:
#                         token.current_price = live_price

#                     token = self._analyze_token(token)
#                     analyzed_tokens.append(token)
#                 except Exception as e:
#                     logger.error(f"Error analyzing {token.symbol}: {e}")
#                     continue

#                 if (i + 1) % 10 == 0:
#                     logger.info(f"Progress: {i+1}/{len(tokens)} tokens analyzed")

#             scored_tokens = self.scoring_engine.score_all(analyzed_tokens)
#             self.results = scored_tokens

#             alert_count = 0
#             for token in scored_tokens:
#                 if self.notifier.should_alert(token):
#                     self.notifier.send_zone_alert(token)
#                     alert_count += 1
#                     if alert_count >= 5:
#                         break

#             near_zone_tokens = [t for t in scored_tokens if t.near_ob_zone or t.near_fvg_zone]
#             if near_zone_tokens and self.scan_count % 4 == 0:
#                 self.notifier.send_summary(near_zone_tokens[:5])

#             elapsed = time.time() - start_time
#             self.last_scan_time = time.time()
#             logger.info(
#                 f"━━━ Scan #{self.scan_count} complete in {elapsed:.1f}s | "
#                 f"{len(near_zone_tokens)} tokens near zones | "
#                 f"{alert_count} alerts sent ━━━"
#             )

#         except Exception as e:
#             logger.exception(f"Scan #{self.scan_count} failed: {e}")
#         finally:
#             self.is_running = False

#         return self.results

#     def _analyze_token(self, token: Token) -> Token:
#         htf_data = self.fetcher.fetch_all_timeframes(token)
#         tp_data = self.fetcher.fetch_tp_timeframes(token)

#         token.order_blocks = self.ob_detector.detect_all_timeframes(
#             token.symbol, htf_data, token.current_price, ob_type="bullish"
#         )
#         token.fvgs = self.fvg_detector.detect_all_timeframes(
#             token.symbol, htf_data, token.current_price, fvg_type="bullish"
#         )
#         token.supply_zones = self.supply_detector.detect(
#             token.symbol, tp_data, token.current_price
#         )
#         token = self.proximity_checker.check_token(token)
#         return token

#     @property
#     def status(self) -> dict:
#         import datetime
#         last_scan = (
#             datetime.datetime.fromtimestamp(self.last_scan_time).strftime("%H:%M:%S")
#             if self.last_scan_time else "Never"
#         )
#         return {
#             "scan_count": self.scan_count,
#             "last_scan": last_scan,
#             "is_running": self.is_running,
#             "total_tokens": len(self.results),
#             "near_zone_tokens": sum(
#                 1 for t in self.results if t.near_ob_zone or t.near_fvg_zone
#             ),
#             "cache_stats": self.cache.stats(),
#         }


"""
scheduler/scanner_scheduler.py
Godzilla Crypto Leverage Formula applied ONLY to BTCUSDT.
Formula from image:
  - I_t = (V_bid - V_ask) / (V_bid + V_ask)  → direction indicator
  - sigma_t = sqrt(forecasted variance) via ARCH/GARCH proxy
  - phi_t = S_t / P_t = relative spread
  - Max Leverage = 1 + phi_t * 1.0
  - High volatility → lower leverage, Low volatility → higher leverage allowed
"""

import time
import numpy as np
from typing import List, Optional
from loguru import logger
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

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
        self.scheduler = BackgroundScheduler()

        # Godzilla BTC-only results
        self.godzilla_btc: dict = {
            "direction": None,       # "LONG" or "SHORT"
            "imbalance": None,       # I_t value
            "volatility": None,      # sigma_t
            "spread": None,          # phi_t
            "max_leverage": None,    # max leverage allowed
            "current_price": None,
        }

    def start(self) -> None:
        logger.info(f"Starting scanner — interval: {scanner_config.scan_interval_minutes} min")
        self.run_scan()
        self.scheduler.add_job(
            self.run_scan,
            trigger=IntervalTrigger(minutes=scanner_config.scan_interval_minutes),
            id="full_scan", replace_existing=True,
        )
        self.scheduler.add_job(
            self.refresh_live_prices,
            trigger=IntervalTrigger(seconds=30),
            id="price_refresh", replace_existing=True,
        )
        self.scheduler.start()

    def stop(self) -> None:
        self.scheduler.shutdown(wait=False)

    def refresh_live_prices(self) -> None:
        """Refresh live prices every 30s without re-running full analysis."""
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
                    # Always get fresh live price
                    live = self.fetcher.fetch_live_price(token)
                    if live and live > 0:
                        token.current_price = live

                    # Standard OB/FVG analysis for ALL tokens
                    token = self._analyze_token(token)

                    # ── Godzilla formula — BTCUSDT ONLY ──────────────────────
                    if token.symbol == "BTCUSDT":
                        htf_data = self.fetcher.fetch_all_timeframes(token)
                        self._run_godzilla(token, htf_data)
                        logger.info(
                            f"🦖 Godzilla BTC: {self.godzilla_btc['direction']} | "
                            f"I_t={self.godzilla_btc['imbalance']:.4f} | "
                            f"σ={self.godzilla_btc['volatility']:.4f} | "
                            f"MaxLev={self.godzilla_btc['max_leverage']:.2f}x"
                        )

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
        """Standard HTF OB + FVG analysis for any token."""
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
        """
        Godzilla Crypto Leverage Formula for BTCUSDT only.

        Variables (from formula image):
          P_t  = current mid-price
          σ_t  = sqrt(forecasted variance) — proxied via rolling std of returns
          V_bid = top few levels bid volume (proxied via up-candle volume)
          V_ask = top few levels ask volume (proxied via down-candle volume)
          S_t  = Ask - Bid spread (proxied via high - low of last candle)
          φ_t  = S_t / P_t = relative spread

          I_t = (V_bid - V_ask) / (V_bid + V_ask)
            > 0 → buyers heavier → LONG
            < 0 → sellers heavier → SHORT

          Max Leverage = 1 + φ_t * 1.0
          High volatility → kam (less leverage)
          Low volatility  → zyada (more leverage allowed)
        """
        try:
            # Use 4H candles for Godzilla calculation
            df = htf_data.get("4h") or htf_data.get("1d")
            if df is None or df.empty or len(df) < 20:
                return

            closes = df["close"].astype(float).values
            highs = df["high"].astype(float).values
            lows = df["low"].astype(float).values
            volumes = df["volume"].astype(float).values

            P_t = float(closes[-1])  # Current mid-price

            # ── σ_t: Forecasted volatility via rolling std of log returns ────
            log_returns = np.diff(np.log(closes[-21:]))  # last 20 returns
            sigma_t = float(np.std(log_returns))  # GARCH proxy

            # ── V_bid / V_ask: Proxy via bullish vs bearish candle volumes ───
            # Last 10 candles
            opens_last = df["open"].astype(float).values[-10:]
            closes_last = closes[-10:]
            vols_last = volumes[-10:]

            v_bid = float(np.sum(vols_last[closes_last >= opens_last]))  # up candle vol
            v_ask = float(np.sum(vols_last[closes_last < opens_last]))   # down candle vol

            # ── I_t: Order flow imbalance ─────────────────────────────────────
            denom = v_bid + v_ask
            I_t = (v_bid - v_ask) / denom if denom > 0 else 0.0

            # ── φ_t: Relative spread ─────────────────────────────────────────
            last_high = float(highs[-1])
            last_low = float(lows[-1])
            S_t = last_high - last_low                    # bid-ask spread proxy
            phi_t = S_t / P_t if P_t > 0 else 0.0

            # ── Max Leverage ─────────────────────────────────────────────────
            # Base: 1 + phi_t
            # Volatility adjustment: high vol → reduce leverage
            vol_scalar = 1.0 / (1.0 + sigma_t * 100)    # scale sigma to %
            max_leverage = (1.0 + phi_t) * vol_scalar
            max_leverage = max(1.0, min(max_leverage, 20.0))  # cap 1x–20x

            # ── Direction ────────────────────────────────────────────────────
            direction = "LONG" if I_t > 0 else "SHORT"

            # Store results
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

            # Also store on the token itself
            token.godzilla_price = P_t
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
            "scan_count": self.scan_count,
            "last_scan": last_scan,
            "is_running": self.is_running,
            "total_tokens": len(self.results),
            "near_zone_tokens": sum(1 for t in self.results if t.near_ob_zone or t.near_fvg_zone),
            "cache_stats": self.cache.stats(),
            "godzilla": self.godzilla_btc,
        }