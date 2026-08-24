"""Markdown parser built on markdown-it tokens (not a flattened HTML dump)."""

from __future__ import annotations

from markdown_it import MarkdownIt

from app.ingestion.mime import canonicalize_mime
from app.parsers.blocks import BlockAccumulator, fallback_title
from app.parsers.models import BlockType, ParsedDocument, RawDocument
from app.parsers.text import decode_bytes

_MD = MarkdownIt("commonmark").enable("table").enable("strikethrough")


class MarkdownParser:
    name = "markdown"
    version = 1

    def supports(self, mime_type: str) -> bool:
        return canonicalize_mime(mime_type) in {"text/markdown", "text/x-markdown"}

    def parse(self, raw_document: RawDocument) -> ParsedDocument:
        source = decode_bytes(raw_document.data)
        acc = BlockAccumulator(default_title=raw_document.title)
        title = fallback_title(raw_document.filename, raw_document.title)
        tokens = _MD.parse(source)
        _walk(tokens, acc)
        return acc.seal(parser_name=self.name, parser_version=self.version, fallback=title)


def _walk(tokens: list, acc: BlockAccumulator) -> None:
    i = 0
    while i < len(tokens):
        token = tokens[i]
        kind = token.type
        if kind == "heading_open":
            level = int(token.tag[1])
            text, images = _inline_content(tokens[i + 1])
            if level == 1 and acc.title is None:
                acc.add(BlockType.TITLE, text, level=1)
            else:
                acc.add(BlockType.HEADING, text, level=level)
            _captions(acc, images)
            i += 3
            continue
        if kind == "paragraph_open":
            text, images = _inline_content(tokens[i + 1])
            acc.add(BlockType.PARAGRAPH, text)
            _captions(acc, images)
            i += 3
            continue
        if kind == "fence":
            acc.add(
                BlockType.CODE,
                token.content,
                metadata={"language": (token.info or "").strip()},
            )
            i += 1
            continue
        if kind == "code_block":
            acc.add(BlockType.CODE, token.content, metadata={"language": ""})
            i += 1
            continue
        if kind in {"bullet_list_open", "ordered_list_open"}:
            items, i, ordered = _collect_list(tokens, i)
            acc.add(
                BlockType.LIST,
                "\n".join(items),
                metadata={"ordered": ordered, "items": items},
            )
            continue
        if kind == "blockquote_open":
            quoted, i = _collect_until(tokens, i, "blockquote_close")
            acc.add(BlockType.QUOTE, quoted)
            continue
        if kind == "table_open":
            rows, i = _collect_table(tokens, i)
            acc.add(
                BlockType.TABLE,
                _pipe_table(rows),
                metadata={"rows": rows},
            )
            continue
        if kind == "html_block":
            acc.add(BlockType.PARAGRAPH, _strip_tags(token.content))
            i += 1
            continue
        i += 1


def _inline_content(token) -> tuple[str, list[str]]:  # noqa: ANN001
    text = token.content if token is not None else ""
    captions: list[str] = []
    for child in getattr(token, "children", None) or []:
        if child.type == "image":
            alt = child.content or ""
            title = ""
            if child.attrs:
                title = str(child.attrs.get("title") or "")
            caption = alt or title
            if caption:
                captions.append(caption)
    return text, captions


def _captions(acc: BlockAccumulator, captions: list[str]) -> None:
    for caption in captions:
        acc.add(BlockType.IMAGE_CAPTION, caption)


def _collect_list(tokens: list, start: int) -> tuple[list[str], int, bool]:
    ordered = tokens[start].type == "ordered_list_open"
    items: list[str] = []
    i = start + 1
    close = "ordered_list_close" if ordered else "bullet_list_close"
    while i < len(tokens) and tokens[i].type != close:
        if tokens[i].type == "list_item_open":
            text, i = _collect_list_item(tokens, i)
            if text:
                items.append(text)
        else:
            i += 1
    return items, i + 1, ordered


def _collect_list_item(tokens: list, start: int) -> tuple[str, int]:
    parts: list[str] = []
    i = start + 1
    while i < len(tokens) and tokens[i].type != "list_item_close":
        token = tokens[i]
        if token.type == "paragraph_open":
            text, _ = _inline_content(tokens[i + 1])
            parts.append(text)
            i += 3
        elif token.type in {"bullet_list_open", "ordered_list_open"}:
            nested, i, _ = _collect_list(tokens, i)
            parts.extend(nested)
        elif token.type == "inline":
            parts.append(token.content)
            i += 1
        elif token.type == "fence":
            parts.append(token.content.strip())
            i += 1
        else:
            i += 1
    return "\n".join(part for part in parts if part.strip()), i + 1


def _collect_until(tokens: list, start: int, close: str) -> tuple[str, int]:
    parts: list[str] = []
    i = start + 1
    while i < len(tokens) and tokens[i].type != close:
        token = tokens[i]
        if token.type == "inline":
            parts.append(token.content)
            i += 1
        elif token.type == "paragraph_open":
            text, _ = _inline_content(tokens[i + 1])
            parts.append(text)
            i += 3
        else:
            i += 1
    return " ".join(part for part in parts if part.strip()), i + 1


def _collect_table(tokens: list, start: int) -> tuple[list[list[str]], int]:
    rows: list[list[str]] = []
    current: list[str] = []
    i = start + 1
    while i < len(tokens) and tokens[i].type != "table_close":
        token = tokens[i]
        if token.type in {"th_open", "td_open"}:
            if tokens[i + 1].type == "inline":
                current.append(tokens[i + 1].content.strip())
                i += 3
            else:
                current.append("")
                i += 1
        elif token.type == "tr_close":
            if current:
                rows.append(current)
                current = []
            i += 1
        else:
            i += 1
    return rows, i + 1


def _pipe_table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    lines = ["| " + " | ".join(normalized[0]) + " |"]
    if len(normalized) > 1:
        lines.append("| " + " | ".join("---" for _ in range(width)) + " |")
        for row in normalized[1:]:
            lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _strip_tags(html: str) -> str:
    from html import unescape
    from re import sub

    return unescape(sub(r"<[^>]+>", " ", html))
