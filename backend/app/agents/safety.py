"""Output safety: forbidden-language detector + filter.

Belt-and-braces. The system prompt forbids these words; the schema constrains
the rationale length; this filter is the third layer that scrubs any stray
leakage before output reaches the user.

Word-boundary matching matters: "long" must NOT match inside "long-term",
"longer", or "longest", and "short" must NOT match inside "short-term" or
"shortly". An earlier substring-match version was dropping legitimate
scenarios for these false positives.
"""

from __future__ import annotations

import re
from typing import Iterable

from app.core.logging import get_logger


log = get_logger("agents.safety")


# Each pattern is matched as a whole word (or short phrase) with case-insensitive,
# word-boundary semantics. Multi-word phrases like "target price" use literal
# whitespace; single words use \b boundaries to avoid false positives like
# "long-term" → "long" or "shortly" → "short".
# For "long" and "short" we exclude hyphenated compounds (long-term, short-term)
# AND derivative suffixes (longer, longest, shortly, shorter) by requiring no
# word-char OR hyphen on either side.
_FORBIDDEN_PATTERNS: tuple[str, ...] = (
    r"\bbuy\b",
    r"\bsell\b",
    r"(?<![\w-])long(?![\w-])",
    r"(?<![\w-])short(?![\w-])",
    r"\btarget\s+price\b",
    r"\bpredict(?:s|ed|ion|ions)?\b",
    r"\bforecast(?:s|ed|ing)?\b",
    r"\brecommend(?:s|ed|ation|ations)?\b",
    r"\bhigh\s+probability\b",
)
_FORBIDDEN_RE = re.compile("|".join(_FORBIDDEN_PATTERNS), flags=re.IGNORECASE)


def contains_forbidden(text: str) -> str | None:
    """Return the first forbidden word/phrase found (lower-cased), or None."""
    match = _FORBIDDEN_RE.search(text)
    return match.group(0).lower() if match is not None else None


def filter_rationales(items: Iterable, *, agent_name: str) -> list:
    """Drop items whose `rationale` attribute contains forbidden language."""
    safe: list = []
    for item in items:
        rationale = getattr(item, "rationale", "") or ""
        offending = contains_forbidden(rationale)
        if offending is None:
            safe.append(item)
        else:
            log.warning(
                "agents.dropped_forbidden_word",
                agent=agent_name,
                word=offending,
                rationale=rationale[:80],
            )
    return safe


# Re-exported tuple for tests / docs that want to enumerate the patterns.
FORBIDDEN_PATTERNS = _FORBIDDEN_PATTERNS
