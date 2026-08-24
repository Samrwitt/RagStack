"""Website crawler connector with sitemap, canonical URL, and rate-limit support."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import httpx

from app.connectors.base import metadata_with_connector, permissions_from_config
from app.connectors.protocol import ConnectorPermission, DiscoveredItem, FetchedContent


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.links: list[str] = []
        self.canonical: str | None = None
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "title":
            self._in_title = True
        if tag == "a" and values.get("href"):
            self.links.append(values["href"] or "")
        if tag == "link" and values.get("rel") == "canonical" and values.get("href"):
            self.canonical = values["href"]

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data.strip()


class WebsiteConnector:
    def __init__(self, *, config: dict[str, Any]) -> None:
        self.config = config
        self.start_urls = [str(item) for item in config.get("start_urls", [])]
        if not self.start_urls and config.get("base_url"):
            self.start_urls = [str(config["base_url"])]
        self.sitemap_urls = [str(item) for item in config.get("sitemap_urls", [])]
        self.max_pages = int(config.get("max_pages", 100))
        self.same_domain = bool(config.get("same_domain", True))
        self.request_delay_seconds = float(config.get("request_delay_seconds", 0))
        self._pages: dict[str, tuple[str, bytes, str]] = {}
        self._checkpoint: dict[str, Any] = {}

    async def discover(
        self,
        checkpoint: dict[str, Any] | None = None,
    ) -> AsyncIterator[DiscoveredItem]:
        seen = set((checkpoint or {}).get("seen_urls", []))
        queue = [url for url in self.start_urls if url not in seen]
        allowed_hosts = {urlparse(url).netloc for url in self.start_urls}
        timeout = float(self.config.get("timeout_seconds", 30))
        async with httpx.AsyncClient(timeout=timeout) as client:
            for sitemap_url in self.sitemap_urls:
                for url in await _sitemap_urls(client, sitemap_url):
                    if url not in seen and url not in queue:
                        queue.append(url)
            while queue and len(self._pages) < self.max_pages:
                url = queue.pop(0)
                if url in seen:
                    continue
                if self.request_delay_seconds > 0:
                    await asyncio.sleep(self.request_delay_seconds)
                seen.add(url)
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "text/html").split(";")[0]
                body = response.content
                parser = _PageParser()
                if content_type == "text/html":
                    parser.feed(response.text)
                    for link in parser.links:
                        next_url = urljoin(str(response.url), link)
                        if self.same_domain and urlparse(next_url).netloc not in allowed_hosts:
                            continue
                        if next_url not in seen and next_url not in queue:
                            queue.append(next_url)
                canonical = parser.canonical or str(response.url)
                title = parser.title or urlparse(canonical).path.strip("/") or canonical
                self._pages[canonical] = (title, body, content_type)
                self._checkpoint = {"seen_urls": sorted(seen)}
                yield DiscoveredItem(
                    source_id=canonical,
                    title=title,
                    mime_type=content_type,
                    source_url=canonical,
                    metadata=metadata_with_connector("website", {"url": canonical}),
                )

    async def fetch(self, source_id: str) -> FetchedContent:
        title, body, mime_type = self._pages[source_id]
        return FetchedContent(
            source_id=source_id,
            title=title,
            mime_type=mime_type,
            data=body,
            source_url=source_id,
            metadata=metadata_with_connector("website", {"url": source_id}),
            permissions=await self.get_permissions(source_id),
        )

    async def get_permissions(self, source_id: str) -> ConnectorPermission:
        del source_id
        return permissions_from_config(self.config)

    async def checkpoint(self) -> dict[str, Any]:
        return self._checkpoint


async def _sitemap_urls(client: httpx.AsyncClient, sitemap_url: str) -> list[str]:
    response = await client.get(sitemap_url)
    response.raise_for_status()
    root = ElementTree.fromstring(response.content)
    urls: list[str] = []
    for loc in root.iter():
        if loc.tag.endswith("loc") and loc.text:
            urls.append(loc.text.strip())
    return urls
