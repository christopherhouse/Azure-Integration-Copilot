"""Feature flags API route.

Exposes App Configuration key-values whose keys start with the ``feature.``
prefix as a simple boolean flag map.  This lets the frontend query flags
without direct access to App Configuration (which is private).
"""

import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Request

from shared.app_config import app_config_service
from shared.models import Meta, ResponseEnvelope

from .models import FeatureFlagsResponse

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/feature-flags", tags=["feature-flags"])

_FEATURE_PREFIX = "feature."


def _request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID", str(uuid.uuid4()))


@router.get("")
async def get_feature_flags(request: Request):
    """Return all feature flags from App Configuration.

    Keys in App Configuration that begin with ``feature.`` are surfaced as
    feature flags.  The prefix is stripped so callers receive plain flag
    names (e.g. ``new-dashboard``, not ``feature.new-dashboard``).

    A flag is **enabled** when its value is the string ``"true"``
    (case-insensitive).  All other values — or a missing key — are treated
    as disabled.

    When App Configuration is not configured (local dev without
    ``APP_CONFIG_ENDPOINT`` set) an empty flags map is returned so the UI
    degrades gracefully.
    """
    req_id = _request_id(request)

    await app_config_service.ensure_loaded()

    flags: dict[str, bool] = {}
    for key, value in app_config_service._cache.items():
        if key.startswith(_FEATURE_PREFIX):
            flag_name = key[len(_FEATURE_PREFIX):]
            flags[flag_name] = value.strip().lower() == "true"

    logger.debug("feature_flags_fetched", flag_count=len(flags))

    envelope = ResponseEnvelope(
        data=FeatureFlagsResponse(flags=flags),
        meta=Meta(request_id=req_id, timestamp=datetime.now(UTC)),
    )
    return envelope.model_dump(mode="json")
