# """
# data/ohlcv_fetcher.py - FAST VERSION
# No pagination. Single request per timeframe. Max 500 candles.
# """

# import time
# import pandas as pd
# from typing import Dict, Optional
# from loguru import logger

# from config import scanner_config
# from models.token import Token
# from exchanges.binance_client import BinanceClient
# from exchanges.mexc_client import MEXCClient
# from data.cache_manager import CacheManager

# # Candle limits per timeframe (single request, no pagination)
# CANDLE_LIMITS = {
#     "1h":  500,   # ~20 days
#     "4h":  500,   # ~83 days
#     "1d":  365,   # 1 year
#     "1w":  100,   # ~2 years
#     "1M":  36,    # 3 years
# }


# class OHLCVFetcher:

#     def __init__(self, binance: BinanceClient, mexc: MEXCClient, cache: CacheManager):
#         self.binance = binance
#         self.mexc = mexc
#         self.cache = cache

#     def fetch_live_price(self, token: Token) -> float:
#         """Fetch real-time price. Never cached."""
#         ccxt_symbol = f"{token.base}/{token.quote}"
#         try:
#             if token.exchange in ("binance", "both"):
#                 ticker = self.binance.exchange.fetch_ticker(ccxt_symbol)
#                 return float(ticker["last"])
#             else:
#                 ticker = self.mexc.exchange.fetch_ticker(ccxt_symbol)
#                 return float(ticker["last"])
#         except Exception as e:
#             logger.debug(f"Live price failed {token.symbol}: {e}")
#             return token.current_price

#     def fetch_all_timeframes(self, token: Token, timeframes: Optional[list] = None) -> Dict[str, pd.DataFrame]:
#         timeframes = timeframes or scanner_config.timeframes
#         result: Dict[str, pd.DataFrame] = {}
#         ccxt_symbol = f"{token.base}/{token.quote}"

#         for tf in timeframes:
#             cache_key = f"{token.symbol}:{tf}:v2"
#             cached = self.cache.get(cache_key)
#             if cached is not None:
#                 result[tf] = cached
#                 continue

#             df = self._fetch_single(token, ccxt_symbol, tf)
#             if df is not None and not df.empty:
#                 self.cache.set(cache_key, df)
#                 result[tf] = df

#         return result

#     def fetch_tp_timeframes(self, token: Token) -> Dict[str, pd.DataFrame]:
#         return self.fetch_all_timeframes(token, timeframes=scanner_config.tp_timeframes)

#     def _fetch_single(self, token: Token, ccxt_symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
#         """Single API call — no pagination."""
#         limit = CANDLE_LIMITS.get(timeframe, 200)
#         try:
#             if token.exchange in ("binance", "both"):
#                 raw = self.binance.exchange.fetch_ohlcv(ccxt_symbol, timeframe, limit=limit)
#             else:
#                 raw = self.mexc.exchange.fetch_ohlcv(ccxt_symbol, timeframe, limit=limit)

#             if not raw:
#                 return None

#             df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
#             df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
#             df = df.drop_duplicates(subset="timestamp").set_index("timestamp").sort_index()
#             return df

#         except Exception as e:
#             logger.debug(f"Fetch failed {token.symbol} {timeframe}: {e}")
#             return None



"""
data/ohlcv_fetcher.py — 5 months data, 12H + 3D support, single request per TF
"""

import time
import pandas as pd
from typing import Dict, Optional
from loguru import logger

from config import scanner_config
from models.token import Token
from exchanges.binance_client import BinanceClient
from exchanges.mexc_client import MEXCClient
from data.cache_manager import CacheManager
from data.timeframe_manager import TimeframeManager

# Binance timeframe mapping (3d and 12h need specific strings)
BINANCE_TF_MAP = {
    "1h":  "1h",
    "4h":  "4h",
    "12h": "12h",
    "1d":  "1d",
    "3d":  "3d",
    "1w":  "1w",
    "1M":  "1M",
}

MEXC_TF_MAP = {
    "1h":  "1h",
    "4h":  "4h",
    "12h": "12h",
    "1d":  "1d",
    "3d":  "3d",
    "1w":  "1W",
    "1M":  "1M",
}


class OHLCVFetcher:

    def __init__(self, binance: BinanceClient, mexc: MEXCClient, cache: CacheManager):
        self.binance = binance
        self.mexc = mexc
        self.cache = cache

    def fetch_live_price(self, token: Token) -> float:
        """Always-fresh live price from exchange ticker."""
        ccxt_symbol = f"{token.base}/{token.quote}"
        try:
            if token.exchange in ("binance", "both"):
                ticker = self.binance.exchange.fetch_ticker(ccxt_symbol)
                return float(ticker["last"])
            else:
                ticker = self.mexc.exchange.fetch_ticker(ccxt_symbol)
                return float(ticker["last"])
        except Exception as e:
            logger.debug(f"Live price failed {token.symbol}: {e}")
            return token.current_price

    def fetch_all_timeframes(self, token: Token, timeframes: Optional[list] = None) -> Dict[str, pd.DataFrame]:
        """Fetch 5 months of OHLCV across all timeframes."""
        timeframes = timeframes or scanner_config.timeframes
        result: Dict[str, pd.DataFrame] = {}
        ccxt_symbol = f"{token.base}/{token.quote}"

        for tf in timeframes:
            cache_key = f"{token.symbol}:{tf}:5m"
            cached = self.cache.get(cache_key)
            if cached is not None:
                result[tf] = cached
                continue

            df = self._fetch_single(token, ccxt_symbol, tf)
            if df is not None and not df.empty:
                self.cache.set(cache_key, df)
                result[tf] = df

        return result

    def fetch_tp_timeframes(self, token: Token) -> Dict[str, pd.DataFrame]:
        return self.fetch_all_timeframes(token, timeframes=scanner_config.tp_timeframes)

    def _fetch_single(self, token: Token, ccxt_symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """Single API call — no pagination. Uses 5-month candle count."""
        limit = TimeframeManager.candle_count(timeframe)
        limit = min(limit, 1000)  # Exchange cap

        try:
            if token.exchange in ("binance", "both"):
                tf_str = BINANCE_TF_MAP.get(timeframe, timeframe)
                raw = self.binance.exchange.fetch_ohlcv(ccxt_symbol, tf_str, limit=limit)
            else:
                tf_str = MEXC_TF_MAP.get(timeframe, timeframe)
                raw = self.mexc.exchange.fetch_ohlcv(ccxt_symbol, tf_str, limit=limit)

            if not raw:
                return None

            df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
            df = df.drop_duplicates(subset="timestamp").set_index("timestamp").sort_index()
            return df

        except Exception as e:
            logger.debug(f"Fetch failed {token.symbol} {timeframe}: {e}")
            return None