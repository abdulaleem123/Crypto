# """
# dashboard/table_builder.py
# ───────────────────────────
# Builds the pandas DataFrame for the dashboard.
# Now shows FVG midpoint (key buying zone) prominently.
# """

# import pandas as pd
# from typing import List
# from models.token import Token


# class TableBuilder:

#     def build(self, tokens: List[Token]) -> pd.DataFrame:
#         if not tokens:
#             return pd.DataFrame()
#         rows = [self._build_row(t) for t in tokens]
#         return pd.DataFrame(rows)

#     def _build_row(self, token: Token) -> dict:
#         price = token.current_price

#         def fmt(p):
#             if p == 0: return "—"
#             if p < 0.000001: return f"{p:.10f}"
#             if p < 0.0001: return f"{p:.8f}"
#             if p < 0.01: return f"{p:.6f}"
#             if p < 1: return f"{p:.4f}"
#             return f"{p:.3f}"

#         # OBs grouped by timeframe
#         ob_by_tf = {}
#         for ob in token.order_blocks:
#             if ob.is_active and ob.ob_type == "bullish" and ob.timeframe not in ob_by_tf:
#                 ob_by_tf[ob.timeframe] = f"{fmt(ob.low)}–{fmt(ob.high)}"

#         # FVGs grouped by timeframe — show MIDPOINT prominently
#         fvg_by_tf = {}
#         fvg_mid_by_tf = {}
#         for fvg in token.fvgs:
#             if not fvg.is_filled and fvg.fvg_type == "bullish" and fvg.timeframe not in fvg_by_tf:
#                 fvg_by_tf[fvg.timeframe] = f"{fmt(fvg.bottom)}–{fmt(fvg.top)}"
#                 fvg_mid_by_tf[fvg.timeframe] = fmt(fvg.midpoint)

#         # TP levels
#         tp = {}
#         for sz in token.supply_zones[:3]:
#             tp[sz.tp_priority] = f"{fmt(sz.level)} [{sz.timeframe.upper()}]"

#         zone_status = []
#         if token.near_fvg_zone: zone_status.append("FVG")
#         if token.near_ob_zone: zone_status.append("OB")

#         return {
#             "Token":        token.symbol,
#             "Exchange":     "🔵 MEXC" if token.is_mexc_only else token.exchange.capitalize(),
#             "Price (LIVE)": fmt(price),
#             "24h %":        f"{token.price_change_24h_pct:+.2f}%",
#             "Score":        f"{token.proximity_score:.0f}",
#             "Near Zone":    " + ".join(zone_status) if zone_status else "—",
#             # OB columns
#             "OB 4H":        ob_by_tf.get("4h", "—"),
#             "OB Daily":     ob_by_tf.get("1d", "—"),
#             "OB Weekly":    ob_by_tf.get("1w", "—"),
#             "OB Monthly":   ob_by_tf.get("1M", "—"),
#             # FVG zone columns
#             "FVG 4H":       fvg_by_tf.get("4h", "—"),
#             "FVG Daily":    fvg_by_tf.get("1d", "—"),
#             "FVG Weekly":   fvg_by_tf.get("1w", "—"),
#             "FVG Monthly":  fvg_by_tf.get("1M", "—"),
#             # FVG midpoint columns (key buy zone)
#             "FVG Mid 4H":   fvg_mid_by_tf.get("4h", "—"),
#             "FVG Mid Daily":fvg_mid_by_tf.get("1d", "—"),
#             "FVG Mid Wkly": fvg_mid_by_tf.get("1w", "—"),
#             "FVG Mid Mnth": fvg_mid_by_tf.get("1M", "—"),
#             # TP levels
#             "TP1":          tp.get(1, "—"),
#             "TP2":          tp.get(2, "—"),
#             "TP3":          tp.get(3, "—"),
#             "Vol (USDT)":   self._fmt_vol(token.volume_24h_usdt),
#             "Small Cap":    "✅" if token.is_mexc_only else "",
#         }

#     def _fmt_vol(self, v: float) -> str:
#         if v >= 1_000_000_000: return f"${v/1e9:.1f}B"
#         if v >= 1_000_000: return f"${v/1e6:.1f}M"
#         if v >= 1_000: return f"${v/1e3:.0f}K"
#         return f"${v:.0f}"

"""
dashboard/table_builder.py
- No 12H columns
- No FVG Mid Daily
- Keep FVG Mid 4H, 3D, Weekly, Monthly
- Zone Signal column prominent
"""

import pandas as pd
from typing import List
from models.token import Token


class TableBuilder:

    def build(self, tokens: List[Token]) -> pd.DataFrame:
        if not tokens:
            return pd.DataFrame()
        return pd.DataFrame([self._build_row(t) for t in tokens])

    def _build_row(self, token: Token) -> dict:
        price = token.current_price

        def fmt(p):
            if not p or p == 0: return "—"
            if p < 0.000001: return f"{p:.10f}"
            if p < 0.0001:   return f"{p:.8f}"
            if p < 0.01:     return f"{p:.6f}"
            if p < 1:        return f"{p:.4f}"
            return f"{p:.3f}"

        # OBs — NO 12H
        ob_by_tf = {}
        for ob in token.order_blocks:
            if ob.is_active and ob.ob_type == "bullish" and ob.timeframe not in ob_by_tf:
                if ob.timeframe != "12h":
                    ob_by_tf[ob.timeframe] = f"{fmt(ob.low)}–{fmt(ob.high)}"

        # FVGs — NO 12H, NO FVG Mid Daily
        fvg_by_tf = {}
        fvg_mid_by_tf = {}
        for fvg in token.fvgs:
            if not fvg.is_filled and fvg.fvg_type == "bullish" and fvg.timeframe not in fvg_by_tf:
                if fvg.timeframe != "12h":
                    fvg_by_tf[fvg.timeframe] = f"{fmt(fvg.bottom)}–{fmt(fvg.top)}"
                    # Only mid for 4H, 3D, Weekly, Monthly — NOT daily
                    if fvg.timeframe in ("4h", "3d", "1w", "1M"):
                        fvg_mid_by_tf[fvg.timeframe] = fmt(fvg.midpoint)

        # TP levels
        tp = {}
        for sz in token.supply_zones[:3]:
            tp[sz.tp_priority] = f"{fmt(sz.level)} [{sz.timeframe.upper()}]"

        return {
            "Token":          token.symbol,
            "Exchange":       "🔵 MEXC" if token.is_mexc_only else token.exchange.capitalize(),
            "Price (LIVE)":   fmt(price),
            "24h %":          f"{token.price_change_24h_pct:+.2f}%",
            "Score":          f"{token.proximity_score:.0f}",
            "Zone Signal":    token.near_zone_label,   # e.g. NEAR 1D OB, INSIDE 4H FVG
            # OB columns (no 12H)
            "OB 4H":          ob_by_tf.get("4h",  "—"),
            "OB Daily":       ob_by_tf.get("1d",  "—"),
            "OB 3D":          ob_by_tf.get("3d",  "—"),
            "OB Weekly":      ob_by_tf.get("1w",  "—"),
            "OB Monthly":     ob_by_tf.get("1M",  "—"),
            # FVG zone columns (no 12H)
            "FVG 4H":         fvg_by_tf.get("4h",  "—"),
            "FVG Daily":      fvg_by_tf.get("1d",  "—"),
            "FVG 3D":         fvg_by_tf.get("3d",  "—"),
            "FVG Weekly":     fvg_by_tf.get("1w",  "—"),
            "FVG Monthly":    fvg_by_tf.get("1M",  "—"),
            # FVG midpoints — no daily mid
            "FVG Mid 4H":     fvg_mid_by_tf.get("4h",  "—"),
            "FVG Mid 3D":     fvg_mid_by_tf.get("3d",  "—"),
            "FVG Mid Weekly": fvg_mid_by_tf.get("1w",  "—"),
            "FVG Mid Monthly":fvg_mid_by_tf.get("1M",  "—"),
            # TP levels
            "TP1":            tp.get(1, "—"),
            "TP2":            tp.get(2, "—"),
            "TP3":            tp.get(3, "—"),
            "Vol (USDT)":     self._fmt_vol(token.volume_24h_usdt),
            "Small Cap":      "✅" if token.is_mexc_only else "",
        }

    def _fmt_vol(self, v: float) -> str:
        if v >= 1_000_000_000: return f"${v/1e9:.1f}B"
        if v >= 1_000_000:     return f"${v/1e6:.1f}M"
        if v >= 1_000:         return f"${v/1e3:.0f}K"
        return f"${v:.0f}"