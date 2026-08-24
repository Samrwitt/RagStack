# Parsing

Status: **Phase 3 implemented**. Documents move `FETCHED → PARSING → PARSED` in the same ingestion job. Normalization starts in Phase 4.

## Goals

1. Never flatten a document into one giant string before chunking.
2. Emit typed blocks (title, heading, paragraph, list, code, table, quote, image caption).
3. Keep page and section on blocks so later citations can point at a location.
4. Version parsers (`markdown:1`) so a reprocess can replay raw bytes with a new parser.
5. Use OCR only when a PDF has too little digital text.

## Parser protocol

```python
class DocumentParser(Protocol):
    name: str
    version: int
    def supports(self, mime_type: str) -> bool: ...
    def parse(self, raw_document: RawDocument) -> ParsedDocument: ...
```

`ParserRegistry` picks the first parser that `supports` the MIME type. Unknown types raise `UnsupportedMimeError` (permanent — Celery does not retry).

| Parser | MIME | Notes |
| --- | --- | --- |
| `txt` | `text/plain` | ATX headings, lists, quotes, fenced/indented code |
| `markdown` | `text/markdown` | markdown-it tokens, including GFM tables |
| `html` | `text/html` | Drops `script`/`style`; walks headings, lists, tables |
| `docx` | WordprocessingML | Body order so tables stay with surrounding paragraphs |
| `pdf` | `application/pdf` | pdfplumber text + tables; font-size headings; OCR fallback |

## PDF / OCR

Digital extraction always runs first. OCR (Tesseract via `pdf2image`) runs only when extracted characters are below `pdf_ocr_min_chars_per_page * page_count` (default 40). The Docker image includes `tesseract-ocr` and `poppler-utils`. If OCR is unavailable and the PDF has no digital text, the job fails permanently.

## Persistence

- Parser metadata lives on `document_versions` (`parser_name`, `parser_version`, `used_ocr`, `parsed_block_count`, `parse_warnings`, `parsed_at`).
- Blocks live in `document_blocks`, keyed by `version_id` + `ordinal`. Old versions keep their blocks.
- Reprocess with an unchanged hash re-parses in place (`PARSED → PARSING → PARSED`) and does not bump `version_number`.

## API

```text
GET /api/v1/documents/{id}/blocks
GET /api/v1/documents/{id}/blocks?version=1
```

Inspect parser identity on `GET /api/v1/documents/{id}/versions`.
