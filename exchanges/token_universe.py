"""
exchanges/token_universe.py
────────────────────────────
Builds the master list of Token objects from both Binance and MEXC.

Steps:
  1. Load all USDT spot pairs from Binance
  2. Load all USDT spot pairs from MEXC
  3. Filter by minimum volume
  4. Tag MEXC-only tokens as is_mexc_only=True
  5. Return a flat list of Token objects ready for analysis
"""

from typing import List, Tuple
from loguru import logger

from config import scanner_config
from models.token import Token
from exchanges.binance_client import BinanceClient
from exchanges.mexc_client import MEXCClient


class TokenUniverse:
    """Aggregates tokens from Binance and MEXC into a unified Token list."""

    def __init__(self):
        self.binance = BinanceClient()
        self.mexc = MEXCClient()

    def build(self) -> List[Token]:
        """
        Main entry point — fetches and merges tokens from both exchanges.

        Returns:
            List[Token] — complete universe ready for OHLCV + analysis pipeline.
        """
        logger.info("Building token universe from Binance + MEXC...")

        # ── Step 1: Load markets from both exchanges ─────────────────────────
        self.binance.load_markets()
        self.mexc.load_markets()

        binance_base_set = self.binance.get_symbol_set()
        mexc_only_symbols = self.mexc.find_mexc_only_tokens(binance_base_set)

        # ── Step 2: Fetch tickers for volume filtering ───────────────────────
        logger.info("Fetching tickers for volume filtering...")
        binance_tickers = self.binance.get_tickers()
        mexc_tickers = self.mexc.get_tickers()

        # ── Step 3: Build Token objects for Binance pairs ────────────────────
        tokens: List[Token] = []
        seen_symbols = set()

        for symbol in self.binance.get_usdt_symbols():
            ticker = binance_tickers.get(symbol, {})
            volume = ticker.get("quoteVolume", 0) or 0

            if volume < scanner_config.min_volume_usdt:
                continue

            base = symbol.split("/")[0]
            token = Token(
                symbol=symbol.replace("/", ""),   # BTCUSDT format
                base=base,
                quote="USDT",
                exchange="binance",
                current_price=ticker.get("last", 0) or 0,
                volume_24h_usdt=volume,
                price_change_24h_pct=ticker.get("percentage", 0) or 0,
                is_mexc_only=False,
            )
            tokens.append(token)
            seen_symbols.add(base)

        logger.info(f"Binance tokens after volume filter: {len(tokens)}")

        # ── Step 4: Build Token objects for MEXC-only tokens ─────────────────
        mexc_only_count = 0
        for symbol in mexc_only_symbols:
            ticker = mexc_tickers.get(symbol, {})
            volume = ticker.get("quoteVolume", 0) or 0

            if volume < scanner_config.min_volume_usdt:
                continue

            base = symbol.split("/")[0]
            if base in seen_symbols:
                continue

            token = Token(
                symbol=symbol.replace("/", ""),
                base=base,
                quote="USDT",
                exchange="mexc",
                current_price=ticker.get("last", 0) or 0,
                volume_24h_usdt=volume,
                price_change_24h_pct=ticker.get("percentage", 0) or 0,
                is_mexc_only=True,
            )
            tokens.append(token)
            mexc_only_count += 1

        logger.info(f"MEXC-only small cap tokens added: {mexc_only_count}")

        # ── Step 5: Apply token cap ───────────────────────────────────────────
        if scanner_config.max_tokens > 0:
            # Sort by volume descending, keep top N
            tokens.sort(key=lambda t: t.volume_24h_usdt, reverse=True)
            tokens = tokens[:scanner_config.max_tokens]

        logger.info(f"Total token universe: {len(tokens)} tokens")
        return tokens

    def get_exchange_for_symbol(self, base: str, binance_base_set: set) -> str:
        """Helper: determine if token is on 'binance', 'mexc', or 'both'."""
        on_binance = base in binance_base_set
        mexc_bases = self.mexc.get_symbol_set()
        on_mexc = base in mexc_bases

        if on_binance and on_mexc:
            return "both"
        if on_binance:
            return "binance"
        return "mexc"
