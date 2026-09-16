import time
from urllib.parse import urlsplit

import httpx

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class WebhookDeliveryError(Exception):
    """Raised when a webhook could not be delivered after all retries."""


class WebhookNotConfiguredError(WebhookDeliveryError):
    """Raised when N8N_WEBHOOK_URL is not set -- delivery is a no-op by design."""


def _mask_url(url: str) -> str:
    """Log-safe form of a webhook URL: scheme+host only.

    n8n webhook paths embed an effectively-secret, unguessable id -- treat
    the full URL like a credential and never write it to logs.
    """
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}/***"


def _safe_response_snippet(response: httpx.Response) -> str:
    """Best-effort short description of a response body for error messages.

    Never lets a malformed/unreadable response body raise past this point.
    """
    try:
        return response.text[:200]
    except Exception:
        return "<unreadable response body>"


def send_webhook(payload: dict) -> None:
    """POST `payload` as JSON to the configured n8n webhook URL.

    Retries on timeout/connection errors and 5xx responses (fixed backoff
    scaled by attempt number), up to `settings.n8n_webhook_max_retries`
    attempts. A 4xx response is not retried (the payload or URL is wrong,
    retrying won't help). Raises WebhookNotConfiguredError if no URL is set,
    or WebhookDeliveryError on final failure -- callers are expected to
    catch both and never let them propagate, so a misbehaving or
    unreachable n8n instance can never affect NetAutoOps itself.
    """
    if not settings.n8n_webhook_url:
        raise WebhookNotConfiguredError("N8N_WEBHOOK_URL is not configured")

    url = settings.n8n_webhook_url
    masked_url = _mask_url(url)
    max_attempts = settings.n8n_webhook_max_retries
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            response = httpx.post(url, json=payload, timeout=settings.n8n_webhook_timeout)
        except httpx.TimeoutException as exc:
            last_error = exc
            logger.warning("Webhook timeout url=%s attempt=%s/%s", masked_url, attempt, max_attempts)
        except httpx.RequestError as exc:
            last_error = exc
            logger.warning(
                "Webhook connection error url=%s attempt=%s/%s type=%s",
                masked_url, attempt, max_attempts, type(exc).__name__,
            )
        else:
            if response.status_code < 300:
                logger.info(
                    "Webhook delivered url=%s status_code=%s attempt=%s",
                    masked_url, response.status_code, attempt,
                )
                return
            if response.status_code < 500:
                raise WebhookDeliveryError(
                    f"Webhook rejected with HTTP {response.status_code} (not retrying): "
                    f"{_safe_response_snippet(response)}"
                )
            last_error = WebhookDeliveryError(f"Webhook server error HTTP {response.status_code}")
            logger.warning(
                "Webhook server error url=%s attempt=%s/%s status_code=%s",
                masked_url, attempt, max_attempts, response.status_code,
            )

        if attempt < max_attempts:
            time.sleep(settings.n8n_webhook_retry_backoff_seconds * attempt)

    raise WebhookDeliveryError(
        f"Webhook delivery failed after {max_attempts} attempts"
    ) from last_error
