"""
models/fvg.py
─────────────
Fair Value Gap model — now includes midpoint (key buying zone).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass
class FairValueGap:
    symbol: str
    timeframe: str
    timestamp: datetime

    top: float          # Upper boundary
    bottom: float       # Lower boundary
    midpoint: float     # (top + bottom) / 2 — where big orders cluster

    fvg_type: Literal["bullish", "bearish"] = "bullish"

    is_filled: bool = False
    fill_pct: float = 0.0
    gap_size_pct: float = 0.0

    @property
    def size(self) -> float:
        return self.top - self.bottom

    def distance_to_price(self, current_price: float) -> float:
        """% distance from current price to nearest FVG edge. -1 = inside."""
        if current_price >= self.bottom and current_price <= self.top:
            return -1.0
        if current_price > self.top:
            return ((current_price - self.top) / self.top) * 100
        return ((self.bottom - current_price) / current_price) * 100

    def distance_to_midpoint(self, current_price: float) -> float:
        """% distance from current price to FVG midpoint."""
        if self.midpoint == 0:
            return 999.0
        return abs((current_price - self.midpoint) / self.midpoint) * 100

    def __repr__(self):
        return (
            f"FVG({self.symbol} {self.timeframe} {self.fvg_type.upper()} "
            f"{self.bottom:.6f}–{self.top:.6f} mid={self.midpoint:.6f} filled={self.is_filled})"
        )