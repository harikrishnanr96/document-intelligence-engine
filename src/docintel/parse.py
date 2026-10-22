"""PDF -> clean text: the first stage of the pipeline.

Three steps:
  1. Read each page's text layer with pypdf.
  2. Refuse PDFs without a usable text layer (scans): OCR is out of scope, and
     extracting from near-empty text would silently return "nothing found".
  3. Remove headers/footers that repeat across pages, e.g. the SEC filing footer
     "Source: 2THEMART COM INC, 10-12G, 8/26/1999", which otherwise lands in the
     middle of any sentence that crosses a page break.
"""

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

logging.getLogger("pypdf").setLevel(logging.ERROR)  # malformed-PDF warnings aren't actionable here

MIN_CHARS_PER_PAGE = 100  # below this on average, treat the PDF as a scan
EDGE_LINES = 3  # headers/footers live in the first/last few lines of a page
REPEAT_SHARE = 0.5  # a line on at least half the pages is a header/footer
# "3", "- 3 -", "Page 3", "Page 3 of 9", "3/9"
_PAGE_NUMBER = re.compile(r"^\W*(page\s*)?\d+(\s*(of|/)\s*\d+)?\W*$", re.I)


class NoTextLayerError(ValueError):
    """The PDF has (almost) no extractable text, so it is probably scanned."""


@dataclass
class ParsedDocument:
    text: str
    pages: int
    removed_lines: list[str] = field(default_factory=list)  # distinct header/footer lines removed


def _key(line: str) -> str:
    # Page numbers differ on every page but are the same footer. Any other line must
    # repeat exactly, so headings like "ARTICLE 3" at the top of pages are kept.
    line = line.strip()
    return "<page number>" if _PAGE_NUMBER.match(line) else line.lower()


def strip_repeated_lines(pages: list[str]) -> tuple[list[str], list[str]]:
    """Remove lines that appear at the top or bottom of most pages."""
    if len(pages) < 3:
        return pages, []
    page_lines = [p.splitlines() for p in pages]

    def edges(lines: list[str]) -> list[str]:
        content = [ln for ln in lines if ln.strip()]
        return content[:EDGE_LINES] + content[-EDGE_LINES:]

    counts = Counter(k for lines in page_lines for k in {_key(ln) for ln in edges(lines)})
    threshold = max(3, REPEAT_SHARE * len(pages))
    repeated = {k for k, n in counts.items() if n >= threshold and k}

    cleaned, removed = [], {}
    for lines in page_lines:
        edge = set(edges(lines))
        kept = []
        for ln in lines:
            if ln in edge and _key(ln) in repeated:
                removed.setdefault(_key(ln), ln.strip())
            else:
                kept.append(ln)
        cleaned.append("\n".join(kept))
    return cleaned, list(removed.values())


def parse_pdf(path: str | Path) -> ParsedDocument:
    pages = [page.extract_text() or "" for page in PdfReader(path).pages]
    if not pages or sum(len(p.strip()) for p in pages) / len(pages) < MIN_CHARS_PER_PAGE:
        raise NoTextLayerError(
            f"{Path(path).name}: no usable text layer; this looks like a scanned document (OCR is out of scope)")
    pages, removed = strip_repeated_lines(pages)
    return ParsedDocument(text="\n".join(pages), pages=len(pages), removed_lines=removed)
