# """
# config.py
# ─────────
# Central configuration — loads .env and exposes typed settings
# used by all modules in the project.
# """

# import os
# from dotenv import load_dotenv
# from pydantic import BaseModel, Field
# from typing import List

# load_dotenv()


# class ExchangeConfig(BaseModel):
#     binance_api_key: str = Field(default_factory=lambda: os.getenv("BINANCE_API_KEY", ""))
#     binance_api_secret: str = Field(default_factory=lambda: os.getenv("BINANCE_API_SECRET", ""))
#     mexc_api_key: str = Field(default_factory=lambda: os.getenv("MEXC_API_KEY", ""))
#     mexc_api_secret: str = Field(default_factory=lambda: os.getenv("MEXC_API_SECRET", ""))


# class ScannerConfig(BaseModel):
#     # Timeframes to analyze — ordered from smallest to largest
#     timeframes: List[str] = ["4h", "1d", "1w", "1M"]

#     # Supply zone timeframes for TP calculation (starts from 1h)
#     tp_timeframes: List[str] = ["1h", "4h", "1d", "1w", "1M"]

#     # How close price must be to a zone (%) to trigger highlighting
#     proximity_threshold_pct: float = float(os.getenv("PROXIMITY_THRESHOLD_PERCENT", "2.0"))

#     # Minimum 24h volume in USDT to include a token
#     min_volume_usdt: float = float(os.getenv("MIN_VOLUME_USDT", "100000"))

#     # Max tokens to scan (0 = unlimited)
#     max_tokens: int = int(os.getenv("MAX_TOKENS_TO_SCAN", "500"))

#     # How many candles to fetch per timeframe
#     candle_lookback: int = 200

#     # Scan interval
#     scan_interval_minutes: int = int(os.getenv("SCAN_INTERVAL_MINUTES", "15"))


# class CacheConfig(BaseModel):
#     use_redis: bool = os.getenv("USE_REDIS", "false").lower() == "true"
#     redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
#     cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "900"))
#     disk_cache_dir: str = ".cache"


# class NotificationConfig(BaseModel):
#     openclaw_api_key: str = Field(default_factory=lambda: os.getenv("OPENCLAW_API_KEY", ""))
#     openclaw_phone: str = Field(default_factory=lambda: os.getenv("OPENCLAW_PHONE_NUMBER", ""))
#     # Send alerts only for these zone types
#     alert_on_ob: bool = True
#     alert_on_fvg: bool = True
#     # Minimum score to send alert (0-100)
#     alert_min_score: float = 70.0


# class DashboardConfig(BaseModel):
#     title: str = "🔍 HTF OB & FVG Scanner"
#     refresh_interval_seconds: int = 60
#     # Number of top tokens to show highlighted
#     top_n: int = 50
#     # Color definitions
#     fvg_zone_color: str = "#1a5c2a"       # dark green
#     ob_zone_color: str = "#4caf50"         # light green
#     mexc_only_color: str = "#1565c0"       # blue for small caps


# # ─── Singleton instances ─────────────────────────────────────────────────────

# exchange_config = ExchangeConfig()
# scanner_config = ScannerConfig()
# cache_config = CacheConfig()
# notification_config = NotificationConfig()
# dashboard_config = DashboardConfig()



import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import List

load_dotenv()

class ExchangeConfig(BaseModel):
    binance_api_key: str = Field(default_factory=lambda: os.getenv("BINANCE_API_KEY", ""))
    binance_api_secret: str = Field(default_factory=lambda: os.getenv("BINANCE_API_SECRET", ""))
    mexc_api_key: str = Field(default_factory=lambda: os.getenv("MEXC_API_KEY", ""))
    mexc_api_secret: str = Field(default_factory=lambda: os.getenv("MEXC_API_SECRET", ""))

class ScannerConfig(BaseModel):
    # NO 12h — removed as requested
    timeframes: List[str] = ["4h", "1d", "3d", "1w", "1M"]
    tp_timeframes: List[str] = ["1h", "4h", "1d", "3d", "1w", "1M"]
    proximity_threshold_pct: float = float(os.getenv("PROXIMITY_THRESHOLD_PERCENT", "2.0"))
    min_volume_usdt: float = float(os.getenv("MIN_VOLUME_USDT", "100000"))
    max_tokens: int = int(os.getenv("MAX_TOKENS_TO_SCAN", "100"))
    candle_lookback: int = 200
    scan_interval_minutes: int = int(os.getenv("SCAN_INTERVAL_MINUTES", "15"))

class CacheConfig(BaseModel):
    use_redis: bool = os.getenv("USE_REDIS", "false").lower() == "true"
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "900"))
    disk_cache_dir: str = ".cache"

class NotificationConfig(BaseModel):
    openclaw_api_key: str = Field(default_factory=lambda: os.getenv("OPENCLAW_API_KEY", ""))
    openclaw_phone: str = Field(default_factory=lambda: os.getenv("OPENCLAW_PHONE_NUMBER", ""))
    alert_on_ob: bool = True
    alert_on_fvg: bool = True
    alert_min_score: float = 70.0

class DashboardConfig(BaseModel):
    title: str = "🦖 Godzilla HTF Scanner"
    refresh_interval_seconds: int = 30
    top_n: int = 100

exchange_config = ExchangeConfig()
scanner_config = ScannerConfig()
cache_config = CacheConfig()
notification_config = NotificationConfig()
dashboard_config = DashboardConfig()