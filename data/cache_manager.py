"""
data/cache_manager.py
──────────────────────
Caching layer for OHLCV data.

Supports two backends:
  - Redis (preferred for production)
  - diskcache (file-based, no Redis needed for local dev)

DataFrame serialization: Parquet format (fast + compact).
"""

import io
import pandas as pd
from typing import Optional
from loguru import logger

from config import cache_config


class CacheManager:
    """
    Transparent cache for OHLCV DataFrames.

    Keys follow the pattern: "{SYMBOL}:{TIMEFRAME}"
    e.g. "BTCUSDT:4h", "ETHUSDT:1d"
    """

    def __init__(self):
        self._backend = None
        self._setup_backend()

    def _setup_backend(self):
        """Initialize Redis or disk cache backend."""
        if cache_config.use_redis:
            try:
                import redis
                self._backend = redis.from_url(cache_config.redis_url, decode_responses=False)
                self._backend.ping()
                self._mode = "redis"
                logger.info("Cache: Redis backend connected")
            except Exception as e:
                logger.warning(f"Redis unavailable ({e}), falling back to diskcache")
                self._init_diskcache()
        else:
            self._init_diskcache()

    def _init_diskcache(self):
        import diskcache
        self._backend = diskcache.Cache(cache_config.disk_cache_dir)
        self._mode = "disk"
        logger.info(f"Cache: Disk backend at '{cache_config.disk_cache_dir}'")

    def get(self, key: str) -> Optional[pd.DataFrame]:
        """
        Retrieve a DataFrame from cache.

        Returns:
            DataFrame if found and not expired, else None.
        """
        try:
            raw = self._backend.get(key)
            if raw is None:
                return None
            return pd.read_parquet(io.BytesIO(raw))
        except Exception as e:
            logger.debug(f"Cache miss or error for {key}: {e}")
            return None

    def set(self, key: str, df: pd.DataFrame) -> None:
        """Store a DataFrame in cache with configured TTL."""
        try:
            buffer = io.BytesIO()
            df.to_parquet(buffer, index=True)
            raw = buffer.getvalue()

            if self._mode == "redis":
                self._backend.setex(key, cache_config.cache_ttl_seconds, raw)
            else:
                self._backend.set(key, raw, expire=cache_config.cache_ttl_seconds)
        except Exception as e:
            logger.warning(f"Cache write error for {key}: {e}")

    def invalidate(self, key: str) -> None:
        """Remove a specific key from cache."""
        try:
            if self._mode == "redis":
                self._backend.delete(key)
            else:
                self._backend.delete(key)
        except Exception as e:
            logger.warning(f"Cache invalidation error for {key}: {e}")

    def clear_all(self) -> None:
        """Wipe entire cache — use carefully."""
        try:
            if self._mode == "redis":
                self._backend.flushdb()
            else:
                self._backend.clear()
            logger.info("Cache cleared")
        except Exception as e:
            logger.error(f"Cache clear error: {e}")

    def stats(self) -> dict:
        """Return basic cache statistics."""
        try:
            if self._mode == "redis":
                info = self._backend.info()
                return {
                    "mode": "redis",
                    "keys": self._backend.dbsize(),
                    "memory_mb": round(info.get("used_memory", 0) / 1e6, 2),
                }
            else:
                return {
                    "mode": "disk",
                    "keys": len(self._backend),
                    "size_mb": round(self._backend.volume() / 1e6, 2),
                }
        except Exception:
            return {"mode": self._mode, "error": "stats unavailable"}
