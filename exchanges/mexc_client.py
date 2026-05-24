"""
exchanges/mexc_client.py
─────────────────────────
MEXC exchange client.

Responsibilities:
  - Fetch all USDT spot trading pairs from MEXC
  - Identify tokens listed on MEXC but NOT on Binance (small caps)
  - Fetch OHLCV candle data for any symbol / timeframe
"""

import ccxt
import pandas as pd
from typing import List, Dict, Set, Optional
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config import exchange_config, scanner_config


class MEXCClient:
    """Wrapper around ccxt MEXC for OHLCV and ticker data."""

    TIMEFRAME_MAP = {
        "1h": "1h",
        "4h": "4h",
        "1d": "1d",
        "1w": "1W",   # MEXC uses "1W" not "1w"
        "1M": "1M",
    }

    def __init__(self):
        self.exchange = ccxt.mexc({
            "apiKey": exchange_config.mexc_api_key,
            "secret": exchange_config.mexc_api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        })
        self._markets: Dict = {}

    def load_markets(self) -> None:
        """Load and cache all MEXC markets."""
        logger.info("Loading MEXC markets...")
        self._markets = self.exchange.load_markets()
        logger.info(f"MEXC: {len(self._markets)} markets loaded")

    def get_usdt_symbols(self) -> List[str]:
        """
        Return all active USDT spot pairs on MEXC.
        Returns symbols in ccxt format e.g. 'BTC/USDT'
        """
        if not self._markets:
            self.load_markets()

        symbols = []
        for symbol, market in self._markets.items():
            if (
                market.get("quote") == "USDT"
                and market.get("spot", False)
                and market.get("active", False)
            ):
                symbols.append(symbol)

        logger.info(f"MEXC USDT spot pairs: {len(symbols)}")
        return symbols

    def get_tickers(self, symbols: Optional[List[str]] = None) -> Dict[str, Dict]:
        """Fetch current tickers from MEXC."""
        logger.info("Fetching MEXC tickers...")
        try:
            tickers = self.exchange.fetch_tickers(symbols) if symbols else self.exchange.fetch_tickers()
            logger.info(f"Fetched {len(tickers)} tickers from MEXC")
            return tickers
        except Exception as e:
            logger.error(f"Error fetching MEXC tickers: {e}")
            return {}

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = None,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV candle data from MEXC.

        Args:
            symbol:    e.g. "PEPE/USDT"
            timeframe: e.g. "4h", "1d", "1w", "1M"
            limit:     Number of candles

        Returns:
            DataFrame with columns: [timestamp, open, high, low, close, volume]
        """
        limit = limit or scanner_config.candle_lookback
        tf = self.TIMEFRAME_MAP.get(timeframe, timeframe)

        try:
            raw = self.exchange.fetch_ohlcv(symbol, tf, limit=limit)
            df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df = df.set_index("timestamp")
            return df
        except ccxt.BadSymbol:
            logger.warning(f"MEXC: symbol {symbol} not found")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"MEXC OHLCV error [{symbol} {timeframe}]: {e}")
            raise

    def get_symbol_set(self) -> Set[str]:
        """Return set of base assets (e.g. {'BTC', 'PEPE', ...}) listed on MEXC."""
        if not self._markets:
            self.load_markets()
        return {
            market["base"]
            for market in self._markets.values()
            if market.get("quote") == "USDT" and market.get("spot")
        }

    def find_mexc_only_tokens(self, binance_symbols: Set[str]) -> List[str]:
        """
        Identify tokens listed on MEXC but NOT on Binance.
        These are potential small-cap gems to monitor separately.

        Args:
            binance_symbols: Set of base assets from Binance

        Returns:
            List of MEXC-only symbols in ccxt format (e.g. ['NEWTOKEN/USDT', ...])
        """
        mexc_symbols = self.get_symbol_set()
        mexc_only_bases = mexc_symbols - binance_symbols

        mexc_only_pairs = []
        for symbol, market in self._markets.items():
            if (
                market.get("base") in mexc_only_bases
                and market.get("quote") == "USDT"
                and market.get("spot")
                and market.get("active")
            ):
                mexc_only_pairs.append(symbol)

        logger.info(f"MEXC-only tokens (not on Binance): {len(mexc_only_pairs)}")
        return mexc_only_pairs
