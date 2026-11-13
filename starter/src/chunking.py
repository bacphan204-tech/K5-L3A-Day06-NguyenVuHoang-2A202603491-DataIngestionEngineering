"""Page-bounded fixed windows and sentence-boundary-aware chunks."""
import hashlib
import re
from .models import Chunk, DocumentPage


def make_chunk(page, start, end, method):
    text = page.text[start:end]
    digest = hashlib.sha256(f"{method}|{page.document_id}|{page.page}|{start}|{end}|{text}".encode()).hexdigest()[:24]
    return Chunk(digest, page.document_id, page.source, page.page, text,
                 {**page.metadata, "start_char": start, "end_char": end})


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("Require size > 0 and 0 <= overlap < size")
    chunks = []
    for start in range(0, len(page.text), size - overlap):
        end = min(start + size, len(page.text))
        chunks.append(make_chunk(page, start, end, f"fixed-{size}-{overlap}"))
        if end == len(page.text):
            break
    return chunks


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    """Prefer sentence boundaries: PDF line breaks are unreliable paragraphs.

    Oversized sentences split at whitespace. No cross-page context or overlap.
    """
    if max_size <= 0:
        raise ValueError("max_size must be positive")
    boundaries = [m.end() for m in re.finditer(r'[.!?][”"\']?\s+', page.text)]
    chunks, start = [], 0
    while start < len(page.text):
        limit = min(start + max_size, len(page.text))
        if limit == len(page.text):
            end = limit
        else:
            candidates = [b for b in boundaries if start + max_size // 3 <= b <= limit]
            end = max(candidates) if candidates else page.text.rfind(" ", start + 1, limit)
            if end <= start:
                end = limit
        chunks.append(make_chunk(page, start, end, f"sentence-{max_size}"))
        start = end
    return chunks
