# 🚀 Deploy to Streamlit Cloud (Free)

## Step 1 — Create a GitHub Account
Go to https://github.com and sign up (free).

## Step 2 — Create a New Repository
1. Click the **+** icon → **New repository**
2. Name it: `crypto-htf-scanner`
3. Set to **Public**
4. Click **Create repository**

## Step 3 — Upload Your Files
On the new repo page:
1. Click **"uploading an existing file"**
2. Drag & drop ALL files from this folder (the ones you got from Claude)
3. Click **Commit changes**

> ⚠️ Do NOT upload any `.env` file — your keys stay private!

## Step 4 — Deploy on Streamlit Cloud
1. Go to https://share.streamlit.io
2. Sign in with your **GitHub account**
3. Click **"New app"**
4. Fill in:
   - **Repository:** `your-username/crypto-htf-scanner`
   - **Branch:** `main`
   - **Main file path:** `dashboard/app.py`
5. Click **Deploy!**

## Step 5 — Wait ~2-3 minutes
Streamlit will install packages and start your app.
You'll get a free URL like:
`https://your-username-crypto-htf-scanner-dashboard-app-xxxxx.streamlit.app`

## ✅ That's it! Your scanner is live for free.

---

## Notes
- The app uses **public APIs only** — no API keys needed for Binance/MEXC market data
- WhatsApp alerts (OpenClaw) are disabled by default — they only activate if you add the key
- The scanner auto-refreshes prices every 30 seconds
- First scan takes ~5 minutes to load all 100 tokens
