"""Text normalization shared by grounding checks and span matching."""

import re

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize(s: str) -> str:
    """Lowercase, and collapse punctuation/whitespace runs to single spaces.

    PDF and TXT extraction differ in line breaks, spacing and quote characters;
    comparing normalized text keeps those differences from counting as errors.
    """
    return _NON_ALNUM.sub(" ", s.lower()).strip()


def tokens(s: str) -> set[str]:
    return set(normalize(s).split())


def jaccard(a: str, b: str) -> float:
    """Word-set overlap: |A ∩ B| / |A ∪ B|. The metric CUAD's own evaluation uses."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def containment(a: str, b: str) -> float:
    """|A ∩ B| / min(|A|, |B|): high when one passage sits inside the other."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))
