"""Feature flags API route.

Exposes Azure App Configuration feature flags as a simple boolean flag map.
Feature flags in App Configuration use the key prefix
``.appconfig.featureflag/`` and store a JSON value with an ``enabled``
boolean.  This endpoint parses that format and returns a flat
``{flag_name: bool}`` map so the frontend can query flags without direct
access to App Configuration (which is private).
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


def _request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID", str(uuid.uuid4()))


@router.get("")
async def get_feature_flags(request: Request):
    """Return all feature flags from App Configuration.

    Feature flags in Azure App Configuration use the key prefix
    ``.appconfig.featureflag/`` and their values are JSON objects containing
    an ``enabled`` boolean field.  The prefix is stripped so callers receive
    plain flag names (e.g. ``displayProductLandingPage``).

    When App Configuration is not configured (local dev without
    ``APP_CONFIG_ENDPOINT`` set) an empty flags map is returned so the UI
    degrades gracefully.
    """
    req_id = _request_id(request)

    await app_config_service.ensure_loaded()

    flags = app_config_service.get_feature_flags()

    logger.debug("feature_flags_fetched", flag_count=len(flags))

    envelope = ResponseEnvelope(
        data=FeatureFlagsResponse(flags=flags),
        meta=Meta(request_id=req_id, timestamp=datetime.now(UTC)),
    )
    return envelope.model_dump(mode="json")
