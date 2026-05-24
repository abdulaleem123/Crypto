# 🚀 Crypto HTF OB & FVG Scanner

Automatically scans **all tokens on Binance & MEXC**, detects Higher Time Frame Order Blocks and Fair Value Gaps, and highlights high-probability spot trading entries with TP levels in supply zones.

---

## ⚙️ Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Fill in your API keys in .env
```

### 3. Run the Dashboard
```bash
streamlit run dashboard/app.py
```

---

## 🧠 Features

| Feature | Description |
|---|---|
| OB Detection | Finds Order Blocks from 4H → Monthly |
| FVG Detection | Finds Fair Value Gaps from 4H → Monthly |
| Supply Zones | TP levels from 1H → Monthly supply |
| MEXC-only tokens | Flags small caps not on Binance |
| WhatsApp Alerts | Sends alerts via OpenClaw when price enters zone |
| Color Coding | Dark green = FVG zone, Light green = OB zone |
| Auto Ranking | Tokens near zones bubble to top automatically |

---

## 📁 Project Structure

```
crypto-htf-scanner/
├── exchanges/          # Binance + MEXC API clients
├── data/               # OHLCV fetching and caching
├── analysis/           # OB, FVG, Supply Zone detection
├── notifications/      # WhatsApp alerts via OpenClaw
├── dashboard/          # Streamlit dashboard
├── scheduler/          # Background scanner scheduler
├── models/             # Data models/dataclasses
└── tests/              # Unit tests
```

---

## 🔑 Required API Keys (in .env)

- `BINANCE_API_KEY` / `BINANCE_API_SECRET`
- `MEXC_API_KEY` / `MEXC_API_SECRET`
- `OPENCLAW_API_KEY` + `OPENCLAW_PHONE_NUMBER` (WhatsApp alerts)

---

## ⚠️ Disclaimer

This tool is for **educational and informational purposes only**. Not financial advice. Always DYOR.


First go to the cmd once the anaconda environemnt gets activated so type this
streamlit run dashboard/app.py
