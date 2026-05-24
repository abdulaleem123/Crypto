"""
analysis/fvg_detector.py
─────────────────────────
CORRECTED FVG Detection - Proper 3-candle imbalance logic.

═══════════════════════════════════════════════════════════════
CORRECT FVG DEFINITION:
═══════════════════════════════════════════════════════════════
Given 3 consecutive candles: A, B, C

Bullish FVG (demand imbalance):
  - C.low > A.high  → gap between A.high and C.low
  - B is usually a strong bullish candle
  - Midpoint = (A.high + C.low) / 2  ← where big buy orders sit
  - Zone is BELOW current price (unfilled demand)

Bearish FVG (supply imbalance):
  - C.high < A.low  → gap between C.high and A.low
  - B is usually a strong bearish candle
  - Midpoint = (A.low + C.high) / 2  ← where big sell orders sit
  - Zone is ABOVE current price (unfilled supply)

For Weekly/Monthly: we look at the candle bodies (open/close)
not just wicks for more reliable HTF gaps.
═══════════════════════════════════════════════════════════════
"""

import pandas as pd
from typing import List
from datetime import datetime
from loguru import logger

from models.fvg import FairValueGap
from data.timeframe_manager import TimeframeManager


class FVGDetector:

    def __init__(
        self,
        min_gap_pct: float = 0.15,     # Min gap size % — filters noise
        max_fvgs_per_tf: int = 5,
    ):
        self.min_gap_pct = min_gap_pct
        self.max_fvgs_per_tf = max_fvgs_per_tf

    def detect(
        self,
        symbol: str,
        df: pd.DataFrame,
        timeframe: str,
        current_price: float,
        fvg_type: str = "bullish",
    ) -> List[FairValueGap]:
        if df is None or len(df) < 3:
            return []

        fvgs: List[FairValueGap] = []
        candles = df.reset_index()

        # For HTF (weekly/monthly) use stricter body-based detection
        use_body = timeframe in ("1w", "1M")

        for i in range(1, len(candles) - 1):
            A = candles.iloc[i - 1]   # First candle
            B = candles.iloc[i]       # Middle candle (the impulse)
            C = candles.iloc[i + 1]   # Third candle

            ts = B.get("timestamp", datetime.utcnow())
            if hasattr(ts, 'to_pydatetime'):
                ts = ts.to_pydatetime()

            if fvg_type in ("bullish", "both"):
                fvg = self._check_bullish_fvg(
                    symbol, timeframe, ts, A, B, C, current_price, use_body
                )
                if fvg:
                    fvgs.append(fvg)

            if fvg_type in ("bearish", "both"):
                fvg = self._check_bearish_fvg(
                    symbol, timeframe, ts, A, B, C, current_price, use_body
                )
                if fvg:
                    fvgs.append(fvg)

        # Update fill status for each detected FVG
        for fvg in fvgs:
            self._update_fill_status(fvg, current_price)

        # Remove fully filled FVGs
        fvgs = [f for f in fvgs if not f.is_filled]

        # Sort newest first, cap
        fvgs.sort(key=lambda x: x.timestamp, reverse=True)
        return fvgs[:self.max_fvgs_per_tf]

    def detect_all_timeframes(
        self,
        symbol: str,
        ohlcv_data: dict,
        current_price: float,
        fvg_type: str = "bullish",
    ) -> List[FairValueGap]:
        all_fvgs: List[FairValueGap] = []
        for tf, df in ohlcv_data.items():
            if not TimeframeManager.is_htf(tf):
                continue
            tf_fvgs = self.detect(symbol, df, tf, current_price, fvg_type)
            all_fvgs.extend(tf_fvgs)
            logger.debug(f"{symbol} {tf}: {len(tf_fvgs)} {fvg_type} FVGs detected")
        return all_fvgs

    # ─── Core Detection Logic ─────────────────────────────────────────────────

    def _check_bullish_fvg(self, symbol, timeframe, ts, A, B, C, current_price, use_body):
        """
        Bullish FVG: gap between A.high and C.low (C.low > A.high).
        For HTF: also check body gap (max(A.open,A.close) vs min(C.open,C.close)).
        FVG must be BELOW current price (demand zone).
        """
        a_high = float(A["high"])
        c_low = float(C["low"])

        # Standard wick-based FVG
        bottom = a_high
        top = c_low

        if use_body:
            # For weekly/monthly also check body-based gap (more reliable)
            a_body_top = max(float(A["open"]), float(A["close"]))
            c_body_bot = min(float(C["open"]), float(C["close"]))
            if c_body_bot > a_body_top:
                # Use body gap if it's larger
                if (c_body_bot - a_body_top) > (top - bottom):
                    bottom = a_body_top
                    top = c_body_bot

        if top <= bottom:
            return None  # No gap

        gap_size_pct = ((top - bottom) / bottom) * 100
        if gap_size_pct < self.min_gap_pct:
            return None  # Too small

        # Must be below current price to be a demand/entry zone
        if top >= current_price:
            return None

        # Middle candle should be bullish (confirms momentum)
        b_bullish = float(B["close"]) > float(B["open"])
        if not b_bullish:
            return None

        midpoint = (bottom + top) / 2

        return FairValueGap(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=ts,
            top=top,
            bottom=bottom,
            midpoint=midpoint,
            fvg_type="bullish",
            gap_size_pct=gap_size_pct,
        )

    def _check_bearish_fvg(self, symbol, timeframe, ts, A, B, C, current_price, use_body):
        """
        Bearish FVG: gap between C.high and A.low (C.high < A.low).
        FVG must be ABOVE current price (supply zone / TP target).
        """
        a_low = float(A["low"])
        c_high = float(C["high"])

        bottom = c_high
        top = a_low

        if use_body:
            a_body_bot = min(float(A["open"]), float(A["close"]))
            c_body_top = max(float(C["open"]), float(C["close"]))
            if a_body_bot > c_body_top:
                if (a_body_bot - c_body_top) > (top - bottom):
                    bottom = c_body_top
                    top = a_body_bot

        if top <= bottom:
            return None

        gap_size_pct = ((top - bottom) / bottom) * 100
        if gap_size_pct < self.min_gap_pct:
            return None

        # Must be above current price (supply / TP zone)
        if bottom <= current_price:
            return None

        # Middle candle should be bearish
        b_bearish = float(B["close"]) < float(B["open"])
        if not b_bearish:
            return None

        midpoint = (bottom + top) / 2

        return FairValueGap(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=ts,
            top=top,
            bottom=bottom,
            midpoint=midpoint,
            fvg_type="bearish",
            gap_size_pct=gap_size_pct,
        )

    def _update_fill_status(self, fvg: FairValueGap, current_price: float) -> None:
        """
        Check if FVG has been filled based on current price.
        A bullish FVG is filled when price drops to or below its bottom.
        A bearish FVG is filled when price rises to or above its top.
        """
        if fvg.fvg_type == "bullish":
            if current_price <= fvg.bottom:
                fvg.is_filled = True
                fvg.fill_pct = 100.0
            elif current_price < fvg.top:
                # Price is inside the FVG — partially entered
                penetration = fvg.top - current_price
                gap_size = fvg.top - fvg.bottom
                fvg.fill_pct = (penetration / gap_size) * 100 if gap_size > 0 else 0
            else:
                fvg.fill_pct = 0.0

        elif fvg.fvg_type == "bearish":
            if current_price >= fvg.top:
                fvg.is_filled = True
                fvg.fill_pct = 100.0
            elif current_price > fvg.bottom:
                penetration = current_price - fvg.bottom
                gap_size = fvg.top - fvg.bottom
                fvg.fill_pct = (penetration / gap_size) * 100 if gap_size > 0 else 0
            else:
                fvg.fill_pct = 0.0