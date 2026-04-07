"""Async ClamAV scanner client speaking the clamd TCP protocol.

Connects to a clamd sidecar container and scans data using the INSTREAM
command.  No external dependencies required — uses only the stdlib
:mod:`asyncio` for TCP communication.
"""

from __future__ import annotations

import asyncio
import struct
from dataclasses import dataclass

import structlog

from config import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Maximum chunk size sent to clamd in INSTREAM mode (clamd default limit is 25 MiB).
_CHUNK_SIZE = 8192

# Timeout for individual TCP operations.
_TCP_TIMEOUT = 30.0


@dataclass(frozen=True)
class ClamScanResult:
    """Structured result from a ClamAV scan."""

    is_clean: bool
    signature: str | None
    raw_response: str


class ClamAVScanner:
    """Async client for the ClamAV daemon (clamd) TCP protocol.

    Parameters
    ----------
    host:
        Hostname or IP address of the clamd daemon.
    port:
        TCP port of the clamd daemon (default 3310).
    """

    def __init__(self, host: str | None = None, port: int | None = None) -> None:
        self._host = host or settings.clamd_host
        self._port = port or settings.clamd_port

    async def _send_command(self, command: bytes) -> bytes:
        """Open a TCP connection, send *command*, and return the full response.

        Commands use the clamd ``z`` (null-terminated) protocol format.
        """
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self._host, self._port),
            timeout=_TCP_TIMEOUT,
        )
        try:
            writer.write(command)
            await writer.drain()
            response = await asyncio.wait_for(reader.read(4096), timeout=_TCP_TIMEOUT)
            return response
        finally:
            writer.close()
            await writer.wait_closed()

    async def ping(self) -> bool:
        """Send a ``PING`` command and expect ``PONG`` back.

        Uses the clamd ``z`` (null-terminated) command format:
        ``zPING\\0`` → ``PONG\\0``.

        Returns ``True`` if clamd is reachable and healthy.
        """
        try:
            logger.debug("clamd_ping_request", host=self._host, port=self._port)
            response = await self._send_command(b"zPING\0")
            decoded = response.strip(b"\0").strip()
            is_pong = decoded == b"PONG"
            logger.debug(
                "clamd_ping_response",
                raw_response=decoded.decode("utf-8", errors="replace"),
                healthy=is_pong,
            )
            return is_pong
        except Exception:
            logger.warning("clamd_ping_failed", host=self._host, port=self._port, exc_info=True)
            return False

    async def scan(self, data: bytes) -> ClamScanResult:
        """Scan *data* using the clamd ``INSTREAM`` command.

        Streams the payload in length-prefixed chunks, then reads the
        scan verdict.

        Returns
        -------
        ClamScanResult
            ``is_clean=True`` when the response ends with ``OK``.
            ``is_clean=False`` when the response contains ``FOUND``;
            the malware signature is extracted.
        """
        data_size = len(data)
        chunk_count = (data_size + _CHUNK_SIZE - 1) // _CHUNK_SIZE
        logger.info(
            "clamd_scan_request",
            host=self._host,
            port=self._port,
            data_size_bytes=data_size,
            chunk_size=_CHUNK_SIZE,
            chunk_count=chunk_count,
        )

        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self._host, self._port),
            timeout=_TCP_TIMEOUT,
        )
        try:
            # Send INSTREAM command using clamd null-terminated (z) format
            writer.write(b"zINSTREAM\0")
            await writer.drain()
            logger.debug("clamd_instream_command_sent")

            # Stream data in length-prefixed chunks
            offset = 0
            chunks_sent = 0
            while offset < len(data):
                chunk = data[offset : offset + _CHUNK_SIZE]
                # Each chunk is preceded by a 4-byte big-endian length
                writer.write(struct.pack(">I", len(chunk)))
                writer.write(chunk)
                offset += _CHUNK_SIZE
                chunks_sent += 1
            await writer.drain()
            logger.debug("clamd_chunks_streamed", chunks_sent=chunks_sent, total_bytes=data_size)

            # Send zero-length terminator to signal end of stream
            writer.write(struct.pack(">I", 0))
            await writer.drain()
            logger.debug("clamd_stream_terminated")

            # Read the scan result
            response_bytes = await asyncio.wait_for(reader.read(4096), timeout=_TCP_TIMEOUT)
            raw_response = response_bytes.strip(b"\0").decode("utf-8", errors="replace").strip()

            result = _parse_scan_response(raw_response)
            logger.info(
                "clamd_scan_response",
                raw_response=result.raw_response,
                is_clean=result.is_clean,
                signature=result.signature,
                data_size_bytes=data_size,
            )
            return result
        finally:
            writer.close()
            await writer.wait_closed()


def _parse_scan_response(raw: str) -> ClamScanResult:
    """Parse a clamd INSTREAM response line.

    Expected formats::

        stream: OK
        stream: Eicar-Signature FOUND
    """
    if raw.endswith("OK"):
        return ClamScanResult(is_clean=True, signature=None, raw_response=raw)

    if "FOUND" in raw:
        # Extract signature: "stream: <signature> FOUND"
        parts = raw.split(":", 1)
        detail = parts[1].strip() if len(parts) > 1 else raw
        signature = detail.rsplit(" FOUND", 1)[0].strip()
        return ClamScanResult(is_clean=False, signature=signature, raw_response=raw)

    # Unexpected response — treat as error (not clean, no signature)
    logger.warning("clamd_unexpected_response", raw=raw)
    return ClamScanResult(is_clean=False, signature=None, raw_response=raw)


clamav_scanner = ClamAVScanner()
