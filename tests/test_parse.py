import pytest
from pypdf import PdfWriter

from docintel.parse import NoTextLayerError, parse_pdf, strip_repeated_lines

FOOTER = "Source: 2THEMART COM INC, 10-12G, 8/26/1999"


def page(body: str, n: int) -> str:
    return f"ACME CONFIDENTIAL\n{body}\nmore text on page {n}\nPage {n} of 4\n{FOOTER}"


def test_repeated_headers_and_footers_are_removed():
    pages = [page(f"Clause {n} text.", n) for n in range(1, 5)]
    cleaned, removed = strip_repeated_lines(pages)
    assert all(FOOTER not in p and "ACME CONFIDENTIAL" not in p for p in cleaned)
    assert all("Page" not in p.split("\n")[-1] for p in cleaned)  # "Page n of 4" differs only in digits
    assert "Clause 3 text." in cleaned[2]
    assert FOOTER in removed


def test_lines_repeated_only_mid_page_are_kept():
    body = [f"line {i} of the body" for i in range(10)]
    body[5] = "The Supplier shall deliver."
    pages = ["\n".join([f"top {n}"] + body + [f"bottom {n}"]) for n in range(4)]
    cleaned, _ = strip_repeated_lines(pages)
    assert all("The Supplier shall deliver." in p for p in cleaned)


def test_numbered_headings_at_page_tops_are_kept():
    pages = ["\n".join([f"ARTICLE {n}"] + [f"article {n} sentence {i}" for i in range(6)]) for n in range(1, 5)]
    cleaned, removed = strip_repeated_lines(pages)
    assert removed == [] and "ARTICLE 3" in cleaned[2]


def test_short_documents_are_left_alone():
    pages = [page("a", 1), page("b", 2)]
    assert strip_repeated_lines(pages) == (pages, [])


def test_pdf_without_text_layer_is_refused(tmp_path):
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)  # an image-only scan looks like this to pypdf
    path = tmp_path / "scan.pdf"
    with open(path, "wb") as f:
        writer.write(f)
    with pytest.raises(NoTextLayerError, match="scanned"):
        parse_pdf(path)
