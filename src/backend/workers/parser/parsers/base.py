"""Abstract base class for artifact parsers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from workers.parser.models import ParseResult


class BaseParser(ABC):
    """Interface that each artifact-type parser must implement."""

    @abstractmethod
    def parse(self, content: bytes, filename: str) -> ParseResult:
        """Parse raw artifact content and return structured components and edges.

        Parameters
        ----------
        content:
            Raw file bytes downloaded from Blob Storage.
        filename:
            Original filename (used for display names and format detection).

        Returns
        -------
        ParseResult
            Components, edges, and external references extracted from the artifact.
        """
