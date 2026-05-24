# """
# dashboard/color_rules.py
# ─────────────────────────
# Applies color highlighting to the token table based on zone proximity.

# Rules:
#   🟢 Dark green  (#1a5c2a) → Token near/inside FVG zone
#   🟩 Light green (#c8e6c9) → Token near/inside OB zone
#   🔵 Blue        (#bbdefb) → MEXC-only small cap (secondary color)

# FVG takes priority over OB if both apply.
# """

# import pandas as pd


# # ─── Color Constants ─────────────────────────────────────────────────────────
# COLOR_FVG   = "#1a5c2a"        # Dark green background
# COLOR_FVG_TEXT = "#ffffff"     # White text on dark green

# COLOR_OB    = "#c8e6c9"        # Light green background
# COLOR_OB_TEXT = "#1b5e20"      # Dark green text on light green

# COLOR_MEXC  = "#bbdefb"        # Light blue background
# COLOR_MEXC_TEXT = "#0d47a1"    # Dark blue text

# COLOR_DEFAULT = ""             # No color


# def apply_color_rules(df: pd.DataFrame):
#     """
#     Apply row-level color coding to the DataFrame based on zone proximity.

#     Args:
#         df: DataFrame from TableBuilder.build()

#     Returns:
#         Pandas Styler object with color rules applied
#     """
#     if df.empty:
#         return df.style

#     def row_style(row):
#         near_zone = row.get("Near Zone", "")
#         exchange = row.get("Exchange", "")
#         small_cap = row.get("Small Cap", "")

#         styles = [""] * len(row)

#         if "FVG" in str(near_zone):
#             # Dark green for FVG
#             styles = [
#                 f"background-color: {COLOR_FVG}; color: {COLOR_FVG_TEXT}; font-weight: bold"
#             ] * len(row)

#         elif "OB" in str(near_zone):
#             # Light green for OB
#             styles = [
#                 f"background-color: {COLOR_OB}; color: {COLOR_OB_TEXT}"
#             ] * len(row)

#         elif small_cap == "✅" or "MEXC" in str(exchange):
#             # Light blue for MEXC-only small caps
#             styles = [
#                 f"background-color: {COLOR_MEXC}; color: {COLOR_MEXC_TEXT}"
#             ] * len(row)

#         return styles

#     return df.style.apply(row_style, axis=1)

"""
dashboard/color_rules.py
Color rules:
  DARK GREEN  = Near BOTH OB + FVG
  LIGHT GREEN = Near OB only
  RED         = Near FVG only
  BLUE        = MEXC small cap only
"""

import pandas as pd


def apply_color_rules(df: pd.DataFrame):
    if df.empty:
        return df.style

    def row_style(row):
        zone = str(row.get("Zone Signal", "—"))
        exchange = str(row.get("Exchange", ""))
        small_cap = str(row.get("Small Cap", ""))

        near_ob  = "OB"  in zone and zone != "—"
        near_fvg = "FVG" in zone and zone != "—"

        if near_ob and near_fvg:
            # DARK GREEN — both OB + FVG confluence
            style = "background-color: #1b5e20; color: #ffffff; font-weight: bold"
        elif near_ob:
            # LIGHT GREEN — OB only
            style = "background-color: #a5d6a7; color: #1b5e20; font-weight: bold"
        elif near_fvg:
            # RED — FVG only
            style = "background-color: #b71c1c; color: #ffffff; font-weight: bold"
        elif small_cap == "✅" or "MEXC" in exchange:
            # BLUE — MEXC small cap
            style = "background-color: #bbdefb; color: #0d47a1"
        else:
            return [""] * len(row)

        return [style] * len(row)

    return df.style.apply(row_style, axis=1)