import re
from pathlib import Path


class ExtractionError(Exception):
    pass


def extract_text(path, ext):
    """Return a list of (page_number_or_None, text)."""
    ext = ext.lower()
    try:
        if ext == ".pdf":
            pages = _pdf(path)
        elif ext == ".docx":
            pages = _docx(path)
        elif ext in (".txt", ".md"):
            pages = _plain(path)
        else:
            raise ExtractionError(f"Unsupported file type: {ext}")
    except ExtractionError:
        raise
    except Exception as exc:  # corrupt files etc.
        raise ExtractionError(f"Could not read the document: {exc.__class__.__name__}") from exc
    pages = [(p, t) for p, t in pages if t and t.strip()]
    if not pages:
        raise ExtractionError("No readable text found (scanned PDFs need OCR first).")
    return pages


def _pdf(path):
    import fitz  # PyMuPDF

    out = []
    with fitz.open(str(path)) as doc:
        for number, page in enumerate(doc, start=1):
            out.append((number, page.get_text("text")))
    return out


def _docx(path):
    import docx

    document = docx.Document(str(path))
    parts = [p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text.strip() for cell in row.cells))
    return [(None, "\n".join(parts))]


def _plain(path):
    raw = Path(path).read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    return [(None, text)]


def chunk_text(text, size, overlap):
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    chunks, start, n = [], 0, len(text)
    while start < n:
        end = min(start + size, n)
        if end < n:
            window = text[start:end]
            cut = max(window.rfind("\n\n"), window.rfind(". "), window.rfind("\n"))
            if cut > size * 0.5:
                end = start + cut + 1
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks


def chunk_pages(pages, size, overlap):
    """Return a list of {'text': str, 'page': int|None}."""
    result = []
    for page, text in pages:
        for piece in chunk_text(text, size, overlap):
            result.append({"text": piece, "page": page})
    return result
