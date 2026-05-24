"""
analysis/scoring_engine.py
───────────────────────────
Scores each token 0–100 based on proximity to zones and zone quality.

Higher score = higher priority in the dashboard table.

Scoring factors:
  - Distance to nearest OB or FVG (closer = higher score)
  - Timeframe of the zone (higher TF = more weight)
  - Whether price is already inside the zone (max bonus)
  - OB impulse size (stronger move = more institutional interest)
  - FVG gap size (larger gap = stronger imbalance)
  - Confluence (both OB and FVG near same level = bonus)
"""

from typing import List
from loguru import logger

from models.token import Token
from data.timeframe_manager import TimeframeManager
from analysis.proximity_checker import ProximityChecker


class ScoringEngine:
    """
    Assigns a proximity_score (0–100) to each token.
    Tokens are then sorted descending by this score in the dashboard.
    """

    def __init__(self):
        self.proximity_checker = ProximityChecker()

    def score_token(self, token: Token) -> Token:
        """
        Calculate and assign token.proximity_score.

        Args:
            token: Token with OBs, FVGs, supply zones already populated

        Returns:
            Token with proximity_score set
        """
        score = 0.0
        price = token.current_price

        if price == 0:
            token.proximity_score = 0.0
            return token

        # ── 1. OB Score ───────────────────────────────────────────────────────
        ob_score = self._score_obs(token, price)
        score += ob_score

        # ── 2. FVG Score ─────────────────────────────────────────────────────
        fvg_score = self._score_fvgs(token, price)
        score += fvg_score

        # ── 3. Confluence Bonus ───────────────────────────────────────────────
        if ob_score > 0 and fvg_score > 0:
            score += 10.0  # Both OB and FVG near same price

        # ── 4. Inside Zone Bonus ─────────────────────────────────────────────
        if self.proximity_checker.is_inside_any_zone(token):
            score += 15.0

        # ── 5. Higher Volume Bonus (more liquid = more reliable) ──────────────
        if token.volume_24h_usdt >= 10_000_000:
            score += 5.0

        # Cap at 100
        token.proximity_score = min(round(score, 2), 100.0)
        return token

    def score_all(self, tokens: List[Token]) -> List[Token]:
        """
        Score all tokens and return sorted list (highest score first).
        Tokens near zones automatically bubble to the top.
        """
        logger.info(f"Scoring {len(tokens)} tokens...")
        scored = [self.score_token(t) for t in tokens]
        scored.sort(key=lambda t: t.proximity_score, reverse=True)
        logger.info(f"Scoring complete. Top token: {scored[0].symbol if scored else 'N/A'}")
        return scored

    # ─── Private Methods ─────────────────────────────────────────────────────

    def _score_obs(self, token: Token, price: float) -> float:
        """Score contribution from Order Blocks."""
        active_obs = [ob for ob in token.order_blocks if ob.is_active and ob.ob_type == "bullish"]
        if not active_obs:
            return 0.0

        best_score = 0.0
        for ob in active_obs:
            distance = ob.distance_to_price(price)

            if distance == -1:
                # Inside the zone
                proximity_score = 40.0
            elif distance <= 0.5:
                proximity_score = 35.0
            elif distance <= 1.0:
                proximity_score = 28.0
            elif distance <= 2.0:
                proximity_score = 20.0
            elif distance <= 5.0:
                proximity_score = 10.0
            else:
                proximity_score = 0.0

            # Apply timeframe weight multiplier
            tf_weight = TimeframeManager.weight(ob.timeframe)
            tf_multiplier = min(tf_weight / 4.0, 1.5)  # Normalize weight

            # Impulse quality bonus
            impulse_bonus = min(ob.impulse_size_pct / 10.0, 5.0)

            total = (proximity_score * tf_multiplier) + impulse_bonus
            best_score = max(best_score, total)

        return min(best_score, 45.0)

    def _score_fvgs(self, token: Token, price: float) -> float:
        """Score contribution from Fair Value Gaps."""
        active_fvgs = [f for f in token.fvgs if not f.is_filled and f.fvg_type == "bullish"]
        if not active_fvgs:
            return 0.0

        best_score = 0.0
        for fvg in active_fvgs:
            distance = fvg.distance_to_price(price)

            if distance == -1:
                proximity_score = 35.0
            elif distance <= 0.5:
                proximity_score = 30.0
            elif distance <= 1.0:
                proximity_score = 22.0
            elif distance <= 2.0:
                proximity_score = 15.0
            elif distance <= 5.0:
                proximity_score = 7.0
            else:
                proximity_score = 0.0

            tf_weight = TimeframeManager.weight(fvg.timeframe)
            tf_multiplier = min(tf_weight / 4.0, 1.5)

            # Larger gap = stronger imbalance bonus
            gap_bonus = min(fvg.gap_size_pct / 5.0, 5.0)

            total = (proximity_score * tf_multiplier) + gap_bonus
            best_score = max(best_score, total)

        return min(best_score, 40.0)
