"""
Webhook notification system.
Sends HTTP POST notifications for system events.
"""

import json
import logging
import urllib.request
import urllib.error
from typing import Optional


class NotificationManager:
    """Sends webhook notifications for system events."""

    def __init__(self, webhook_url: str = "", enabled: bool = False):
        self.webhook_url = webhook_url
        self.enabled = enabled and bool(webhook_url)
        self.logger = logging.getLogger(__name__)

        if self.enabled:
            self.logger.info(f"Notifications enabled (webhook: {webhook_url[:30]}...)")
        else:
            self.logger.debug("Notifications disabled")

    def notify(self, event: str, message: str, level: str = "info") -> bool:
        """Send a notification.

        Args:
            event: Event type (e.g., 'startup', 'obs_crash', 'webdav_failure')
            message: Human-readable message
            level: Severity level ('info', 'warning', 'error')

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            return False

        payload = {
            "event": event,
            "message": message,
            "level": level,
            "source": "obs-digital-signage",
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status < 300:
                    self.logger.debug(f"Notification sent: {event}")
                    return True
                else:
                    self.logger.warning(f"Notification failed (HTTP {resp.status}): {event}")
                    return False
        except Exception as e:
            self.logger.warning(f"Notification send error: {e}")
            return False

    def notify_startup(self) -> bool:
        return self.notify("startup", "Digital signage system started")

    def notify_shutdown(self) -> bool:
        return self.notify("shutdown", "Digital signage system stopped")

    def notify_obs_crash(self, details: str = "") -> bool:
        return self.notify("obs_crash", f"OBS connection lost. {details}".strip(), level="error")

    def notify_webdav_failure(self, details: str = "") -> bool:
        return self.notify("webdav_failure", f"WebDAV sync failed. {details}".strip(), level="warning")
