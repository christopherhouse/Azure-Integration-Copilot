"""Feature flags domain models."""

from pydantic import BaseModel


class FeatureFlagsResponse(BaseModel):
    """Feature flags returned to the UI.

    Each key is a flag name (the ``.appconfig.featureflag/`` prefix is
    stripped from the App Configuration key).  Values are booleans derived
    from the ``enabled`` field in the feature flag's JSON value.
    """

    flags: dict[str, bool]
