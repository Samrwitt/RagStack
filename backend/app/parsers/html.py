"""HTML parser. Scripts/styles are dropped; structure is walked in document order."""

from __future__ import annotations

from bs4 import BeautifulSoup, NavigableString, Tag

from app.ingestion.mime import canonicalize_mime
from app.parsers.blocks import BlockAccumulator, fallback_title
from app.parsers.models import BlockType, ParsedDocument, RawDocument
from app.parsers.text import decode_bytes

_SKIP = {"script", "style", "noscript", "svg", "iframe", "template"}
_HEADINGS = {f"h{i}": i for i in range(1, 7)}


class HtmlParser:
    name = "html"
    version = 1

    def supports(self, mime_type: str) -> bool:
        return canonicalize_mime(mime_type) in {"text/html", "application/xhtml+xml"}

    def parse(self, raw_document: RawDocument) -> ParsedDocument:
        source = decode_bytes(raw_document.data)
        soup = _soup(source)
        for tag in soup.find_all(_SKIP):
            tag.decompose()
        acc = BlockAccumulator(default_title=raw_document.title)
        title = fallback_title(raw_document.filename, raw_document.title)
        if soup.title and soup.title.string:
            acc.add(BlockType.TITLE, soup.title.get_text(" ", strip=True), level=1)
        root = soup.body if soup.body else soup
        _walk(root, acc)
        return acc.seal(parser_name=self.name, parser_version=self.version, fallback=title)


def _soup(source: str) -> BeautifulSoup:
    try:
        return BeautifulSoup(source, "lxml")
    except Exception:
        return BeautifulSoup(source, "html.parser")


def _walk(node: Tag, acc: BlockAccumulator) -> None:
    for child in list(node.children):
        if isinstance(child, NavigableString):
            text = str(child).strip()
            if text and child.parent is node and node.name in {"body", "div", "article", "main", "section"}:
                acc.add(BlockType.PARAGRAPH, text)
            continue
        if not isinstance(child, Tag):
            continue
        name = child.name.lower() if child.name else ""
        if name in _SKIP:
            continue
        if name in _HEADINGS:
            level = _HEADINGS[name]
            text = child.get_text(" ", strip=True)
            if level == 1 and acc.title is None:
                acc.add(BlockType.TITLE, text, level=1)
            else:
                acc.add(BlockType.HEADING, text, level=level)
            continue
        if name == "p":
            acc.add(BlockType.PARAGRAPH, child.get_text(" ", strip=True))
            _images(child, acc)
            continue
        if name in {"ul", "ol"}:
            items = [
                li.get_text(" ", strip=True)
                for li in child.find_all("li", recursive=False)
                if li.get_text(" ", strip=True)
            ]
            acc.add(
                BlockType.LIST,
                "\n".join(items),
                metadata={"ordered": name == "ol", "items": items},
            )
            continue
        if name == "pre":
            acc.add(
                BlockType.CODE,
                child.get_text(),
                metadata={"language": _code_language(child)},
            )
            continue
        if name == "blockquote":
            acc.add(BlockType.QUOTE, child.get_text(" ", strip=True))
            continue
        if name == "table":
            rows = _table_rows(child)
            acc.add(BlockType.TABLE, _pipe_table(rows), metadata={"rows": rows})
            continue
        if name in {"figcaption"}:
            acc.add(BlockType.IMAGE_CAPTION, child.get_text(" ", strip=True))
            continue
        if name == "img":
            caption = (child.get("alt") or child.get("title") or "").strip()
            if caption:
                acc.add(BlockType.IMAGE_CAPTION, caption)
            continue
        _walk(child, acc)


def _images(tag: Tag, acc: BlockAccumulator) -> None:
    for img in tag.find_all("img"):
        caption = (img.get("alt") or img.get("title") or "").strip()
        if caption:
            acc.add(BlockType.IMAGE_CAPTION, caption)


def _code_language(pre: Tag) -> str:
    code = pre.find("code")
    classes = []
    if code and code.get("class"):
        classes.extend(code.get("class"))
    if pre.get("class"):
        classes.extend(pre.get("class"))
    for item in classes:
        if item.startswith("language-"):
            return item.removeprefix("language-")
    return ""


def _table_rows(table: Tag) -> list[list[str]]:
    rows: list[list[str]] = []
    for tr in table.find_all("tr"):
        cells = [
            cell.get_text(" ", strip=True)
            for cell in tr.find_all(["th", "td"], recursive=False)
        ]
        if cells:
            rows.append(cells)
    return rows


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
