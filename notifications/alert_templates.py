"""
notifications/alert_templates.py
──────────────────────────────────
WhatsApp message templates for different alert types.
Keeps messages concise and scannable on mobile.
"""

from typing import List
from models.token import Token


class AlertTemplates:
    """Static factory methods that return formatted WhatsApp message strings."""

    @staticmethod
    def ob_alert(token: Token) -> str:
        """Alert: Token approaching or entering an HTF Order Block."""
        ob = token.nearest_ob
        tf_label = ob.timeframe.upper() if ob else "HTF"
        price_fmt = f"{token.current_price:.6f}" if token.current_price < 0.01 else f"{token.current_price:.4f}"
        ob_range = f"{ob.low:.6f}–{ob.high:.6f}" if ob else "N/A"

        tp_info = ""
        if token.supply_zones:
            sz = token.supply_zones[0]
            tp_info = f"\n🎯 TP1: {sz.level:.6f} [{sz.timeframe.upper()}]"

        return (
            f"🟢 *ORDER BLOCK ALERT*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💎 *{token.symbol}*\n"
            f"💰 Price: {price_fmt}\n"
            f"📊 TF: {tf_label} OB\n"
            f"📍 Zone: {ob_range}\n"
            f"🔥 Score: {token.proximity_score:.0f}/100"
            f"{tp_info}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ Spot only | DYOR"
        )

    @staticmethod
    def fvg_alert(token: Token) -> str:
        """Alert: Token approaching or entering an HTF Fair Value Gap."""
        fvg = token.nearest_fvg
        tf_label = fvg.timeframe.upper() if fvg else "HTF"
        price_fmt = f"{token.current_price:.6f}" if token.current_price < 0.01 else f"{token.current_price:.4f}"
        fvg_range = f"{fvg.bottom:.6f}–{fvg.top:.6f}" if fvg else "N/A"
        fill_pct = f"{fvg.fill_pct:.0f}% filled" if fvg else ""

        tp_info = ""
        if token.supply_zones:
            sz = token.supply_zones[0]
            tp_info = f"\n🎯 TP1: {sz.level:.6f} [{sz.timeframe.upper()}]"
            if len(token.supply_zones) > 1:
                sz2 = token.supply_zones[1]
                tp_info += f"\n🎯 TP2: {sz2.level:.6f} [{sz2.timeframe.upper()}]"

        mexc_tag = "\n🔵 *MEXC Small Cap*" if token.is_mexc_only else ""

        return (
            f"🟩 *FVG ALERT*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💎 *{token.symbol}*{mexc_tag}\n"
            f"💰 Price: {price_fmt}\n"
            f"📊 TF: {tf_label} FVG ({fill_pct})\n"
            f"📍 Gap: {fvg_range}\n"
            f"🔥 Score: {token.proximity_score:.0f}/100"
            f"{tp_info}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ Spot only | DYOR"
        )

    @staticmethod
    def summary_alert(tokens: List[Token]) -> str:
        """Periodic summary of top tokens near zones."""
        if not tokens:
            return "📊 Scanner update: No tokens near HTF zones currently."

        lines = ["📊 *HTF ZONE SCANNER — TOP PICKS*", "━━━━━━━━━━━━━━━━━━━━"]

        for i, token in enumerate(tokens, 1):
            price_fmt = (
                f"{token.current_price:.6f}"
                if token.current_price < 0.01
                else f"{token.current_price:.4f}"
            )
            zone_type = []
            if token.near_fvg_zone:
                zone_type.append("FVG")
            if token.near_ob_zone:
                zone_type.append("OB")
            zone_str = " + ".join(zone_type) if zone_type else "Approaching"
            mexc_tag = " 🔵" if token.is_mexc_only else ""

            lines.append(
                f"{i}. *{token.symbol}*{mexc_tag} @ {price_fmt}\n"
                f"   → {zone_str} | Score: {token.proximity_score:.0f}"
            )

        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("⚡ Spot only | DYOR | Not financial advice")

        return "\n".join(lines)
