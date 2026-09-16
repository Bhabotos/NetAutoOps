from typing import Any

from app.alerts.events import EventPayload, EventType, build_event_payload
from app.alerts.webhook_client import WebhookDeliveryError, WebhookNotConfiguredError, send_webhook
from app.models.device import Device
from app.utils.logger import get_logger

logger = get_logger(__name__)


def deliver_event(payload: EventPayload) -> bool:
    """Send an already-built EventPayload to n8n.

    Never raises: every failure mode (not configured, delivery failure, or
    anything unexpected) is caught and logged instead, so a broken or
    unreachable n8n instance can never crash a monitoring/backup run or the
    API request that triggered it. Returns True only on confirmed delivery.
    """
    try:
        send_webhook(payload.model_dump(mode="json"))
    except WebhookNotConfiguredError:
        logger.info(
            "N8N_WEBHOOK_URL not configured; skipping event=%s device_id=%s",
            payload.event.value, payload.device_id,
        )
        return False
    except WebhookDeliveryError as exc:
        logger.warning(
            "Event delivery failed event=%s device_id=%s reason=%s",
            payload.event.value, payload.device_id, exc,
        )
        return False
    except Exception as exc:
        logger.error(
            "Unexpected event delivery error event=%s device_id=%s type=%s",
            payload.event.value, payload.device_id, type(exc).__name__,
        )
        return False

    logger.info("Event delivered event=%s device_id=%s", payload.event.value, payload.device_id)
    return True


def dispatch_event(
    event: EventType, device: Device, status: str, details: dict[str, Any] | None = None
) -> bool:
    """Build a standard payload from `device` and deliver it. Never raises."""
    payload = build_event_payload(event, device, status, details)
    return deliver_event(payload)
