"""
models/supply_zone.py
──────────────────────
Supply Zone model — used as Take Profit (TP) targets.

Supply zones are bearish OBs or bearish FVGs on higher timeframes.
For spot trading, they are the areas where price is likely to face
heavy selling pressure and reverse — ideal TP levels.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass
class SupplyZone:
    # ─── Identity ────────────────────────────────────────────────────────────
    symbol: str
    timeframe: str                               # "1h", "4h", "1d", "1w", "1M"
    timestamp: datetime

    # ─── Price Levels ────────────────────────────────────────────────────────
    high: float                                  # Top of supply zone
    low: float                                   # Bottom of supply zone

    # ─── Source ──────────────────────────────────────────────────────────────
    source: Literal["ob", "fvg", "swing_high"] = "ob"
    # ob         = bearish Order Block
    # fvg        = bearish Fair Value Gap
    # swing_high = major swing high acting as resistance

    # ─── State ───────────────────────────────────────────────────────────────
    is_active: bool = True
    is_tested: bool = False                      # Price has visited but not broken

    # ─── TP Context ──────────────────────────────────────────────────────────
    tp_priority: int = 1                         # 1 = nearest TP, 2 = next, etc.
    risk_reward_ratio: float = 0.0              # Calculated against entry zone

    # ─── Convenience ─────────────────────────────────────────────────────────
    @property
    def level(self) -> float:
        """Primary TP level — bottom of supply zone (conservative target)."""
        return self.low

    @property
    def extended_level(self) -> float:
        """Extended TP level — top of supply zone (aggressive target)."""
        return self.high

    @property
    def midpoint(self) -> float:
        return (self.high + self.low) / 2

    def distance_from_price(self, current_price: float) -> float:
        """% upside from current price to the bottom of this supply zone."""
        if current_price == 0:
            return 0.0
        return ((self.low - current_price) / current_price) * 100

    def __repr__(self):
        return (
            f"SupplyZone({self.symbol} {self.timeframe} [{self.source.upper()}] "
            f"TP @ {self.low:.4f}–{self.high:.4f} | TP#{self.tp_priority})"
        )
