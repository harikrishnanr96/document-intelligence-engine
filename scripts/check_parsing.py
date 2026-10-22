"""Check the PDF parse step on every CUAD contract (free: no API calls).

    python scripts/check_parsing.py

Reports: PDFs refused as scans, header/footer lines removed, and how many of the
lawyer-labelled passages (our 12 fields) are still findable in the parsed text,
before and after header/footer removal.
"""

import time
from collections import Counter

from pypdf import PdfReader

from docintel.cuad import DEFAULT_ROOT, load_cuad
from docintel.parse import NoTextLayerError, parse_pdf
from docintel.text import normalize


def main() -> None:
    pdfs = {p.stem.lower(): p for p in (DEFAULT_ROOT / "full_contract_pdf").rglob("*")
            if p.suffix.lower() == ".pdf"}
    contracts = load_cuad()
    refused, missing_pdf, footer_docs = [], [], 0
    found_raw = found_clean = total = 0
    removed_examples: Counter = Counter()
    start = time.perf_counter()

    for c in contracts:
        path = pdfs.get(c.id.lower())
        if path is None:
            missing_pdf.append(c.id)
            continue
        try:
            doc = parse_pdf(path)
        except NoTextLayerError:
            refused.append(c.id)
            continue
        raw = " " + normalize(" ".join(p.extract_text() or "" for p in PdfReader(path).pages)) + " "
        clean = " " + normalize(doc.text) + " "
        footer_docs += bool(doc.removed_lines)
        removed_examples.update(doc.removed_lines)
        for spans in c.labels.values():
            for s in spans:
                total += 1
                found_raw += f" {normalize(s)} " in raw
                found_clean += f" {normalize(s)} " in clean

    parsed = len(contracts) - len(refused) - len(missing_pdf)
    print(f"{len(contracts)} contracts, {time.perf_counter() - start:.0f}s")
    print(f"  PDF not matched to a label record: {len(missing_pdf)} {missing_pdf[:5]}")
    print(f"  refused as scanned (no text layer): {len(refused)} {refused[:5]}")
    print(f"  parsed: {parsed}; with headers/footers removed: {footer_docs}")
    print(f"  lawyer passages findable  before cleanup: {found_raw}/{total} = {100 * found_raw / total:.1f}%")
    print(f"                            after cleanup:  {found_clean}/{total} = {100 * found_clean / total:.1f}%")
    print("  most common removed lines:")
    for line, n in removed_examples.most_common(8):
        print(f"    {n:4}  {line[:90]}")


if __name__ == "__main__":
    main()
