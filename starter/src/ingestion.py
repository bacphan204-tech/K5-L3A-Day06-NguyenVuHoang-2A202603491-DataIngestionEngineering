"""Load page-level provenance and conservatively remove PDF page furniture."""
import json
import re
import unicodedata
from pathlib import Path
from .models import DocumentPage


def normalize_text(text: str) -> str:
    lines = []
    for line in unicodedata.normalize("NFC", text).splitlines():
        line = " ".join(line.split())
        if line == "Access for free at openstax.org":
            continue
        if re.match(r"^\d+\s+[34]\s+•\s", line):
            continue
        if re.match(r"^[34]\.\d\s+•.*\s\d+$", line):
            continue
        if re.match(r"^[34]\s+•\s+Key.*\s\d+$", line):
            continue
        lines.append(line)
    return re.sub(r"\s+", " ", "\n".join(lines)).strip()


def load_corpus(root: Path) -> list[DocumentPage]:
    records = [json.loads(line) for line in (root / "data/processed/pages.jsonl").read_text(encoding="utf-8").splitlines()]
    if len(records) < 30:
        raise ValueError("Fewer than 30 selected pages")
    pages = []
    for r in records:
        text = normalize_text(r["text"])
        if not text:
            raise ValueError(f"Empty selected page: {r['page']}")
        pages.append(DocumentPage(r["document_id"], r["source"], r["page"], text,
            {k: r[k] for k in ("chapter", "chapter_title", "printed_page", "original_pdf_page")}))
    return pages


def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    from pypdf import PdfReader
    pages = []
    for n, page in enumerate(PdfReader(path).pages, 1):
        text = normalize_text(page.extract_text() or "")
        if not text:
            raise ValueError(f"No extracted text on page {n}; inspect/OCR explicitly")
        pages.append(DocumentPage(document_id, source, n, text))
    return pages
