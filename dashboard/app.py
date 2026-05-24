# """
# dashboard/app.py
# ─────────────────
# Main Streamlit dashboard. Live prices refresh every 30s.
# """

# import sys, os
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# import streamlit as st
# from streamlit_autorefresh import st_autorefresh
# import pandas as pd

# from config import dashboard_config, scanner_config
# from scheduler.scanner_scheduler import ScannerScheduler
# from dashboard.table_builder import TableBuilder
# from dashboard.color_rules import apply_color_rules

# st.set_page_config(
#     page_title=dashboard_config.title,
#     page_icon="🔍",
#     layout="wide",
#     initial_sidebar_state="expanded",
# )

# # Auto-refresh every 30 seconds (for live prices)
# st_autorefresh(interval=30_000, key="scanner_refresh")


# @st.cache_resource
# def get_scanner() -> ScannerScheduler:
#     scanner = ScannerScheduler()
#     scanner.start()
#     return scanner


# scanner = get_scanner()

# # ─── Sidebar ──────────────────────────────────────────────────────────────────
# with st.sidebar:
#     st.title("⚙️ Filters")

#     exchange_filter = st.selectbox("Exchange", ["All", "Binance", "MEXC Only (Small Caps)"])
#     zone_filter = st.multiselect("Zone Type", ["Near OB", "Near FVG", "Both OB + FVG"], default=[])
#     min_score = st.slider("Min Score", 0, 100, 0, 5)
#     timeframe_filter = st.multiselect("TF must include", ["4h", "1d", "1w", "1M"], default=[])
#     show_mexc_only = st.checkbox("MEXC small caps only", value=False)
#     top_n = st.number_input("Max rows", min_value=10, max_value=500, value=100)

#     st.divider()
#     st.caption(f"Prices refresh: every 30s")
#     st.caption(f"OB/FVG scan: every {scanner_config.scan_interval_minutes} min")
#     if st.button("🔄 Force Rescan"):
#         with st.spinner("Scanning..."):
#             scanner.run_scan()
#         st.success("Done!")

# # ─── Header ───────────────────────────────────────────────────────────────────
# st.title(dashboard_config.title)
# st.caption("🟢 Live prices refresh every 30s | OB/FVG analysis uses 1 year of candle data")

# status = scanner.status
# c1, c2, c3, c4, c5 = st.columns(5)
# c1.metric("Total Tokens", status["total_tokens"])
# c2.metric("Near Zones", status["near_zone_tokens"])
# c3.metric("Scans Run", status["scan_count"])
# c4.metric("Last Scan", status["last_scan"])
# c5.metric("Status", "🟢 Live" if not status["is_running"] else "🔄 Scanning")

# st.divider()

# tokens = scanner.results
# if not tokens:
#     st.info("⏳ First scan in progress... This may take a few minutes.")
#     st.stop()

# # ─── Filter ───────────────────────────────────────────────────────────────────
# filtered = tokens[:]

# if show_mexc_only or exchange_filter == "MEXC Only (Small Caps)":
#     filtered = [t for t in filtered if t.is_mexc_only]
# elif exchange_filter == "Binance":
#     filtered = [t for t in filtered if not t.is_mexc_only]

# if "Near OB" in zone_filter:
#     filtered = [t for t in filtered if t.near_ob_zone]
# if "Near FVG" in zone_filter:
#     filtered = [t for t in filtered if t.near_fvg_zone]
# if "Both OB + FVG" in zone_filter:
#     filtered = [t for t in filtered if t.near_ob_zone and t.near_fvg_zone]

# filtered = [t for t in filtered if t.proximity_score >= min_score]

# if timeframe_filter:
#     def has_tf(token, tfs):
#         ob_tfs = {ob.timeframe for ob in token.order_blocks}
#         fvg_tfs = {fvg.timeframe for fvg in token.fvgs}
#         return bool((ob_tfs | fvg_tfs) & set(tfs))
#     filtered = [t for t in filtered if has_tf(t, timeframe_filter)]

# filtered = filtered[:int(top_n)]

# # ─── Table ────────────────────────────────────────────────────────────────────
# builder = TableBuilder()
# df = builder.build(filtered)
# styled_df = apply_color_rules(df)

# tab1, tab2, tab3, tab4 = st.tabs([
#     f"📊 All ({len(filtered)})",
#     f"🟩 Near OBs ({sum(1 for t in filtered if t.near_ob_zone)})",
#     f"🟢 Near FVGs ({sum(1 for t in filtered if t.near_fvg_zone)})",
#     f"🔵 MEXC Small Caps ({sum(1 for t in filtered if t.is_mexc_only)})",
# ])

# with tab1:
#     st.dataframe(styled_df, width='stretch', height=600)
# with tab2:
#     ob_df = builder.build([t for t in filtered if t.near_ob_zone])
#     st.dataframe(apply_color_rules(ob_df), width='stretch', height=600)
# with tab3:
#     fvg_df = builder.build([t for t in filtered if t.near_fvg_zone])
#     st.dataframe(apply_color_rules(fvg_df), width='stretch', height=600)
# with tab4:
#     mexc_df = builder.build([t for t in filtered if t.is_mexc_only])
#     st.dataframe(apply_color_rules(mexc_df), width='stretch', height=600)

# st.divider()
# st.markdown("""
# **Color:** 🟢 Dark Green = Near **FVG** zone | 🟩 Light Green = Near **OB** zone | 🔵 Blue = MEXC Small Cap  
# **FVG Mid** columns = midpoint of the gap (where largest buy orders cluster)  
# ⚠️ Not financial advice. Spot only.
# """)

"""
dashboard/app.py — saves results, clears cache on start, correct colors
"""

import sys, os, json, time
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

# Auto-refresh every 30 seconds for live prices
st_autorefresh(interval=30_000, key="scanner_refresh")


@st.cache_resource
def get_scanner() -> ScannerScheduler:
    # Delete old corrupted cache on fresh start
    import shutil
    if os.path.exists(".cache"):
        try:
            shutil.rmtree(".cache")
        except Exception:
            pass
    scanner = ScannerScheduler()
    scanner.start()
    return scanner


scanner = get_scanner()

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
    st.caption(f"💾 100 tokens, results saved")
    if st.button("🔄 Force Rescan"):
        with st.spinner("Scanning..."):
            scanner.run_scan()
        st.success("Done!")

# ─── Header ───────────────────────────────────────────────────────────────────
st.title("🦖 Godzilla HTF OB & FVG Scanner")
st.caption("🟢 Live prices every 30s | Timeframes: 4H, Daily, 3D, Weekly, Monthly")

# ─── Status ───────────────────────────────────────────────────────────────────
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
    note = "🔻 High Vol → Lower Leverage" if gz.get('volatility', 0) > 0.02 else "🔺 Low Vol → More Leverage Allowed"
    st.caption(f"V_bid: {gz.get('v_bid',0):,.0f} | V_ask: {gz.get('v_ask',0):,.0f} | {note}")

st.divider()

# ─── Token Table ──────────────────────────────────────────────────────────────
tokens = scanner.results
if not tokens:
    st.info("⏳ First scan running... Takes ~5 mins for 100 tokens. Results will appear automatically.")
    st.stop()

# Apply filters
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
        ob_tfs = {ob.timeframe for ob in token.order_blocks}
        fvg_tfs = {fvg.timeframe for fvg in token.fvgs}
        return bool((ob_tfs | fvg_tfs) & set(tfs))
    filtered = [t for t in filtered if has_tf(t, tf_filter)]

filtered = filtered[:int(top_n)]

builder = TableBuilder()

tab1, tab2, tab3, tab4 = st.tabs([
    f"📊 All Tokens ({len(filtered)})",
    f"🟢 OB + FVG ({sum(1 for t in filtered if t.near_ob_zone and t.near_fvg_zone)})",
    f"🟩 OB Only ({sum(1 for t in filtered if t.near_ob_zone and not t.near_fvg_zone)})",
    f"🔴 FVG Only ({sum(1 for t in filtered if t.near_fvg_zone and not t.near_ob_zone)})",
])

with tab1:
    df = builder.build(filtered)
    st.dataframe(apply_color_rules(df), width='stretch', height=600)

with tab2:
    both = [t for t in filtered if t.near_ob_zone and t.near_fvg_zone]
    st.dataframe(apply_color_rules(builder.build(both)), width='stretch', height=600)

with tab3:
    ob_only = [t for t in filtered if t.near_ob_zone and not t.near_fvg_zone]
    st.dataframe(apply_color_rules(builder.build(ob_only)), width='stretch', height=600)

with tab4:
    fvg_only = [t for t in filtered if t.near_fvg_zone and not t.near_ob_zone]
    st.dataframe(apply_color_rules(builder.build(fvg_only)), width='stretch', height=600)

st.divider()
st.markdown("""
**🟢 Dark Green** = Near **OB + FVG** (strongest signal)  
**🟩 Light Green** = Near **OB only**  
**🔴 Red** = Near **FVG only**  
**🔵 Blue** = MEXC Small Cap  
**Zone Signal** = e.g. `NEAR 1D OB`, `INSIDE 4H FVG`, `NEAR WEEKLY FVG + 1D OB`  
⚠️ Not financial advice. Spot trading only.
""")