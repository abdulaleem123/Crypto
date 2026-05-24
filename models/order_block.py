"""
models/order_block.py
──────────────────────
Order Block data model.

An Order Block (OB) is the last bearish candle before a strong bullish impulse
(for a bullish/demand OB). It represents institutional order flow and acts as
a high-probability demand zone for spot entries.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass
class OrderBlock:
    # ─── Location ────────────────────────────────────────────────────────────
    symbol: str
    timeframe: str                           # "4h", "1d", "1w", "1M"
    timestamp: datetime                      # Candle open time of the OB

    # ─── Price Levels ────────────────────────────────────────────────────────
    high: float                              # Top of the OB candle
    low: float                               # Bottom of the OB candle
    open: float
    close: float

    # ─── Classification ──────────────────────────────────────────────────────
    ob_type: Literal["bullish", "bearish"] = "bullish"
    # bullish OB = demand zone (we look for buys here — spot strategy)
    # bearish OB = supply zone (acts as TP / resistance)

    # ─── State ───────────────────────────────────────────────────────────────
    is_active: bool = True                   # False if price has closed through it
    is_mitigated: bool = False               # True if price wicked into zone
    mitigation_pct: float = 0.0             # How deep price entered the zone (%)

    # ─── Strength Metrics ────────────────────────────────────────────────────
    impulse_size_pct: float = 0.0           # % move of the impulse that created OB
    volume_at_ob: float = 0.0               # Volume on the OB candle

    # ─── Convenience ─────────────────────────────────────────────────────────
    @property
    def midpoint(self) -> float:
        return (self.high + self.low) / 2

    @property
    def size_pct(self) -> float:
        """Size of the OB as % of its low."""
        if self.low == 0:
            return 0.0
        return ((self.high - self.low) / self.low) * 100

    def distance_to_price(self, current_price: float) -> float:
        """
        Returns % distance from current price to the nearest edge of the OB.
        Negative means price is already inside the OB.
        """
        if current_price >= self.low and current_price <= self.high:
            return -1.0  # inside the zone
        if current_price > self.high:
            return ((current_price - self.high) / self.high) * 100
        return ((self.low - current_price) / current_price) * 100

    def __repr__(self):
        return (
            f"OB({self.symbol} {self.timeframe} {self.ob_type.upper()} "
            f"{self.low:.4f}–{self.high:.4f} active={self.is_active})"
        )
