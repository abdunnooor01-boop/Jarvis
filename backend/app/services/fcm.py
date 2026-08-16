"""Firebase Cloud Messaging (FCM) service for push notifications.

Sends push notifications to registered device tokens via FCM HTTP v1 API.
Gracefully falls back when Firebase is not configured.
"""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class FCMService:
    """Firebase Cloud Messaging service.

    Sends push notifications to iOS, Android, and web devices.
    Uses Firebase Admin SDK when configured, otherwise logs silently.
    """

    def __init__(self) -> None:
        self._initialized = False
        self._firebase_app: Any = None

    async def initialize(self) -> bool:
        """Initialize the Firebase Admin SDK.

        Returns True if initialized successfully, False if not configured.
        """
        if self._initialized:
            return True

        if not settings.firebase_credentials_path:
            logger.info("Firebase not configured — push notifications disabled")
            return False

        try:
            import firebase_admin
            from firebase_admin import credentials

            cred = credentials.Certificate(settings.firebase_credentials_path)
            self._firebase_app = firebase_admin.initialize_app(cred)
            self._initialized = True
            logger.info("Firebase Admin SDK initialized")
            return True
        except Exception as e:
            logger.error("Failed to initialize Firebase", error=str(e))
            return False

    async def send_push(
        self,
        token: str,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> bool:
        """Send a push notification to a single device token.

        Returns True if sent successfully, False otherwise.
        """
        if not self._initialized:
            ok = await self.initialize()
            if not ok:
                logger.debug(
                    "Push not sent — Firebase not configured",
                    title=title,
                )
                return False

        try:
            from firebase_admin import messaging

            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
                token=token,
            )

            response = messaging.send(message)
            logger.info(
                "Push notification sent",
                response=response,
                token_prefix=token[:12],
            )
            return True
        except Exception as e:
            logger.error("Failed to send push notification", error=str(e))
            return False

    async def send_multicast(
        self,
        tokens: list[str],
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> dict[str, int]:
        """Send a push notification to multiple device tokens.

        Returns dict with success_count and failure_count.
        """
        if not self._initialized:
            ok = await self.initialize()
            if not ok:
                logger.debug(
                    "Multicast push not sent — Firebase not configured",
                    title=title,
                    device_count=len(tokens),
                )
                return {"success_count": 0, "failure_count": len(tokens)}

        try:
            from firebase_admin import messaging

            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
            )

            response = messaging.send_each(message, tokens)
            logger.info(
                "Multicast push sent",
                success=response.success_count,
                failure=response.failure_count,
            )
            return {
                "success_count": response.success_count,
                "failure_count": response.failure_count,
            }
        except Exception as e:
            logger.error("Failed to send multicast push", error=str(e))
            return {"success_count": 0, "failure_count": len(tokens)}


# Singleton
_fcm_service: FCMService | None = None


def get_fcm_service() -> FCMService:
    """Get or create the FCMService singleton."""
    global _fcm_service
    if _fcm_service is None:
        _fcm_service = FCMService()
    return _fcm_service