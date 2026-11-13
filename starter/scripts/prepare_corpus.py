"""Extract the selected source pages; eligibility requires manual review."""
import csv
import hashlib
import json
import unicodedata
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
PDF_PATH = ROOT / "data/raw/economics-chapters-3-4.pdf"
OUTPUT_DIR = ROOT / "data/processed"
SELECTIONS = [
    (3, "Demand and Supply", 2, 34),
    (4, "Labor and Financial Markets", 35, 53),
]


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(" ".join(line.split()) for line in text.splitlines()).strip()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    reader = PdfReader(PDF_PATH)
    records, inventory, issues = [], [], []
    for chapter, title, start, end in SELECTIONS:
        for pdf_page in range(start, end + 1):
            original_page = pdf_page + (61 if chapter == 3 else 66)
            error = ""
            try:
                text = normalize_text(reader.pages[pdf_page - 1].extract_text() or "")
            except Exception as exc:
                text = ""
                error = f"{type(exc).__name__}: {exc}"
            if error:
                status = "extraction_error"
            elif not text:
                status = "no_extracted_text"
            elif len(text) < 300:
                status = "short_text_review"
            else:
                status = "needs_content_review"
            records.append({
                "document_id": "openstax-principles-economics-3e",
                "source": "data/raw/economics-chapters-3-4.pdf",
                "page": pdf_page, "printed_page": original_page - 16, "original_pdf_page": original_page,
                "chapter": chapter, "chapter_title": title,
                "text": text, "char_count": len(text), "status": status,
            })
            inventory.append({
                "pdf_page": pdf_page, "printed_page": original_page - 16, "original_pdf_page": original_page,
                "chapter": chapter, "char_count": len(text), "status": status,
                "preview": text[:180].replace("\n", " | "),
                "include": "", "review_note": "",
            })
            if status != "needs_content_review":
                issues.append({"pdf_page": pdf_page, "status": status, "error": error})
    with (OUTPUT_DIR / "pages.jsonl").open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    with (OUTPUT_DIR / "page_inventory.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=inventory[0].keys())
        writer.writeheader()
        writer.writerows(inventory)
    (OUTPUT_DIR / "extraction_log.json").write_text(
        json.dumps(issues, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifest = {
        "source_id": "openstax-principles-economics-3e",
        "title": "Principles of Economics 3e",
        "publisher": "OpenStax, Rice University",
        "source_path_or_url": "data/raw/economics-chapters-3-4.pdf",
        "source_url": "https://openstax.org/details/books/principles-economics-3e/",
        "download_url": "https://assets.openstax.org/oscms-prodcms/media/documents/principles-economics-3e_-_WEB.pdf",
        "accessed_at": "2026-11-13",
        "license_or_permission": "CC BY-NC-SA 4.0; see excerpt PDF page 1 (original PDF page 4)",
        "attribution": "Access for free at openstax.org. OpenStax, Rice University, Principles of Economics 3e.",
        "snapshot": {
            "sha256": hashlib.sha256(PDF_PATH.read_bytes()).hexdigest(),
            "size_bytes": PDF_PATH.stat().st_size,
            "total_physical_pages": len(reader.pages),
            "copyright_notice_in_file": "2026 Rice University",
            "original_publication_year_in_file": 2022,
        },
        "scope": "Demand and supply, including labor and financial markets",
        "page_numbering": "page is the one-based physical page in the 53-page excerpt. original_pdf_page and printed_page preserve the original mapping; see data/excerpt_page_map.csv.",
        "counting_rule": "Count relevant instructional pages only after content review. Exclude cover, contents, blank and references-only pages. Short pages require review, not automatic exclusion.",
        "selected_page_count": len(records),
        "verified_content_page_count": None,
        "review_status": "pending_content_and_visual_review",
        "pages": [
            {key: r[key] for key in ("page", "printed_page", "original_pdf_page", "chapter", "char_count", "status")}
            for r in records
        ],
        "filter_metadata": {
            "chapter": {"type": "integer", "values": [3, 4], "provenance": "Chapter headings and table of contents in source PDF", "purpose": "Restrict retrieval to the chapter explicitly requested by the question or prior user context"}
        },
        "limitations": [
            "Text extraction does not preserve graph geometry or reliably reconstruct tables.",
            "Some words are joined in the source extraction; normalization does not infer missing spaces.",
            "Paragraph structure and printed-page mapping require checking against the PDF.",
            "The original full PDF was removed locally; the excerpt includes its copyright page, which is excluded from indexing.",
        ],
    }
    review_path = ROOT / "data/corpus_review.json"
    if review_path.exists():
        review = json.loads(review_path.read_text(encoding="utf-8"))
        if review["excerpt_sha256"] == manifest["snapshot"]["sha256"]:
            manifest["verified_content_page_count"] = review["selected_content_pages"]
            manifest["review_status"] = "assistant_structural_review_complete; student_review_pending"
            manifest["review_evidence"] = "data/corpus_review.json"
            for row in manifest["pages"]:
                row["content_review"] = "AI structural/source review; student confirmation pending"
            for row in inventory:
                row["include"] = "true"
                if row["pdf_page"] in (2, 35):
                    note = "Chapter opening with learning objectives and substantive introduction, not a cover-only page."
                elif row["pdf_page"] in (33, 34):
                    note = "Relevant glossary/summary with economic definitions, not references-only."
                elif row["pdf_page"] == 53:
                    note = "Graph plus substantive caption/conclusion on nurses' wages and uncertain employment."
                else:
                    note = "Instructional text/examples in selected chapter, with extracted readable content."
                row["review_note"] = "AI review: " + note + " Student confirmation pending."
            with (OUTPUT_DIR / "page_inventory.csv").open("w", newline="", encoding="utf-8-sig") as stream:
                writer = csv.DictWriter(stream, fieldnames=inventory[0].keys())
                writer.writeheader()
                writer.writerows(inventory)
    (ROOT / "data/manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Selected pages: {len(records)}")
    print(f"Pages with text: {sum(bool(r['text']) for r in records)}")
    print(f"Pages needing extraction review: {len(issues)}")
    print(f"Extracted characters: {sum(r['char_count'] for r in records)}")
    print("Content eligibility still requires manual review.")
    for chapter, title, start, end in SELECTIONS:
        for page_number in (start, end):
            record = next(r for r in records if r["page"] == page_number)
            print(f"\nPDF PAGE {page_number}:")
            print(record["text"][:700])
            print("...")
            print(record["text"][-250:])
    print(f"\nOutputs saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
