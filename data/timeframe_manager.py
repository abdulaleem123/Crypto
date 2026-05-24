# """
# data/timeframe_manager.py
# ──────────────────────────
# Manages timeframe ordering, weighting, and HTF logic.

# Higher timeframes carry more weight in scoring —
# a Monthly OB is more significant than a 4H OB.
# """

# from typing import List, Dict

# # Timeframes ordered from smallest to largest
# TIMEFRAME_ORDER = ["1h", "4h", "1d", "1w", "1M"]

# # Relative weight for scoring (higher TF = stronger signal)
# TIMEFRAME_WEIGHTS: Dict[str, float] = {
#     "1h":  1.0,
#     "4h":  2.0,
#     "1d":  4.0,
#     "1w":  7.0,
#     "1M": 12.0,
# }

# # Human-readable labels
# TIMEFRAME_LABELS: Dict[str, str] = {
#     "1h":  "1 Hour",
#     "4h":  "4 Hour",
#     "1d":  "Daily",
#     "1w":  "Weekly",
#     "1M":  "Monthly",
# }


# class TimeframeManager:
#     """Utility class for timeframe logic across the scanner."""

#     @staticmethod
#     def get_htf_timeframes() -> List[str]:
#         """HTF timeframes used for OB and FVG detection (4H and above)."""
#         return ["4h", "1d", "1w", "1M"]

#     @staticmethod
#     def get_all_timeframes() -> List[str]:
#         """All timeframes including 1H (used for TP supply zones)."""
#         return TIMEFRAME_ORDER.copy()

#     @staticmethod
#     def weight(timeframe: str) -> float:
#         """Return the scoring weight for a given timeframe."""
#         return TIMEFRAME_WEIGHTS.get(timeframe, 1.0)

#     @staticmethod
#     def label(timeframe: str) -> str:
#         """Return human-readable label for a timeframe."""
#         return TIMEFRAME_LABELS.get(timeframe, timeframe.upper())

#     @staticmethod
#     def is_htf(timeframe: str) -> bool:
#         """Returns True if this is a Higher Time Frame (4H+)."""
#         return timeframe in {"4h", "1d", "1w", "1M"}

#     @staticmethod
#     def sort_by_tf(timeframes: List[str], descending: bool = False) -> List[str]:
#         """Sort a list of timeframes from smallest to largest (or reverse)."""
#         ordered = [tf for tf in TIMEFRAME_ORDER if tf in timeframes]
#         if descending:
#             ordered.reverse()
#         return ordered

#     @staticmethod
#     def minimum_candles_required(timeframe: str) -> int:
#         """
#         Minimum candle count needed for reliable OB/FVG detection on each TF.
#         Weekly and Monthly need fewer due to limited history.
#         """
#         minimums = {
#             "1h":  50,
#             "4h":  50,
#             "1d":  30,
#             "1w":  15,
#             "1M":   8,
#         }
#         return minimums.get(timeframe, 20)



"""
data/timeframe_manager.py — includes 12H and 3D
"""

from typing import List, Dict

TIMEFRAME_ORDER = ["1h", "4h", "12h", "1d", "3d", "1w", "1M"]

TIMEFRAME_WEIGHTS: Dict[str, float] = {
    "1h":   1.0,
    "4h":   2.0,
    "12h":  3.0,
    "1d":   4.0,
    "3d":   6.0,
    "1w":   7.0,
    "1M":  12.0,
}

TIMEFRAME_LABELS: Dict[str, str] = {
    "1h":  "1 Hour",
    "4h":  "4 Hour",
    "12h": "12 Hour",
    "1d":  "Daily",
    "3d":  "3 Day",
    "1w":  "Weekly",
    "1M":  "Monthly",
}

# Candle counts for ~5 months of data per timeframe
CANDLE_COUNTS_5M: Dict[str, int] = {
    "1h":  150 * 24,    # 3600 (5 months hourly)
    "4h":  150 * 6,     # 900
    "12h": 150 * 2,     # 300
    "1d":  150,         # 150 daily
    "3d":  50,          # ~5 months in 3d candles
    "1w":  22,          # ~5 months weekly
    "1M":  6,           # 6 monthly candles
}


class TimeframeManager:

    @staticmethod
    def get_htf_timeframes() -> List[str]:
        return ["4h", "12h", "1d", "3d", "1w", "1M"]

    @staticmethod
    def get_all_timeframes() -> List[str]:
        return TIMEFRAME_ORDER.copy()

    @staticmethod
    def weight(timeframe: str) -> float:
        return TIMEFRAME_WEIGHTS.get(timeframe, 1.0)

    @staticmethod
    def label(timeframe: str) -> str:
        return TIMEFRAME_LABELS.get(timeframe, timeframe.upper())

    @staticmethod
    def is_htf(timeframe: str) -> bool:
        return timeframe in {"4h", "12h", "1d", "3d", "1w", "1M"}

    @staticmethod
    def candle_count(timeframe: str) -> int:
        return CANDLE_COUNTS_5M.get(timeframe, 200)