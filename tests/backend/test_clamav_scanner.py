"""Tests for the ClamAV async scanner client."""

import asyncio
import os
import struct
from unittest.mock import AsyncMock, patch

import pytest

_test_env = {
    "COSMOS_DB_ENDPOINT": "https://fake-cosmos.documents.azure.com:443/",
    "BLOB_STORAGE_ENDPOINT": "https://fake-blob.blob.core.windows.net/",
    "EVENT_GRID_NAMESPACE_ENDPOINT": "https://fake-eg.westus-1.eventgrid.azure.net",
    "SKIP_AUTH": "true",
}

with patch.dict(os.environ, _test_env):
    from shared.clamav import ClamAVScanner, ClamScanResult, _parse_scan_response


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


class TestParseScanResponse:
    """Tests for _parse_scan_response."""

    def test_clean_response(self):
        result = _parse_scan_response("stream: OK")
        assert result.is_clean is True
        assert result.signature is None
        assert result.raw_response == "stream: OK"

    def test_malware_found_response(self):
        result = _parse_scan_response("stream: Eicar-Signature FOUND")
        assert result.is_clean is False
        assert result.signature == "Eicar-Signature"
        assert "FOUND" in result.raw_response

    def test_malware_with_complex_signature(self):
        result = _parse_scan_response("stream: Win.Trojan.Agent-123456 FOUND")
        assert result.is_clean is False
        assert result.signature == "Win.Trojan.Agent-123456"

    def test_unexpected_response_treated_as_not_clean(self):
        result = _parse_scan_response("stream: ERROR something went wrong")
        assert result.is_clean is False
        assert result.signature is None


# ---------------------------------------------------------------------------
# Scanner ping
# ---------------------------------------------------------------------------


class TestClamAVScannerPing:
    """Tests for the ClamAV scanner ping method."""

    @pytest.mark.asyncio
    async def test_ping_returns_true_when_pong(self):
        scanner = ClamAVScanner(host="127.0.0.1", port=3310)

        mock_reader = AsyncMock()
        mock_reader.read = AsyncMock(return_value=b"PONG\0")
        mock_writer = AsyncMock()
        mock_writer.wait_closed = AsyncMock()

        with patch("shared.clamav.asyncio.open_connection", return_value=(mock_reader, mock_writer)):
            result = await scanner.ping()

        assert result is True

    @pytest.mark.asyncio
    async def test_ping_returns_false_on_connection_error(self):
        scanner = ClamAVScanner(host="127.0.0.1", port=3310)

        with patch("shared.clamav.asyncio.open_connection", side_effect=ConnectionRefusedError):
            result = await scanner.ping()

        assert result is False

    @pytest.mark.asyncio
    async def test_ping_returns_false_on_unexpected_response(self):
        scanner = ClamAVScanner(host="127.0.0.1", port=3310)

        mock_reader = AsyncMock()
        mock_reader.read = AsyncMock(return_value=b"SOMETHING_ELSE\0")
        mock_writer = AsyncMock()
        mock_writer.wait_closed = AsyncMock()

        with patch("shared.clamav.asyncio.open_connection", return_value=(mock_reader, mock_writer)):
            result = await scanner.ping()

        assert result is False


# ---------------------------------------------------------------------------
# Scanner scan
# ---------------------------------------------------------------------------


class TestClamAVScannerScan:
    """Tests for the ClamAV scanner scan method."""

    @pytest.mark.asyncio
    async def test_scan_clean_file(self):
        scanner = ClamAVScanner(host="127.0.0.1", port=3310)

        mock_reader = AsyncMock()
        mock_reader.read = AsyncMock(return_value=b"stream: OK\0")
        mock_writer = AsyncMock()
        mock_writer.wait_closed = AsyncMock()

        with patch("shared.clamav.asyncio.open_connection", return_value=(mock_reader, mock_writer)):
            result = await scanner.scan(b"clean file content")

        assert result.is_clean is True
        assert result.signature is None

    @pytest.mark.asyncio
    async def test_scan_infected_file(self):
        scanner = ClamAVScanner(host="127.0.0.1", port=3310)

        mock_reader = AsyncMock()
        mock_reader.read = AsyncMock(return_value=b"stream: Eicar-Test-Signature FOUND\0")
        mock_writer = AsyncMock()
        mock_writer.wait_closed = AsyncMock()

        with patch("shared.clamav.asyncio.open_connection", return_value=(mock_reader, mock_writer)):
            result = await scanner.scan(b"EICAR test data")

        assert result.is_clean is False
        assert result.signature == "Eicar-Test-Signature"

    @pytest.mark.asyncio
    async def test_scan_sends_instream_protocol(self):
        """Verify the INSTREAM protocol framing is correct."""
        scanner = ClamAVScanner(host="127.0.0.1", port=3310)

        mock_reader = AsyncMock()
        mock_reader.read = AsyncMock(return_value=b"stream: OK\0")
        mock_writer = AsyncMock()
        mock_writer.wait_closed = AsyncMock()

        test_data = b"test data"

        with patch("shared.clamav.asyncio.open_connection", return_value=(mock_reader, mock_writer)):
            await scanner.scan(test_data)

        # Verify the writer received the correct protocol bytes
        write_calls = mock_writer.write.call_args_list
        # First call: INSTREAM command
        assert write_calls[0].args[0] == b"zINSTREAM\0"
        # Second call: chunk length prefix
        assert write_calls[1].args[0] == struct.pack(">I", len(test_data))
        # Third call: chunk data
        assert write_calls[2].args[0] == test_data
        # Fourth call: zero-length terminator
        assert write_calls[3].args[0] == struct.pack(">I", 0)

    @pytest.mark.asyncio
    async def test_scan_raises_on_connection_error(self):
        scanner = ClamAVScanner(host="127.0.0.1", port=3310)

        with patch("shared.clamav.asyncio.open_connection", side_effect=ConnectionRefusedError("no clamd")):
            with pytest.raises(ConnectionRefusedError):
                await scanner.scan(b"data")

    @pytest.mark.asyncio
    async def test_scan_raises_on_timeout(self):
        scanner = ClamAVScanner(host="127.0.0.1", port=3310)

        with patch("shared.clamav.asyncio.open_connection", side_effect=asyncio.TimeoutError):
            with pytest.raises(asyncio.TimeoutError):
                await scanner.scan(b"data")
