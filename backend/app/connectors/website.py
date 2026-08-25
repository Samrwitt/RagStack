"""Website crawler connector with sitemap, canonical URL, and rate-limit support."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
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
        checkpoint = checkpoint or {}
        previous_pages = dict(checkpoint.get("pages", {}))
        seen: set[str] = set()
        queued: set[str] = set()
        queue = [*self.start_urls, *previous_pages.keys()]
        queued.update(queue)
        allowed_hosts = {
            urlparse(url).netloc
            for url in [*self.start_urls, *previous_pages.keys()]
            if urlparse(url).netloc
        }
        discovered_urls: set[str] = set()
        timeout = float(self.config.get("timeout_seconds", 30))
        async with httpx.AsyncClient(timeout=timeout) as client:
            for sitemap_url in self.sitemap_urls:
                try:
                    for url in await _sitemap_urls(client, sitemap_url):
                        if urlparse(url).netloc:
                            allowed_hosts.add(urlparse(url).netloc)
                        if url not in queued:
                            queue.append(url)
                            queued.add(url)
                except Exception:
                    continue
            while queue and len(self._pages) < self.max_pages:
                url = queue.pop(0)
                if url in seen:
                    continue
                if self.request_delay_seconds > 0:
                    await asyncio.sleep(self.request_delay_seconds)
                seen.add(url)
                try:
                    response = await client.get(
                        url,
                        follow_redirects=True,
                        headers=_conditional_headers(_page_checkpoint(previous_pages, url)),
                    )
                except httpx.HTTPError:
                    continue

                if response.status_code == 304:
                    metadata = _page_checkpoint(previous_pages, url)
                    canonical = str(metadata.get("canonical_url") or url)
                    discovered_urls.add(canonical)
                    self._checkpoint = _checkpoint(previous_pages, discovered_urls)
                    continue

                if response.status_code in (404, 410):
                    metadata = _page_checkpoint(previous_pages, url)
                    canonical = str(metadata.get("canonical_url") or url)
                    previous_pages.pop(canonical, None)
                    previous_pages.pop(url, None)
                    yield DiscoveredItem(
                        source_id=canonical,
                        title=canonical,
                        source_url=canonical,
                        deleted=True,
                        metadata=metadata_with_connector("website", {"url": canonical}),
                    )
                    continue

                if response.status_code >= 400:
                    continue

                content_type = response.headers.get("content-type", "text/html").split(";")[0]
                body = response.content
                parser = _PageParser()
                if content_type == "text/html":
                    parser.feed(response.text)
                    for link in parser.links:
                        next_url = urljoin(str(response.url), link)
                        if self.same_domain and allowed_hosts and urlparse(next_url).netloc not in allowed_hosts:
                            continue
                        if next_url not in seen and next_url not in queued:
                            queue.append(next_url)
                            queued.add(next_url)
                canonical = parser.canonical or str(response.url)
                discovered_urls.add(canonical)
                title = parser.title or urlparse(canonical).path.strip("/") or canonical
                self._pages[canonical] = (title, body, content_type)
                previous_pages[canonical] = {
                    "canonical_url": canonical,
                    "etag": response.headers.get("etag"),
                    "last_modified": response.headers.get("last-modified"),
                    "last_seen_at": datetime.now(UTC).isoformat(),
                }
                self._checkpoint = _checkpoint(previous_pages, discovered_urls)
                yield DiscoveredItem(
                    source_id=canonical,
                    title=title,
                    mime_type=content_type,
                    source_url=canonical,
                    metadata=metadata_with_connector("website", {"url": canonical}),
                )
        if self.config.get("delete_missing_from_sitemap") and self.sitemap_urls:
            for missing_url in sorted(set(previous_pages) - discovered_urls):
                yield DiscoveredItem(
                    source_id=missing_url,
                    title=missing_url,
                    source_url=missing_url,
                    deleted=True,
                    metadata=metadata_with_connector("website", {"url": missing_url}),
                )

    async def fetch(self, source_id: str) -> FetchedContent:
        if source_id not in self._pages:
            timeout = float(self.config.get("timeout_seconds", 30))
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(source_id, follow_redirects=True)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "text/html").split(";")[0]
                parser = _PageParser()
                if content_type == "text/html":
                    parser.feed(response.text)
                canonical = parser.canonical or str(response.url)
                title = parser.title or urlparse(canonical).path.strip("/") or canonical
                self._pages[source_id] = (title, response.content, content_type)

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


def _conditional_headers(metadata: dict[str, Any]) -> dict[str, str]:
    headers: dict[str, str] = {}
    if metadata.get("etag"):
        headers["If-None-Match"] = str(metadata["etag"])
    if metadata.get("last_modified"):
        headers["If-Modified-Since"] = str(metadata["last_modified"])
    return headers


def _page_checkpoint(pages: dict[str, Any], url: str) -> dict[str, Any]:
    if url in pages and isinstance(pages[url], dict):
        return pages[url]
    for metadata in pages.values():
        if isinstance(metadata, dict) and metadata.get("canonical_url") == url:
            return metadata
    return {}


def _checkpoint(pages: dict[str, Any], discovered_urls: set[str]) -> dict[str, Any]:
    return {
        "pages": pages,
        "seen_urls": sorted(pages),
        "last_discovered_urls": sorted(discovered_urls),
        "last_sync_at": datetime.now(UTC).isoformat(),
    }
