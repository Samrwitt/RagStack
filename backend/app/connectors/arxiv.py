"""arXiv research paper connector adhering to SourceConnector protocol."""

from __future__ import annotations

import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import AsyncIterator
from typing import Any

from app.connectors.base import metadata_with_connector, permissions_from_config
from app.connectors.protocol import (
    ConnectorConfigurationError,
    ConnectorPermission,
    DiscoveredItem,
    FetchedContent,
    SourceConnector,
)

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


class ArxivConnector(SourceConnector):
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.arxiv_id = self._extract_arxiv_id(config)
        self.search_query = str(config.get("search_query") or "").strip()
        self.max_results = int(config.get("max_results", 5))

        if not self.arxiv_id and not self.search_query:
            raise ConnectorConfigurationError("arXiv connector requires 'arxiv_id', 'paper_url', or 'search_query'")

        self._cached_papers: dict[str, dict[str, Any]] = {}
        self._checkpoint: dict[str, Any] = {}

    async def discover(
        self, checkpoint: dict[str, Any] | None = None
    ) -> AsyncIterator[DiscoveredItem]:
        del checkpoint
        if self.arxiv_id:
            url = f"http://export.arxiv.org/api/query?id_list={self.arxiv_id}"
        else:
            query = urllib.parse.quote(self.search_query)
            url = f"http://export.arxiv.org/api/query?search_query={query}&max_results={self.max_results}"

        req = urllib.request.Request(url, headers={"User-Agent": "RagStack/1.0 (arXiv connector)"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read()
        except Exception as exc:
            raise ConnectorConfigurationError(f"Failed fetching arXiv metadata: {exc}") from exc

        root = ET.fromstring(content)
        entries = root.findall("atom:entry", ATOM_NS)
        if not entries and self.arxiv_id:
            raise ConnectorConfigurationError(f"arXiv paper {self.arxiv_id} not found")

        for entry in entries:
            id_text = entry.findtext("atom:id", "", ATOM_NS)
            paper_id = self._parse_id_from_url(id_text)
            title = entry.findtext("atom:title", "", ATOM_NS).strip().replace("\n", " ")
            summary = entry.findtext("atom:summary", "", ATOM_NS).strip()
            published = entry.findtext("atom:published", "", ATOM_NS)
            updated = entry.findtext("atom:updated", "", ATOM_NS)

            authors = [
                author.findtext("atom:name", "", ATOM_NS)
                for author in entry.findall("atom:author", ATOM_NS)
            ]

            categories = [
                cat.attrib.get("term")
                for cat in entry.findall("atom:category", ATOM_NS)
                if cat.attrib.get("term")
            ]

            pdf_url = f"https://arxiv.org/pdf/{paper_id}.pdf"
            abs_url = f"https://arxiv.org/abs/{paper_id}"

            self._cached_papers[paper_id] = {
                "arxiv_id": paper_id,
                "title": title,
                "authors": authors,
                "summary": summary,
                "published": published,
                "updated": updated,
                "categories": categories,
                "pdf_url": pdf_url,
                "abs_url": abs_url,
            }

            yield DiscoveredItem(
                source_id=paper_id,
                title=f"[arXiv:{paper_id}] {title}",
                mime_type="application/pdf",
                source_url=abs_url,
                metadata=metadata_with_connector(
                    "arxiv",
                    {
                        "arxiv_id": paper_id,
                        "authors": authors,
                        "pdf_url": pdf_url,
                        "abs_url": abs_url,
                    },
                ),
            )

    async def fetch(self, source_id: str) -> FetchedContent:
        paper_id = self._extract_arxiv_id({"arxiv_id": source_id}) or source_id
        paper_info = self._cached_papers.get(paper_id)

        if not paper_info:
            # Fallback metadata fetch if not in cache
            url = f"http://export.arxiv.org/api/query?id_list={paper_id}"
            req = urllib.request.Request(url, headers={"User-Agent": "RagStack/1.0 (arXiv connector)"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                root = ET.fromstring(resp.read())
                entry = root.find("atom:entry", ATOM_NS)
                if entry is not None:
                    title = entry.findtext("atom:title", "", ATOM_NS).strip().replace("\n", " ")
                    summary = entry.findtext("atom:summary", "", ATOM_NS).strip()
                    authors = [
                        author.findtext("atom:name", "", ATOM_NS)
                        for author in entry.findall("atom:author", ATOM_NS)
                    ]
                    paper_info = {
                        "arxiv_id": paper_id,
                        "title": title,
                        "authors": authors,
                        "summary": summary,
                        "pdf_url": f"https://arxiv.org/pdf/{paper_id}.pdf",
                        "abs_url": f"https://arxiv.org/abs/{paper_id}",
                    }
                else:
                    paper_info = {
                        "arxiv_id": paper_id,
                        "title": f"arXiv Paper {paper_id}",
                        "authors": [],
                        "summary": "",
                        "pdf_url": f"https://arxiv.org/pdf/{paper_id}.pdf",
                        "abs_url": f"https://arxiv.org/abs/{paper_id}",
                    }

        pdf_url = paper_info["pdf_url"]
        pdf_bytes = self._download_pdf(pdf_url)
        mime_type = "application/pdf"

        if pdf_bytes is None:
            # If PDF download fails, fall back to plain text abstract
            abstract_text = f"Title: {paper_info['title']}\nAuthors: {', '.join(paper_info.get('authors', []))}\narXiv ID: {paper_id}\n\nAbstract:\n{paper_info.get('summary', '')}"
            pdf_bytes = abstract_text.encode("utf-8")
            mime_type = "text/plain"

        return FetchedContent(
            source_id=paper_id,
            title=f"[arXiv:{paper_id}] {paper_info['title']}",
            mime_type=mime_type,
            data=pdf_bytes,
            source_url=paper_info["abs_url"],
            metadata=metadata_with_connector(
                "arxiv",
                {
                    "arxiv_id": paper_id,
                    "authors": paper_info.get("authors", []),
                    "pdf_url": pdf_url,
                    "abs_url": paper_info["abs_url"],
                },
            ),
            permissions=await self.get_permissions(source_id),
        )

    async def get_permissions(self, source_id: str) -> ConnectorPermission:
        del source_id
        return permissions_from_config(self.config)

    async def checkpoint(self) -> dict[str, Any]:
        return self._checkpoint

    def _download_pdf(self, pdf_url: str) -> bytes | None:
        try:
            req = urllib.request.Request(pdf_url, headers={"User-Agent": "RagStack/1.0 (arXiv connector)"})
            with urllib.request.urlopen(req, timeout=25) as resp:
                if resp.status == 200:
                    return resp.read()
        except Exception:
            pass
        return None

    def _extract_arxiv_id(self, config: dict[str, Any]) -> str | None:
        raw = str(config.get("arxiv_id") or config.get("paper_url") or "").strip()
        if not raw:
            return None
        match = re.search(r"(\d{4}\.\d{4,5}(?:v\d+)?|[a-zA-Z\-]+(?:\.[a-zA-Z\-]+)?/\d{7})", raw)
        if match:
            return match.group(1)
        return raw

    def _parse_id_from_url(self, url: str) -> str:
        match = re.search(r"(\d{4}\.\d{4,5}(?:v\d+)?|[a-zA-Z\-]+(?:\.[a-zA-Z\-]+)?/\d{7})", url)
        if match:
            return match.group(1)
        return url.split("/")[-1]
