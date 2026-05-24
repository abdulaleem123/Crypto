"""
exchanges/binance_client.py
────────────────────────────
Binance exchange client.

Responsibilities:
  - Fetch all USDT spot trading pairs
  - Fetch current ticker prices and 24h volume
  - Fetch OHLCV candle data for any symbol / timeframe
"""

import ccxt
import pandas as pd
from typing import List, Dict, Optional
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config import exchange_config, scanner_config


class BinanceClient:
    """Wrapper around ccxt Binance for OHLCV and ticker data."""

    # Binance timeframe mapping → ccxt format
    TIMEFRAME_MAP = {
        "1h": "1h",
        "4h": "4h",
        "1d": "1d",
        "1w": "1w",
        "1M": "1M",
    }

    def __init__(self):
        self.exchange = ccxt.binance({
            "apiKey": exchange_config.binance_api_key,
            "secret": exchange_config.binance_api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        })
        self._markets: Dict = {}

    def load_markets(self) -> None:
        """Load and cache all Binance markets."""
        logger.info("Loading Binance markets...")
        self._markets = self.exchange.load_markets()
        logger.info(f"Binance: {len(self._markets)} markets loaded")

    def get_usdt_symbols(self) -> List[str]:
        """
        Return all active USDT spot pairs above minimum volume threshold.
        Returns symbols in Binance format e.g. 'BTC/USDT'
        """
        if not self._markets:
            self.load_markets()

        symbols = []
        for symbol, market in self._markets.items():
            if (
                market.get("quote") == "USDT"
                and market.get("spot", False)
                and market.get("active", False)
                and not market.get("future", False)
            ):
                symbols.append(symbol)

        logger.info(f"Binance USDT spot pairs: {len(symbols)}")
        return symbols

    def get_tickers(self, symbols: Optional[List[str]] = None) -> Dict[str, Dict]:
        """
        Fetch current price and 24h volume for all (or specified) symbols.
        Returns dict keyed by symbol with price/volume data.
        """
        logger.info("Fetching Binance tickers...")
        try:
            if symbols:
                tickers = self.exchange.fetch_tickers(symbols)
            else:
                tickers = self.exchange.fetch_tickers()
            logger.info(f"Fetched {len(tickers)} tickers from Binance")
            return tickers
        except Exception as e:
            logger.error(f"Error fetching Binance tickers: {e}")
            return {}

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = None,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV candle data for a symbol on a given timeframe.

        Args:
            symbol:    e.g. "BTC/USDT"
            timeframe: e.g. "4h", "1d", "1w", "1M"
            limit:     Number of candles (default from config)

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
            logger.warning(f"Binance: symbol {symbol} not found")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Binance OHLCV error [{symbol} {timeframe}]: {e}")
            raise

    def get_symbol_set(self) -> set:
        """Return set of base assets (e.g. {'BTC', 'ETH', ...}) listed on Binance."""
        if not self._markets:
            self.load_markets()
        return {
            market["base"]
            for market in self._markets.values()
            if market.get("quote") == "USDT" and market.get("spot")
        }
