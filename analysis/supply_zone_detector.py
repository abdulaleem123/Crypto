# """
# analysis/supply_zone_detector.py
# ──────────────────────────────────
# Detects supply zones to use as Take Profit (TP) targets.

# Supply zones are identified as:
#   1. Bearish Order Blocks (OBs) above current price
#   2. Bearish FVGs above current price
#   3. Major swing highs (structural resistance)

# TP levels are sorted from nearest to farthest from current price,
# and labeled TP1, TP2, TP3... for easy dashboard display.
# """

# import pandas as pd
# from typing import List, Dict
# from loguru import logger

# from models.supply_zone import SupplyZone
# from models.order_block import OrderBlock
# from models.fvg import FairValueGap
# from analysis.order_block_detector import OrderBlockDetector
# from analysis.fvg_detector import FVGDetector
# from data.timeframe_manager import TimeframeManager


# class SupplyZoneDetector:
#     """
#     Aggregates all supply zones above current price for TP calculation.
#     Covers timeframes from 1H up to Monthly.
#     """

#     def __init__(self):
#         self.ob_detector = OrderBlockDetector()
#         self.fvg_detector = FVGDetector()

#     def detect(
#         self,
#         symbol: str,
#         ohlcv_data: Dict[str, pd.DataFrame],
#         current_price: float,
#         max_tp_levels: int = 5,
#     ) -> List[SupplyZone]:
#         """
#         Find all supply zones above current price across all timeframes.

#         Args:
#             symbol:         Token symbol
#             ohlcv_data:     Dict of {timeframe: DataFrame} including 1H
#             current_price:  Current token price
#             max_tp_levels:  Max number of TP levels to return

#         Returns:
#             List of SupplyZone sorted by proximity (nearest TP first)
#         """
#         supply_zones: List[SupplyZone] = []

#         for tf, df in ohlcv_data.items():
#             if df is None or df.empty:
#                 continue

#             # Detect bearish OBs (supply) on this timeframe
#             ob_supplies = self.ob_detector.detect(
#                 symbol, df, tf, current_price, ob_type="bearish"
#             )
#             for ob in ob_supplies:
#                 if ob.low > current_price and ob.is_active:
#                     sz = self._ob_to_supply_zone(ob, tf)
#                     supply_zones.append(sz)

#             # Detect bearish FVGs (supply imbalance) on this timeframe
#             fvg_supplies = self.fvg_detector.detect(
#                 symbol, df, tf, current_price, fvg_type="bearish"
#             )
#             for fvg in fvg_supplies:
#                 if fvg.bottom > current_price and not fvg.is_filled:
#                     sz = self._fvg_to_supply_zone(fvg, tf)
#                     supply_zones.append(sz)

#             # Detect swing highs
#             swing_highs = self._detect_swing_highs(symbol, df, tf, current_price)
#             supply_zones.extend(swing_highs)

#         # Remove duplicates (zones within 0.5% of each other)
#         supply_zones = self._deduplicate_zones(supply_zones)

#         # Sort by proximity to current price (nearest first = TP1)
#         supply_zones.sort(key=lambda z: z.level - current_price)

#         # Assign TP priority labels
#         for i, zone in enumerate(supply_zones):
#             zone.tp_priority = i + 1
#             # Calculate R:R if entry is at current price
#             risk = current_price * 0.02  # Assume 2% stop loss below entry
#             reward = zone.level - current_price
#             zone.risk_reward_ratio = round(reward / risk, 2) if risk > 0 else 0.0

#         return supply_zones[:max_tp_levels]

#     # ─── Private Helpers ─────────────────────────────────────────────────────

#     def _ob_to_supply_zone(self, ob: OrderBlock, timeframe: str) -> SupplyZone:
#         from datetime import datetime
#         return SupplyZone(
#             symbol=ob.symbol,
#             timeframe=timeframe,
#             timestamp=ob.timestamp,
#             high=ob.high,
#             low=ob.low,
#             source="ob",
#             is_active=ob.is_active,
#         )

#     def _fvg_to_supply_zone(self, fvg: FairValueGap, timeframe: str) -> SupplyZone:
#         return SupplyZone(
#             symbol=fvg.symbol,
#             timeframe=timeframe,
#             timestamp=fvg.timestamp,
#             high=fvg.top,
#             low=fvg.bottom,
#             source="fvg",
#             is_active=not fvg.is_filled,
#         )

#     def _detect_swing_highs(
#         self,
#         symbol: str,
#         df: pd.DataFrame,
#         timeframe: str,
#         current_price: float,
#         n: int = 3,     # Number of candles on each side to confirm swing high
#     ) -> List[SupplyZone]:
#         """
#         Detect major swing highs as structural resistance / TP levels.
#         A swing high is a candle whose high is higher than n candles on both sides.
#         """
#         zones = []
#         candles = df.reset_index()

#         for i in range(n, len(candles) - n):
#             center_high = candles.iloc[i]["high"]

#             # Check if it's a local high
#             is_swing = all(
#                 candles.iloc[i - j]["high"] < center_high and
#                 candles.iloc[i + j]["high"] < center_high
#                 for j in range(1, n + 1)
#             )

#             if not is_swing:
#                 continue

#             # Only care about swing highs ABOVE current price
#             if center_high <= current_price:
#                 continue

#             from datetime import datetime
#             ts = candles.iloc[i].get("timestamp", datetime.utcnow())
#             zone = SupplyZone(
#                 symbol=symbol,
#                 timeframe=timeframe,
#                 timestamp=ts,
#                 high=float(center_high) * 1.002,   # Small buffer
#                 low=float(center_high),
#                 source="swing_high",
#                 is_active=True,
#             )
#             zones.append(zone)

#         return zones

#     def _deduplicate_zones(
#         self,
#         zones: List[SupplyZone],
#         tolerance_pct: float = 0.5,
#     ) -> List[SupplyZone]:
#         """
#         Remove duplicate supply zones that are within tolerance_pct of each other.
#         Keeps the zone with higher timeframe weight.
#         """
#         if not zones:
#             return []

#         zones.sort(key=lambda z: z.low)
#         deduped = [zones[0]]

#         for zone in zones[1:]:
#             prev = deduped[-1]
#             if prev.low == 0:
#                 deduped.append(zone)
#                 continue
#             diff_pct = ((zone.low - prev.low) / prev.low) * 100
#             if diff_pct > tolerance_pct:
#                 deduped.append(zone)
#             else:
#                 # Keep higher TF zone (more significant)
#                 if TimeframeManager.weight(zone.timeframe) > TimeframeManager.weight(prev.timeframe):
#                     deduped[-1] = zone

#         return deduped


"""
analysis/supply_zone_detector.py
──────────────────────────────────
Detects supply zones to use as Take Profit (TP) targets.

Supply zones are identified as:
  1. Bearish Order Blocks (OBs) above current price
  2. Bearish FVGs above current price
  3. Major swing highs (structural resistance)

TP levels are sorted from nearest to farthest from current price,
and labeled TP1, TP2, TP3... for easy dashboard display.
"""

import pandas as pd
from typing import List, Dict
from loguru import logger

from models.supply_zone import SupplyZone
from models.order_block import OrderBlock
from models.fvg import FairValueGap
from analysis.order_block_detector import OrderBlockDetector
from analysis.fvg_detector import FVGDetector
from data.timeframe_manager import TimeframeManager


class SupplyZoneDetector:
    """
    Aggregates all supply zones above current price for TP calculation.
    Covers timeframes from 1H up to Monthly.
    """

    def __init__(self):
        self.ob_detector = OrderBlockDetector()
        self.fvg_detector = FVGDetector()

    def detect(
        self,
        symbol: str,
        ohlcv_data: Dict[str, pd.DataFrame],
        current_price: float,
        max_tp_levels: int = 5,
    ) -> List[SupplyZone]:
        """
        Find all supply zones above current price across all timeframes.

        Args:
            symbol:         Token symbol
            ohlcv_data:     Dict of {timeframe: DataFrame} including 1H
            current_price:  Current token price
            max_tp_levels:  Max number of TP levels to return

        Returns:
            List of SupplyZone sorted by proximity (nearest TP first)
        """
        supply_zones: List[SupplyZone] = []

        for tf, df in ohlcv_data.items():
            if df is None or df.empty:
                continue

            # Detect bearish OBs (supply) on this timeframe
            ob_supplies = self.ob_detector.detect(
                symbol, df, tf, current_price, ob_type="bearish"
            )
            for ob in ob_supplies:
                if ob.low > current_price and ob.is_active:
                    sz = self._ob_to_supply_zone(ob, tf)
                    supply_zones.append(sz)

            # Detect bearish FVGs (supply imbalance) on this timeframe
            fvg_supplies = self.fvg_detector.detect(
                symbol, df, tf, current_price, fvg_type="bearish"
            )
            for fvg in fvg_supplies:
                if fvg.bottom > current_price and not fvg.is_filled:
                    sz = self._fvg_to_supply_zone(fvg, tf)
                    supply_zones.append(sz)

            # Detect swing highs
            swing_highs = self._detect_swing_highs(symbol, df, tf, current_price)
            supply_zones.extend(swing_highs)

        # Remove duplicates (zones within 0.5% of each other)
        supply_zones = self._deduplicate_zones(supply_zones)

        # Sort by proximity to current price (nearest first = TP1)
        supply_zones.sort(key=lambda z: z.level - current_price)

        # Assign TP priority labels
        for i, zone in enumerate(supply_zones):
            zone.tp_priority = i + 1
            # Calculate R:R if entry is at current price
            risk = current_price * 0.02  # Assume 2% stop loss below entry
            reward = zone.level - current_price
            zone.risk_reward_ratio = round(reward / risk, 2) if risk > 0 else 0.0

        return supply_zones[:max_tp_levels]

    # ─── Private Helpers ─────────────────────────────────────────────────────

    def _ob_to_supply_zone(self, ob: OrderBlock, timeframe: str) -> SupplyZone:
        from datetime import datetime
        return SupplyZone(
            symbol=ob.symbol,
            timeframe=timeframe,
            timestamp=ob.timestamp,
            high=ob.high,
            low=ob.low,
            source="ob",
            is_active=ob.is_active,
        )

    def _fvg_to_supply_zone(self, fvg: FairValueGap, timeframe: str) -> SupplyZone:
        return SupplyZone(
            symbol=fvg.symbol,
            timeframe=timeframe,
            timestamp=fvg.timestamp,
            high=fvg.top,
            low=fvg.bottom,
            source="fvg",
            is_active=not fvg.is_filled,
        )

    def _detect_swing_highs(
        self,
        symbol: str,
        df: pd.DataFrame,
        timeframe: str,
        current_price: float,
        n: int = 3,     # Number of candles on each side to confirm swing high
    ) -> List[SupplyZone]:
        """
        Detect major swing highs as structural resistance / TP levels.
        A swing high is a candle whose high is higher than n candles on both sides.
        """
        zones = []
        candles = df.reset_index()

        for i in range(n, len(candles) - n):
            center_high = float(candles.iloc[i]["high"])

            # Check if it's a local high
            is_swing = all(
                float(candles.iloc[i - j]["high"]) < center_high and
                float(candles.iloc[i + j]["high"]) < center_high
                for j in range(1, n + 1)
            )

            if not is_swing:
                continue

            # Only care about swing highs ABOVE current price
            if center_high <= current_price:
                continue

            from datetime import datetime
            ts = candles.iloc[i].get("timestamp", datetime.utcnow())
            if hasattr(ts, 'to_pydatetime'):
                ts = ts.to_pydatetime()
            zone = SupplyZone(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=ts,
                high=center_high * 1.002,
                low=center_high,
                source="swing_high",
                is_active=True,
            )
            zones.append(zone)

        return zones

    def _deduplicate_zones(
        self,
        zones: List[SupplyZone],
        tolerance_pct: float = 0.5,
    ) -> List[SupplyZone]:
        """
        Remove duplicate supply zones that are within tolerance_pct of each other.
        Keeps the zone with higher timeframe weight.
        """
        if not zones:
            return []

        zones.sort(key=lambda z: z.low)
        deduped = [zones[0]]

        for zone in zones[1:]:
            prev = deduped[-1]
            if prev.low == 0:
                deduped.append(zone)
                continue
            diff_pct = ((zone.low - prev.low) / prev.low) * 100
            if diff_pct > tolerance_pct:
                deduped.append(zone)
            else:
                # Keep higher TF zone (more significant)
                if TimeframeManager.weight(zone.timeframe) > TimeframeManager.weight(prev.timeframe):
                    deduped[-1] = zone

        return deduped