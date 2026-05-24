# """
# models/token.py
# ───────────────
# Core Token dataclass that flows through the entire pipeline.
# """

# from dataclasses import dataclass, field
# from typing import List, Optional
# from models.order_block import OrderBlock
# from models.fvg import FairValueGap
# from models.supply_zone import SupplyZone


# @dataclass
# class Token:
#     # ─── Identity ────────────────────────────────────────────────────────────
#     symbol: str                          # e.g. "BTCUSDT"
#     base: str                            # e.g. "BTC"
#     quote: str                           # e.g. "USDT"
#     exchange: str                        # "binance" | "mexc" | "both"

#     # ─── Market Data ─────────────────────────────────────────────────────────
#     current_price: float = 0.0
#     volume_24h_usdt: float = 0.0
#     price_change_24h_pct: float = 0.0

#     # ─── Analysis Results ────────────────────────────────────────────────────
#     order_blocks: List[OrderBlock] = field(default_factory=list)
#     fvgs: List[FairValueGap] = field(default_factory=list)
#     supply_zones: List[SupplyZone] = field(default_factory=list)

#     # ─── Scoring & Ranking ───────────────────────────────────────────────────
#     proximity_score: float = 0.0         # 0-100, higher = closer to a zone
#     nearest_ob: Optional[OrderBlock] = None
#     nearest_fvg: Optional[FairValueGap] = None
#     nearest_supply: Optional[SupplyZone] = None

#     # ─── Flags ───────────────────────────────────────────────────────────────
#     is_mexc_only: bool = False           # True = small cap, only on MEXC
#     near_ob_zone: bool = False           # Within proximity threshold of OB
#     near_fvg_zone: bool = False          # Within proximity threshold of FVG

#     # ─── Display Helpers ─────────────────────────────────────────────────────
#     @property
#     def highlight_color(self) -> Optional[str]:
#         """Returns the highlight color for the dashboard row."""
#         if self.near_fvg_zone:
#             return "dark_green"
#         if self.near_ob_zone:
#             return "light_green"
#         return None

#     @property
#     def ob_summary(self) -> str:
#         """Short string showing active OB levels for table display."""
#         if not self.order_blocks:
#             return "—"
#         active = [ob for ob in self.order_blocks if ob.is_active]
#         if not active:
#             return "—"
#         lines = [f"[{ob.timeframe}] {ob.low:.4f}–{ob.high:.4f}" for ob in active[:3]]
#         return " | ".join(lines)

#     @property
#     def fvg_summary(self) -> str:
#         """Short string showing active FVG levels for table display."""
#         if not self.fvgs:
#             return "—"
#         active = [f for f in self.fvgs if not f.is_filled]
#         if not active:
#             return "—"
#         lines = [f"[{f.timeframe}] {f.bottom:.4f}–{f.top:.4f}" for f in active[:3]]
#         return " | ".join(lines)

#     @property
#     def tp_summary(self) -> str:
#         """Short string showing TP levels (supply zones) for table display."""
#         if not self.supply_zones:
#             return "—"
#         lines = [f"[{s.timeframe}] {s.level:.4f}" for s in self.supply_zones[:4]]
#         return " | ".join(lines)

#     def __repr__(self):
#         return (
#             f"Token({self.symbol} @ {self.current_price:.4f} | "
#             f"Score: {self.proximity_score:.1f} | "
#             f"OBs: {len(self.order_blocks)} | FVGs: {len(self.fvgs)})"
#         )



"""
models/token.py — includes near_zone_label e.g. "NEAR 1D OB"
"""

from dataclasses import dataclass, field
from typing import List, Optional
from models.order_block import OrderBlock
from models.fvg import FairValueGap
from models.supply_zone import SupplyZone


@dataclass
class Token:
    # Identity
    symbol: str
    base: str
    quote: str
    exchange: str

    # Market Data
    current_price: float = 0.0
    volume_24h_usdt: float = 0.0
    price_change_24h_pct: float = 0.0

    # Analysis Results
    order_blocks: List[OrderBlock] = field(default_factory=list)
    fvgs: List[FairValueGap] = field(default_factory=list)
    supply_zones: List[SupplyZone] = field(default_factory=list)

    # Scoring
    proximity_score: float = 0.0
    nearest_ob: Optional[OrderBlock] = None
    nearest_fvg: Optional[FairValueGap] = None
    nearest_supply: Optional[SupplyZone] = None

    # Flags
    is_mexc_only: bool = False
    near_ob_zone: bool = False
    near_fvg_zone: bool = False

    # Human-readable zone label e.g. "NEAR 1D OB", "NEAR 4H FVG"
    near_zone_label: str = "—"

    # Godzilla BTC prediction (only populated for BTCUSDT)
    godzilla_price: Optional[float] = None
    godzilla_direction: Optional[str] = None

    @property
    def highlight_color(self) -> Optional[str]:
        if self.near_fvg_zone:
            return "dark_green"
        if self.near_ob_zone:
            return "light_green"
        return None

    def __repr__(self):
        return (
            f"Token({self.symbol} @ {self.current_price:.4f} | "
            f"Score: {self.proximity_score:.1f} | Zone: {self.near_zone_label})"
        )