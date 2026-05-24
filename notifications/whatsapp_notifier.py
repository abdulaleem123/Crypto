"""
notifications/whatsapp_notifier.py
────────────────────────────────────
Sends WhatsApp alerts via OpenClaw API when a token enters a strong HTF zone.

OpenClaw API docs: https://openclaw.io/docs
Endpoint: POST https://api.openclaw.io/v1/messages/send

Alerts are triggered when:
  - Token enters or is within threshold of an HTF OB or FVG
  - Proximity score exceeds the configured minimum
"""

import requests
from typing import Optional
from loguru import logger

from config import notification_config
from models.token import Token
from notifications.alert_templates import AlertTemplates


class WhatsAppNotifier:
    """
    Sends WhatsApp messages via OpenClaw for high-priority zone alerts.
    """

    OPENCLAW_API_URL = "https://api.openclaw.io/v1/messages/send"

    def __init__(self):
        self.api_key = notification_config.openclaw_api_key
        self.phone = notification_config.openclaw_phone
        self.min_score = notification_config.alert_min_score
        self._sent_alerts: set = set()   # Track sent alerts to avoid spam

    def should_alert(self, token: Token) -> bool:
        """
        Determine if this token warrants a WhatsApp alert.

        Conditions:
          - Score above minimum threshold
          - OB alert enabled AND token near OB, OR
          - FVG alert enabled AND token near FVG
          - Not already alerted for this token+zone combo
        """
        if token.proximity_score < self.min_score:
            return False

        ob_alert = notification_config.alert_on_ob and token.near_ob_zone
        fvg_alert = notification_config.alert_on_fvg and token.near_fvg_zone

        if not ob_alert and not fvg_alert:
            return False

        # Dedup key: symbol + zone type + rounded price (avoids spam)
        rounded_price = round(token.current_price, 4)
        zone_type = "ob" if token.near_ob_zone else "fvg"
        alert_key = f"{token.symbol}:{zone_type}:{rounded_price}"

        if alert_key in self._sent_alerts:
            return False

        self._sent_alerts.add(alert_key)
        return True

    def send_zone_alert(self, token: Token) -> bool:
        """
        Send a WhatsApp alert for a token entering a demand zone.

        Args:
            token: Token near an OB or FVG zone

        Returns:
            True if message sent successfully
        """
        if not self.api_key or not self.phone:
            logger.warning("OpenClaw API key or phone number not configured — skipping alert")
            return False

        # Build message from template
        if token.near_fvg_zone and token.nearest_fvg:
            message = AlertTemplates.fvg_alert(token)
        elif token.near_ob_zone and token.nearest_ob:
            message = AlertTemplates.ob_alert(token)
        else:
            return False

        return self._send_message(message)

    def send_summary(self, tokens: list, top_n: int = 5) -> bool:
        """
        Send a periodic summary of the top N tokens near zones.

        Args:
            tokens: Sorted list of Token objects (highest score first)
            top_n:  Number of tokens to include in summary
        """
        if not self.api_key or not self.phone:
            return False

        message = AlertTemplates.summary_alert(tokens[:top_n])
        return self._send_message(message)

    def _send_message(self, message: str) -> bool:
        """
        Make the HTTP request to OpenClaw API.

        Args:
            message: Formatted text message to send

        Returns:
            True on success, False on failure
        """
        payload = {
            "phone": self.phone,
            "message": message,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                self.OPENCLAW_API_URL,
                json=payload,
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()
            logger.info(f"WhatsApp alert sent: {message[:60]}...")
            return True

        except requests.exceptions.Timeout:
            logger.error("OpenClaw API timeout")
            return False
        except requests.exceptions.HTTPError as e:
            logger.error(f"OpenClaw HTTP error: {e.response.status_code} — {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"OpenClaw unexpected error: {e}")
            return False

    def clear_alert_cache(self) -> None:
        """Clear dedup cache — call periodically to re-enable alerts."""
        self._sent_alerts.clear()
        logger.info("Alert dedup cache cleared")
