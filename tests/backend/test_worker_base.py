"""Tests for the BaseWorker pull loop, idempotency, and error handling."""

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_test_env = {
    "COSMOS_DB_ENDPOINT": "https://fake-cosmos.documents.azure.com:443/",
    "BLOB_STORAGE_ENDPOINT": "https://fake-blob.blob.core.windows.net/",
    "EVENT_GRID_NAMESPACE_ENDPOINT": "https://fake-eg.westus-1.eventgrid.azure.net",
    "SKIP_AUTH": "true",
}

with patch.dict(os.environ, _test_env):
    from workers.base import BaseWorker, PermanentError, TransientError, WorkerHandler


def _make_detail(event_data: dict, event_type: str = "test.event", lock_token: str = "lock-1"):
    """Create a mock ReceiveDetails-like object."""
    event = MagicMock()
    event.id = "evt_test123"
    event.type = event_type
    event.data = event_data
    broker_props = SimpleNamespace(lock_token=lock_token)
    return SimpleNamespace(event=event, broker_properties=broker_props)


class StubHandler(WorkerHandler):
    """Stub handler for testing."""

    def __init__(self):
        self.handled = []
        self.failures = []
        self._already_processed = False
        self._handle_side_effect = None

    async def is_already_processed(self, event_data):
        return self._already_processed

    async def handle(self, event_data):
        if self._handle_side_effect:
            raise self._handle_side_effect
        self.handled.append(event_data)

    async def handle_failure(self, event_data, error):
        self.failures.append((event_data, error))


class TestBaseWorker:
    """Tests for the BaseWorker pull loop."""

    @pytest.mark.asyncio
    async def test_processes_event_and_acknowledges(self):
        consumer = AsyncMock()
        handler = StubHandler()
        detail = _make_detail({"tenantId": "t1", "artifactId": "a1"})

        # Return events once, then stop
        consumer.receive_events = AsyncMock(side_effect=[[detail], []])

        worker = BaseWorker(consumer, handler, poll_interval=0.01)

        # Run briefly then stop
        call_count = 0
        original_receive = consumer.receive_events

        async def receive_then_stop(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [detail]
            worker.stop()
            return []

        consumer.receive_events = receive_then_stop
        await worker.run()

        consumer.acknowledge.assert_awaited_with(["lock-1"])
        assert len(handler.handled) == 1
        assert handler.handled[0] == {"tenantId": "t1", "artifactId": "a1"}

    @pytest.mark.asyncio
    async def test_skips_event_without_tenant_id(self):
        consumer = AsyncMock()
        handler = StubHandler()
        detail = _make_detail({})  # No tenantId

        call_count = 0

        async def receive_then_stop(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [detail]
            worker.stop()
            return []

        consumer.receive_events = receive_then_stop
        worker = BaseWorker(consumer, handler, poll_interval=0.01)
        await worker.run()

        # Should acknowledge (discard) the event
        consumer.acknowledge.assert_awaited_with(["lock-1"])
        assert len(handler.handled) == 0

    @pytest.mark.asyncio
    async def test_skips_already_processed_event(self):
        consumer = AsyncMock()
        handler = StubHandler()
        handler._already_processed = True
        detail = _make_detail({"tenantId": "t1", "artifactId": "a1"})

        call_count = 0

        async def receive_then_stop(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [detail]
            worker.stop()
            return []

        consumer.receive_events = receive_then_stop
        worker = BaseWorker(consumer, handler, poll_interval=0.01)
        await worker.run()

        consumer.acknowledge.assert_awaited_with(["lock-1"])
        assert len(handler.handled) == 0

    @pytest.mark.asyncio
    async def test_releases_on_transient_error(self):
        consumer = AsyncMock()
        handler = StubHandler()
        handler._handle_side_effect = TransientError("temporary failure")
        detail = _make_detail({"tenantId": "t1", "artifactId": "a1"})

        call_count = 0

        async def receive_then_stop(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [detail]
            worker.stop()
            return []

        consumer.receive_events = receive_then_stop
        worker = BaseWorker(consumer, handler, poll_interval=0.01)
        await worker.run()

        consumer.release.assert_awaited_with(["lock-1"])
        consumer.acknowledge.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_acknowledges_on_permanent_error(self):
        consumer = AsyncMock()
        handler = StubHandler()
        handler._handle_side_effect = PermanentError("bad data")
        detail = _make_detail({"tenantId": "t1", "artifactId": "a1"})

        call_count = 0

        async def receive_then_stop(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [detail]
            worker.stop()
            return []

        consumer.receive_events = receive_then_stop
        worker = BaseWorker(consumer, handler, poll_interval=0.01)
        await worker.run()

        consumer.acknowledge.assert_awaited_with(["lock-1"])
        assert len(handler.failures) == 1
        assert isinstance(handler.failures[0][1], PermanentError)

    @pytest.mark.asyncio
    async def test_releases_on_unexpected_error(self):
        consumer = AsyncMock()
        handler = StubHandler()
        handler._handle_side_effect = RuntimeError("unexpected")
        detail = _make_detail({"tenantId": "t1", "artifactId": "a1"})

        call_count = 0

        async def receive_then_stop(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [detail]
            worker.stop()
            return []

        consumer.receive_events = receive_then_stop
        worker = BaseWorker(consumer, handler, poll_interval=0.01)
        await worker.run()

        consumer.release.assert_awaited_with(["lock-1"])

    @pytest.mark.asyncio
    async def test_releases_on_idempotency_check_failure(self):
        consumer = AsyncMock()
        handler = StubHandler()

        async def bad_check(event_data):
            raise RuntimeError("db down")

        handler.is_already_processed = bad_check
        detail = _make_detail({"tenantId": "t1", "artifactId": "a1"})

        call_count = 0

        async def receive_then_stop(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [detail]
            worker.stop()
            return []

        consumer.receive_events = receive_then_stop
        worker = BaseWorker(consumer, handler, poll_interval=0.01)
        await worker.run()

        consumer.release.assert_awaited_with(["lock-1"])

    @pytest.mark.asyncio
    async def test_stop_terminates_loop(self):
        consumer = AsyncMock()
        handler = StubHandler()
        consumer.receive_events = AsyncMock(return_value=[])

        worker = BaseWorker(consumer, handler, poll_interval=0.01)
        worker.stop()
        await worker.run()

        consumer.close.assert_awaited_once()
