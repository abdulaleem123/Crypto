"""
analysis/order_block_detector.py
──────────────────────────────────
CORRECTED Order Block detection.

═══════════════════════════════════════════════════════════════
CORRECT OB DEFINITION:
═══════════════════════════════════════════════════════════════
Bullish OB (demand zone — spot entry):
  → The LAST bearish (red) candle BEFORE a strong bullish impulse
    that breaks structure upward.
  → The OB zone = that bearish candle's [low, high]
  → Price must NOT have closed back below the OB low (still active)
  → For spot: only OBs BELOW current price are relevant

Bearish OB (supply zone — TP target):
  → The LAST bullish (green) candle BEFORE a strong bearish impulse
  → Only OBs ABOVE current price are relevant for TP

Impulse qualification:
  → Next candle body must be >= 1.5% of its open price
  → OR the move must break a recent swing high/low
═══════════════════════════════════════════════════════════════
"""

import pandas as pd
import numpy as np
from typing import List, Optional
from datetime import datetime
from loguru import logger

from models.order_block import OrderBlock
from data.timeframe_manager import TimeframeManager


class OrderBlockDetector:

    def __init__(
        self,
        impulse_threshold_pct: float = 1.5,
        lookback_candles: int = 5,
        max_obs_per_tf: int = 5,
    ):
        self.impulse_threshold_pct = impulse_threshold_pct
        self.lookback_candles = lookback_candles
        self.max_obs_per_tf = max_obs_per_tf

    def detect(
        self,
        symbol: str,
        df: pd.DataFrame,
        timeframe: str,
        current_price: float,
        ob_type: str = "bullish",
    ) -> List[OrderBlock]:
        if df is None or len(df) < self.lookback_candles + 3:
            return []

        obs: List[OrderBlock] = []
        if ob_type in ("bullish", "both"):
            obs.extend(self._detect_bullish_obs(symbol, df, timeframe, current_price))
        if ob_type in ("bearish", "both"):
            obs.extend(self._detect_bearish_obs(symbol, df, timeframe, current_price))

        obs.sort(key=lambda x: x.timestamp, reverse=True)
        return obs[:self.max_obs_per_tf]

    def detect_all_timeframes(
        self,
        symbol: str,
        ohlcv_data: dict,
        current_price: float,
        ob_type: str = "bullish",
    ) -> List[OrderBlock]:
        all_obs: List[OrderBlock] = []
        for tf, df in ohlcv_data.items():
            if not TimeframeManager.is_htf(tf):
                continue
            tf_obs = self.detect(symbol, df, tf, current_price, ob_type)
            all_obs.extend(tf_obs)
            logger.debug(f"{symbol} {tf}: {len(tf_obs)} {ob_type} OBs detected")
        return all_obs

    # ─── Private ─────────────────────────────────────────────────────────────

    def _detect_bullish_obs(self, symbol, df, timeframe, current_price) -> List[OrderBlock]:
        """
        Scan for bullish OBs: last red candle before strong green impulse.
        Only returns OBs whose zone is below current price.
        """
        obs = []
        candles = df.reset_index()
        n = len(candles)

        for i in range(self.lookback_candles, n - 2):
            impulse = candles.iloc[i + 1]

            # Must be a strong bullish impulse
            if not self._is_strong_bullish(impulse):
                continue

            # Find last bearish candle at or before index i
            ob_candle = None
            for j in range(i, max(i - self.lookback_candles, -1), -1):
                c = candles.iloc[j]
                if float(c["close"]) < float(c["open"]):
                    ob_candle = c
                    ob_idx = j
                    break

            if ob_candle is None:
                continue

            ob_high = float(ob_candle["high"])
            ob_low = float(ob_candle["low"])

            # OB zone must be below current price
            if ob_high >= current_price:
                continue

            # Check if OB is still active (no close below ob_low after it formed)
            is_active = self._check_active(candles, ob_idx + 1, ob_low, "bullish")

            ts = ob_candle.get("timestamp", datetime.utcnow())
            if hasattr(ts, 'to_pydatetime'):
                ts = ts.to_pydatetime()

            ob = OrderBlock(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=ts,
                high=ob_high,
                low=ob_low,
                open=float(ob_candle["open"]),
                close=float(ob_candle["close"]),
                ob_type="bullish",
                is_active=is_active,
                impulse_size_pct=self._body_pct(impulse),
                volume_at_ob=float(ob_candle.get("volume", 0)),
            )
            obs.append(ob)

        return obs

    def _detect_bearish_obs(self, symbol, df, timeframe, current_price) -> List[OrderBlock]:
        """
        Scan for bearish OBs: last green candle before strong red impulse.
        Only returns OBs whose zone is above current price (for TP).
        """
        obs = []
        candles = df.reset_index()
        n = len(candles)

        for i in range(self.lookback_candles, n - 2):
            impulse = candles.iloc[i + 1]

            if not self._is_strong_bearish(impulse):
                continue

            ob_candle = None
            ob_idx = i
            for j in range(i, max(i - self.lookback_candles, -1), -1):
                c = candles.iloc[j]
                if float(c["close"]) > float(c["open"]):
                    ob_candle = c
                    ob_idx = j
                    break

            if ob_candle is None:
                continue

            ob_high = float(ob_candle["high"])
            ob_low = float(ob_candle["low"])

            # OB zone must be above current price
            if ob_low <= current_price:
                continue

            is_active = self._check_active(candles, ob_idx + 1, ob_high, "bearish")

            ts = ob_candle.get("timestamp", datetime.utcnow())
            if hasattr(ts, 'to_pydatetime'):
                ts = ts.to_pydatetime()

            ob = OrderBlock(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=ts,
                high=ob_high,
                low=ob_low,
                open=float(ob_candle["open"]),
                close=float(ob_candle["close"]),
                ob_type="bearish",
                is_active=is_active,
                impulse_size_pct=self._body_pct(impulse),
                volume_at_ob=float(ob_candle.get("volume", 0)),
            )
            obs.append(ob)

        return obs

    def _is_strong_bullish(self, candle) -> bool:
        o, c = float(candle["open"]), float(candle["close"])
        if o == 0 or c <= o:
            return False
        return ((c - o) / o) * 100 >= self.impulse_threshold_pct

    def _is_strong_bearish(self, candle) -> bool:
        o, c = float(candle["open"]), float(candle["close"])
        if o == 0 or c >= o:
            return False
        return ((o - c) / o) * 100 >= self.impulse_threshold_pct

    def _body_pct(self, candle) -> float:
        o = float(candle["open"])
        if o == 0:
            return 0.0
        return abs(float(candle["close"]) - o) / o * 100

    def _check_active(self, candles, from_idx: int, level: float, ob_type: str) -> bool:
        """
        Returns True if no subsequent candle has CLOSED through the OB level.
        Bullish OB: invalid if any close < ob_low
        Bearish OB: invalid if any close > ob_high
        """
        for i in range(from_idx, len(candles)):
            close = float(candles.iloc[i]["close"])
            if ob_type == "bullish" and close < level:
                return False
            if ob_type == "bearish" and close > level:
                return False
        return True