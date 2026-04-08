"""Prompt loader — reads LLM prompt text files once at import time.

All prompt files live in the ``prompts/`` directory next to this module.
Each public constant is the stripped text content of the corresponding file.
Templates that require runtime formatting use :func:`str.format` placeholders.
"""

from __future__ import annotations

from pathlib import Path

_PROMPT_DIR = Path(__file__).resolve().parent

def _load(filename: str) -> str:
    """Read and strip a prompt file from the prompts directory."""
    return (_PROMPT_DIR / filename).read_text(encoding="utf-8").strip()


# ── Static system prompts ──────────────────────────────────────────────
ANALYST_SYSTEM_PROMPT: str = _load("analyst_system.txt")
EVALUATOR_SYSTEM_PROMPT: str = _load("evaluator_system.txt")

# ── Templates (use .format(**kwargs) at call sites) ───────────────────
EVALUATOR_USER_TEMPLATE: str = _load("evaluator_user.txt")
ANALYST_REVISION_TEMPLATE: str = _load("analyst_revision.txt")
