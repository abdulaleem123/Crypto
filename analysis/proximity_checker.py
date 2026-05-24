# """
# analysis/proximity_checker.py
# ───────────────────────────────
# Checks how close a token's current price is to its OB / FVG zones.

# Used to:
#   1. Flag tokens as near_ob_zone or near_fvg_zone
#   2. Find the single nearest zone of each type
#   3. Determine if an alert should be triggered
# """

# from typing import Optional, Tuple
# from loguru import logger

# from config import scanner_config
# from models.token import Token
# from models.order_block import OrderBlock
# from models.fvg import FairValueGap


# class ProximityChecker:
#     """
#     Evaluates how close the current price is to detected zones.
#     Updates token flags: near_ob_zone, near_fvg_zone, nearest_ob, nearest_fvg.
#     """

#     def __init__(self, threshold_pct: float = None):
#         # % within which we consider price "near" a zone
#         self.threshold_pct = threshold_pct or scanner_config.proximity_threshold_pct

#     def check_token(self, token: Token) -> Token:
#         """
#         Run proximity checks on a token and update its flags in-place.

#         Args:
#             token: Token with order_blocks, fvgs, supply_zones populated

#         Returns:
#             Updated Token
#         """
#         price = token.current_price
#         if price == 0:
#             return token

#         # ── Check OBs ────────────────────────────────────────────────────────
#         nearest_ob, near_ob = self._find_nearest_ob(token.order_blocks, price)
#         token.nearest_ob = nearest_ob
#         token.near_ob_zone = near_ob

#         # ── Check FVGs ───────────────────────────────────────────────────────
#         nearest_fvg, near_fvg = self._find_nearest_fvg(token.fvgs, price)
#         token.nearest_fvg = nearest_fvg
#         token.near_fvg_zone = near_fvg

#         # ── Check nearest TP supply zone ──────────────────────────────────────
#         if token.supply_zones:
#             token.nearest_supply = token.supply_zones[0]  # Already sorted nearest-first

#         return token

#     def _find_nearest_ob(
#         self,
#         obs: list,
#         current_price: float,
#     ) -> Tuple[Optional[OrderBlock], bool]:
#         """
#         Find the nearest active bullish OB to current price.

#         Returns:
#             (nearest_ob, is_within_threshold)
#         """
#         active_obs = [ob for ob in obs if ob.is_active and ob.ob_type == "bullish"]
#         if not active_obs:
#             return None, False

#         # Sort by distance to current price
#         active_obs.sort(key=lambda ob: ob.distance_to_price(current_price))
#         nearest = active_obs[0]
#         distance = nearest.distance_to_price(current_price)

#         # Inside the zone (distance = -1) or within threshold
#         is_near = distance <= self.threshold_pct

#         return nearest, is_near

#     def _find_nearest_fvg(
#         self,
#         fvgs: list,
#         current_price: float,
#     ) -> Tuple[Optional[FairValueGap], bool]:
#         """
#         Find the nearest unfilled bullish FVG to current price.

#         Returns:
#             (nearest_fvg, is_within_threshold)
#         """
#         active_fvgs = [f for f in fvgs if not f.is_filled and f.fvg_type == "bullish"]
#         if not active_fvgs:
#             return None, False

#         active_fvgs.sort(key=lambda f: f.distance_to_price(current_price))
#         nearest = active_fvgs[0]
#         distance = nearest.distance_to_price(current_price)

#         is_near = distance <= self.threshold_pct

#         return nearest, is_near

#     def get_distance_to_nearest_zone(self, token: Token) -> float:
#         """
#         Return the minimum % distance to any active zone (OB or FVG).
#         Returns 999.0 if no zones found.
#         """
#         price = token.current_price
#         distances = []

#         if token.nearest_ob:
#             d = token.nearest_ob.distance_to_price(price)
#             if d >= 0:
#                 distances.append(d)

#         if token.nearest_fvg:
#             d = token.nearest_fvg.distance_to_price(price)
#             if d >= 0:
#                 distances.append(d)

#         return min(distances) if distances else 999.0

#     def is_inside_any_zone(self, token: Token) -> bool:
#         """True if current price is already inside an OB or FVG zone."""
#         price = token.current_price

#         for ob in token.order_blocks:
#             if ob.is_active and ob.ob_type == "bullish":
#                 if ob.low <= price <= ob.high:
#                     return True

#         for fvg in token.fvgs:
#             if not fvg.is_filled and fvg.fvg_type == "bullish":
#                 if fvg.bottom <= price <= fvg.top:
#                     return True

#         return False


"""
analysis/proximity_checker.py
Sets near_zone_label e.g. "NEAR 1D OB", "NEAR 4H FVG", "INSIDE WK FVG"
"""

from typing import Optional, Tuple
from config import scanner_config
from models.token import Token
from models.order_block import OrderBlock
from models.fvg import FairValueGap
from data.timeframe_manager import TimeframeManager

TF_DISPLAY = {
    "4h":  "4H",
    "12h": "12H",
    "1d":  "1D",
    "3d":  "3D",
    "1w":  "WEEKLY",
    "1M":  "MONTHLY",
}


class ProximityChecker:

    def __init__(self, threshold_pct: float = None):
        self.threshold_pct = threshold_pct or scanner_config.proximity_threshold_pct

    def check_token(self, token: Token) -> Token:
        price = token.current_price
        if price == 0:
            return token

        # Check OBs
        nearest_ob, near_ob = self._find_nearest_ob(token.order_blocks, price)
        token.nearest_ob = nearest_ob
        token.near_ob_zone = near_ob

        # Check FVGs
        nearest_fvg, near_fvg = self._find_nearest_fvg(token.fvgs, price)
        token.nearest_fvg = nearest_fvg
        token.near_fvg_zone = near_fvg

        # Nearest supply TP
        if token.supply_zones:
            token.nearest_supply = token.supply_zones[0]

        # Build near_zone_label — shows WHICH timeframe the zone is on
        token.near_zone_label = self._build_label(token, price)

        return token

    def _build_label(self, token: Token, price: float) -> str:
        """
        Returns human-readable label like:
          "INSIDE 1D FVG"
          "NEAR 4H OB"
          "NEAR WEEKLY FVG + 1D OB"
          "—"
        """
        parts = []

        if token.nearest_fvg and token.near_fvg_zone:
            fvg = token.nearest_fvg
            tf = TF_DISPLAY.get(fvg.timeframe, fvg.timeframe.upper())
            dist = fvg.distance_to_price(price)
            prefix = "INSIDE" if dist == -1 else "NEAR"
            parts.append(f"{prefix} {tf} FVG")

        if token.nearest_ob and token.near_ob_zone:
            ob = token.nearest_ob
            tf = TF_DISPLAY.get(ob.timeframe, ob.timeframe.upper())
            dist = ob.distance_to_price(price)
            prefix = "INSIDE" if dist == -1 else "NEAR"
            parts.append(f"{prefix} {tf} OB")

        return " + ".join(parts) if parts else "—"

    def _find_nearest_ob(self, obs: list, price: float) -> Tuple[Optional[OrderBlock], bool]:
        active = [ob for ob in obs if ob.is_active and ob.ob_type == "bullish"]
        if not active:
            return None, False
        active.sort(key=lambda ob: ob.distance_to_price(price))
        nearest = active[0]
        distance = nearest.distance_to_price(price)
        return nearest, distance <= self.threshold_pct

    def _find_nearest_fvg(self, fvgs: list, price: float) -> Tuple[Optional[FairValueGap], bool]:
        active = [f for f in fvgs if not f.is_filled and f.fvg_type == "bullish"]
        if not active:
            return None, False
        active.sort(key=lambda f: f.distance_to_price(price))
        nearest = active[0]
        distance = nearest.distance_to_price(price)
        return nearest, distance <= self.threshold_pct

    def get_distance_to_nearest_zone(self, token: Token) -> float:
        price = token.current_price
        distances = []
        if token.nearest_ob:
            d = token.nearest_ob.distance_to_price(price)
            if d >= 0:
                distances.append(d)
        if token.nearest_fvg:
            d = token.nearest_fvg.distance_to_price(price)
            if d >= 0:
                distances.append(d)
        return min(distances) if distances else 999.0

    def is_inside_any_zone(self, token: Token) -> bool:
        price = token.current_price
        for ob in token.order_blocks:
            if ob.is_active and ob.ob_type == "bullish":
                if ob.low <= price <= ob.high:
                    return True
        for fvg in token.fvgs:
            if not fvg.is_filled and fvg.fvg_type == "bullish":
                if fvg.bottom <= price <= fvg.top:
                    return True
        return False