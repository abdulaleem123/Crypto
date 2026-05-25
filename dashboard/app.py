"""
dashboard/app.py — Streamlit Cloud compatible with live progress
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from config import dashboard_config, scanner_config
from scheduler.scanner_scheduler import ScannerScheduler
from dashboard.table_builder import TableBuilder
from dashboard.color_rules import apply_color_rules

st.set_page_config(
    page_title="🦖 Godzilla HTF Scanner",
    page_icon="🦖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Auto-refresh every 30 seconds
st_autorefresh(interval=30_000, key="scanner_refresh")


@st.cache_resource
def get_scanner() -> ScannerScheduler:
    import shutil
    if os.path.exists(".cache"):
        try:
            shutil.rmtree(".cache")
        except Exception:
            pass
    scanner = ScannerScheduler()
    scanner.start()
    return scanner


# ── Safe scanner init with error display ─────────────────────────────────────
try:
    scanner = get_scanner()
except Exception as e:
    st.error(f"❌ Scanner failed to start: {e}")
    st.code(str(e))
    st.stop()

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Filters")
    exchange_filter = st.selectbox("Exchange", ["All", "Binance", "MEXC Only"])
    zone_filter = st.multiselect("Zone Type", ["Near OB", "Near FVG", "OB + FVG"], default=[])
    min_score = st.slider("Min Score", 0, 100, 0, 5)
    tf_filter = st.multiselect("TF must include", ["4h", "1d", "3d", "1w", "1M"], default=[])
    show_mexc = st.checkbox("MEXC small caps only", value=False)
    top_n = st.number_input("Max rows", 10, 500, 100)
    st.divider()
    st.caption(f"🔄 Prices: every 30s")
    st.caption(f"📊 Scan: every {scanner_config.scan_interval_minutes} min")
    if st.button("🔄 Force Rescan"):
        with st.spinner("Scanning..."):
            scanner.run_scan()
        st.success("Done!")

# ─── Header ───────────────────────────────────────────────────────────────────
st.title("🦖 Godzilla HTF OB & FVG Scanner")
st.caption("🟢 Live prices every 30s | Timeframes: 4H, Daily, 3D, Weekly, Monthly")

# ─── Status metrics ───────────────────────────────────────────────────────────
status = scanner.status
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Tokens Scanned", status["total_tokens"])
c2.metric("Near Zones",     status["near_zone_tokens"])
c3.metric("Scans Done",     status["scan_count"])
c4.metric("Last Scan",      status["last_scan"])
c5.metric("Status", "🟢 Live" if not status["is_running"] else "🔄 Scanning...")

# ─── Godzilla BTC Panel ───────────────────────────────────────────────────────
gz = status.get("godzilla", {})
if gz and gz.get("direction"):
    st.divider()
    st.subheader("🦖 Godzilla BTC Signal")
    g1, g2, g3, g4, g5 = st.columns(5)
    icon = "🟢" if gz["direction"] == "LONG" else "🔴"
    g1.metric("Direction",     f"{icon} {gz['direction']}")
    g2.metric("Imbalance I_t", f"{gz['imbalance']:.4f}")
    g3.metric("Volatility σ",  f"{gz['volatility']:.4f}")
    g4.metric("Spread φ_t",    f"{gz['spread']:.6f}")
    g5.metric("Max Leverage",  f"{gz['max_leverage']:.1f}x")

st.divider()

# ─── Show progress while scanning ─────────────────────────────────────────────
tokens = scanner.results

if not tokens:
    if status["is_running"]:
        st.info("🔄 Scan in progress... page auto-refreshes every 30s.")
        st.progress(0.0, text="Fetching token data from Binance & MEXC...")
    else:
        st.warning("⏳ Scanner starting up... First scan takes ~5 minutes for 100 tokens.")
        st.info("This page will **automatically refresh** every 30 seconds. Just wait!")

        # Show a manual refresh button too
        if st.button("🔃 Refresh Now"):
            st.rerun()
    st.stop()

# ─── Filters ──────────────────────────────────────────────────────────────────
filtered = tokens[:]
if show_mexc or exchange_filter == "MEXC Only":
    filtered = [t for t in filtered if t.is_mexc_only]
elif exchange_filter == "Binance":
    filtered = [t for t in filtered if not t.is_mexc_only]

if "Near OB" in zone_filter:
    filtered = [t for t in filtered if t.near_ob_zone and not t.near_fvg_zone]
if "Near FVG" in zone_filter:
    filtered = [t for t in filtered if t.near_fvg_zone and not t.near_ob_zone]
if "OB + FVG" in zone_filter:
    filtered = [t for t in filtered if t.near_ob_zone and t.near_fvg_zone]

filtered = [t for t in filtered if t.proximity_score >= min_score]

if tf_filter:
    def has_tf(token, tfs):
        ob_tfs  = {ob.timeframe  for ob  in token.order_blocks}
        fvg_tfs = {fvg.timeframe for fvg in token.fvgs}
        return bool((ob_tfs | fvg_tfs) & set(tfs))
    filtered = [t for t in filtered if has_tf(t, tf_filter)]

filtered = filtered[:int(top_n)]

# ─── Tabs ─────────────────────────────────────────────────────────────────────
builder = TableBuilder()

tab1, tab2, tab3, tab4 = st.tabs([
    f"📊 All Tokens ({len(filtered)})",
    f"🟢 OB + FVG ({sum(1 for t in filtered if t.near_ob_zone and t.near_fvg_zone)})",
    f"🟩 OB Only ({sum(1 for t in filtered if t.near_ob_zone and not t.near_fvg_zone)})",
    f"🔴 FVG Only ({sum(1 for t in filtered if t.near_fvg_zone and not t.near_ob_zone)})",
])

with tab1:
    df = builder.build(filtered)
    st.dataframe(apply_color_rules(df), use_container_width=True, height=600)

with tab2:
    both = [t for t in filtered if t.near_ob_zone and t.near_fvg_zone]
    st.dataframe(apply_color_rules(builder.build(both)), use_container_width=True, height=600)

with tab3:
    ob_only = [t for t in filtered if t.near_ob_zone and not t.near_fvg_zone]
    st.dataframe(apply_color_rules(builder.build(ob_only)), use_container_width=True, height=600)

with tab4:
    fvg_only = [t for t in filtered if t.near_fvg_zone and not t.near_ob_zone]
    st.dataframe(apply_color_rules(builder.build(fvg_only)), use_container_width=True, height=600)

st.divider()
st.markdown("""
**🟢 Dark Green** = Near **OB + FVG** (strongest signal)  
**🟩 Light Green** = Near **OB only**  
**🔴 Red** = Near **FVG only**  
**🔵 Blue** = MEXC Small Cap  
⚠️ Not financial advice. Spot trading only.
""")