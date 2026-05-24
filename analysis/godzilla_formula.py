"""
analysis/godzilla_formula.py
─────────────────────────────
Godzilla Bitcoin Price Prediction Formula

Formula from image:
  I_t = (V_bid - V_ask) / (V_bid + V_ask)

  Where:
    V_bid = top few levels total bid volume
    V_ask = top few levels total ask volume
    I_t > 0 → buyers heavier → LONG pressure
    I_t < 0 → sellers heavier → SHORT pressure

  Max Leverage = 1 + e^(-1.0)  [fixed as per formula]

  Volatility:
    High volatility → leverage kam (lower)
    Low volatility  → leverage zyada (higher)

  Predicted price direction:
    Sign of I_t (plus = LONG, minus = SHORT)

  We estimate V_bid / V_ask from recent candle data:
    V_bid ≈ volume on bullish candles (buyers)
    V_ask ≈ volume on bearish candles (sellers)

  For price target we use:
    predicted_price = current_price * (1 + I_t * volatility_factor)
"""

import math
import numpy as np
import pandas as pd
from typing import Optional, Tuple
from loguru import logger


class GodzillaFormula:
    """
    Calculates the Godzilla predicted price for a token
    using order flow imbalance + volatility.
    """

    def __init__(self, lookback: int = 20):
        self.lookback = lookback  # candles to look back for volume analysis

    def calculate(
        self,
        symbol: str,
        current_price: float,
        ohlcv_data: dict,
        preferred_tf: str = "1d",
    ) -> Tuple[float, str, float]:
        """
        Run the Godzilla formula.

        Returns:
            (predicted_price, direction, imbalance_score)
            direction = "LONG" or "SHORT"
            imbalance_score = I_t value (-1 to +1)
        """
        # Use daily candles for calculation, fallback to 4h
        df = ohlcv_data.get(preferred_tf) or ohlcv_data.get("4h") or ohlcv_data.get("1d")

        if df is None or len(df) < 5:
            return current_price, "—", 0.0

        try:
            recent = df.tail(self.lookback).copy()

            # ── Step 1: Calculate V_bid and V_ask ────────────────────────────
            # V_bid = volume on candles where close > open (buyers won)
            # V_ask = volume on candles where close < open (sellers won)
            bull_mask = recent["close"] > recent["open"]
            bear_mask = recent["close"] < recent["open"]

            v_bid = float(recent.loc[bull_mask, "volume"].sum())
            v_ask = float(recent.loc[bear_mask, "volume"].sum())

            total_vol = v_bid + v_ask
            if total_vol == 0:
                return current_price, "—", 0.0

            # ── Step 2: Imbalance ratio I_t ───────────────────────────────────
            I_t = (v_bid - v_ask) / total_vol  # Range: -1 to +1

            # ── Step 3: Volatility (σ) using std of returns ───────────────────
            returns = recent["close"].pct_change().dropna()
            sigma = float(returns.std()) if len(returns) > 1 else 0.01
            sigma = max(sigma, 0.001)  # Floor to avoid zero

            # ── Step 4: Max Leverage cap = 1 + e^(-1) ≈ 1.368 ───────────────
            max_leverage = 1 + math.exp(-1.0)

            # Volatility adjustment: high vol = less leverage
            # leverage = max_leverage / (1 + sigma * 10)
            adjusted_leverage = max_leverage / (1 + sigma * 10)
            adjusted_leverage = max(adjusted_leverage, 0.1)

            # ── Step 5: Predicted price move ─────────────────────────────────
            # price_change = I_t * sigma * adjusted_leverage
            price_change_pct = I_t * sigma * adjusted_leverage

            predicted_price = current_price * (1 + price_change_pct)

            # Direction
            direction = "LONG 🟢" if I_t > 0.05 else ("SHORT 🔴" if I_t < -0.05 else "NEUTRAL ⚪")

            logger.debug(
                f"Godzilla [{symbol}]: I_t={I_t:.3f} σ={sigma:.4f} "
                f"lev={adjusted_leverage:.2f} pred={predicted_price:.6f} {direction}"
            )

            return predicted_price, direction, round(I_t, 4)

        except Exception as e:
            logger.debug(f"Godzilla calc failed {symbol}: {e}")
            return current_price, "—", 0.0