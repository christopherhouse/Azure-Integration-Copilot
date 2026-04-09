"""Feature flags domain models."""

from pydantic import BaseModel


class FeatureFlagsResponse(BaseModel):
    """Feature flags returned to the UI.

    Each key is a flag name (the ``feature.`` prefix is stripped from the
    App Configuration key).  Values are booleans — only keys whose value
    is the string ``"true"`` (case-insensitive) are treated as enabled.
    """

    flags: dict[str, bool]
