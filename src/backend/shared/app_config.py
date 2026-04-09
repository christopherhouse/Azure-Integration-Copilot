"""Azure App Configuration service — managed-identity, event-driven refresh.

Configuration values are fetched lazily on first access and cached in memory.
Refresh is intentionally **not** polled; instead, callers must wire up an
Event Grid subscription for ``Microsoft.AppConfiguration.KeyValueModified``
and ``Microsoft.AppConfiguration.KeyValueDeleted`` events, then call
:meth:`AppConfigService.on_config_changed` when one arrives.

This avoids unnecessary API calls when settings are stable, while still
keeping the cache fresh after deliberate changes.  A minimum re-fetch
interval (:data:`_MIN_REFRESH_INTERVAL`) acts as a thundering-herd guard so
that a rapid burst of change events does not flood the service with requests.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog
from azure.appconfiguration.aio import AzureAppConfigurationClient

from config import settings
from shared.credential import create_credential

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Minimum seconds to wait between full cache re-loads, even when change
# notifications arrive in quick succession.
_MIN_REFRESH_INTERVAL: float = 30.0


class AppConfigService:
    """Async wrapper around Azure App Configuration.

    Uses a user-assigned managed identity (no connection strings).  When
    ``APP_CONFIG_ENDPOINT`` is not set the service operates in a no-op mode
    suitable for local development.
    """

    def __init__(self) -> None:
        self._client: AzureAppConfigurationClient | None = None
        self._credential: Any = None
        self._cache: dict[str, str] = {}
        self._loaded: bool = False
        self._last_refresh: float = 0.0
        self._lock: asyncio.Lock = asyncio.Lock()

    def _is_configured(self) -> bool:
        return bool(settings.app_config_endpoint)

    async def _get_client(self) -> AzureAppConfigurationClient:
        if self._client is None:
            self._credential = create_credential()
            self._client = AzureAppConfigurationClient(
                base_url=settings.app_config_endpoint,
                credential=self._credential,
            )
        return self._client

    async def _load(self) -> None:
        """Fetch all key-values from App Configuration and refresh the cache."""
        client = await self._get_client()
        new_cache: dict[str, str] = {}
        async for kv in client.list_configuration_settings():
            if kv.key is not None and kv.value is not None:
                new_cache[kv.key] = str(kv.value)
        self._cache = new_cache
        self._loaded = True
        self._last_refresh = time.monotonic()
        logger.info("app_config_loaded", key_count=len(self._cache))

    async def ensure_loaded(self) -> None:
        """Populate the cache on the first call (no-op afterwards).

        Safe to call concurrently — only one coroutine will perform the actual
        network request; others wait and then proceed with the populated cache.
        """
        if self._loaded or not self._is_configured():
            return
        async with self._lock:
            if not self._loaded:
                try:
                    await self._load()
                except Exception:
                    logger.warning("app_config_load_failed", exc_info=True)

    def get(self, key: str, default: Any = None) -> Any:
        """Return the cached value for *key*, or *default* if not present."""
        return self._cache.get(key, default)

    def get_by_prefix(self, prefix: str) -> dict[str, str]:
        """Return all cached key-value pairs whose keys start with *prefix*.

        The returned dictionary contains the original, unmodified keys (the
        prefix is **not** stripped).  Callers are responsible for any key
        transformation they need.
        """
        return {k: v for k, v in self._cache.items() if k.startswith(prefix)}

    async def on_config_changed(self) -> None:
        """Invalidate and refresh the cache.

        Designed to be called from an Event Grid event handler when a
        ``Microsoft.AppConfiguration.KeyValueModified`` or
        ``Microsoft.AppConfiguration.KeyValueDeleted`` event is received.

        A minimum interval of :data:`_MIN_REFRESH_INTERVAL` seconds is
        enforced so that a burst of change events does not cause excessive
        API calls.
        """
        if not self._is_configured():
            return

        elapsed = time.monotonic() - self._last_refresh
        if elapsed < _MIN_REFRESH_INTERVAL:
            logger.debug(
                "app_config_refresh_skipped",
                elapsed_seconds=round(elapsed, 1),
                min_interval=_MIN_REFRESH_INTERVAL,
            )
            return

        async with self._lock:
            # Another coroutine may have refreshed while we waited for the lock.
            elapsed = time.monotonic() - self._last_refresh
            if elapsed < _MIN_REFRESH_INTERVAL:
                return
            try:
                await self._load()
            except Exception:
                logger.warning("app_config_refresh_failed", exc_info=True)

    async def close(self) -> None:
        """Close the underlying SDK client and credential, releasing all resources."""
        if self._client is not None:
            await self._client.close()
            self._client = None
        if self._credential is not None:
            await self._credential.close()
            self._credential = None
        self._loaded = False


app_config_service = AppConfigService()
