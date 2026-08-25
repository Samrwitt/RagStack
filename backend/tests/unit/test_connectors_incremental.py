from datetime import datetime
from uuid import uuid4

import pytest
import httpx

from app.connectors.google_drive import GoogleDriveConnector
from app.connectors.website import WebsiteConnector
from app.connectors.github import GitHubConnector
from app.connectors.postgres import PostgresConnector, _coerce_pk_val, _cursor_from_row
from app.observability.metrics import increment, set_gauge, observe, render_prometheus


@pytest.mark.asyncio
async def test_google_drive_410_fallback(monkeypatch) -> None:
    calls = []

    class Response:
        def __init__(self, status_code, payload=None) -> None:
            self.status_code = status_code
            self._payload = payload or {}

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                request = httpx.Request("GET", "http://test")
                response = httpx.Response(self.status_code, request=request)
                raise httpx.HTTPStatusError("410 Gone", request=request, response=response)

        def json(self):
            return self._payload

    class Client:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def get(self, url, params=None, **kwargs):
            calls.append((url, params))
            if "changes" in url and params and params.get("pageToken") == "expired-token":
                return Response(410)
            if "changes/startPageToken" in url:
                return Response(200, {"startPageToken": "new-start-token"})
            if "files" in url:
                return Response(
                    200,
                    {
                        "files": [
                            {
                                "id": "full-file-1",
                                "name": "Full File",
                                "mimeType": "text/plain",
                                "modifiedTime": "2026-08-25T12:00:00Z",
                            }
                        ],
                    },
                )
            return Response(200, {"files": []})

    monkeypatch.setattr("app.connectors.google_drive.httpx.AsyncClient", Client)
    connector = GoogleDriveConnector(config={"access_token": "token"})

    discovered = [item async for item in connector.discover({"start_page_token": "expired-token"})]

    assert len(discovered) == 1
    assert discovered[0].source_id == "full-file-1"
    assert (await connector.checkpoint())["start_page_token"] == "new-start-token"


@pytest.mark.asyncio
async def test_website_connector_304_and_404_handling(monkeypatch) -> None:
    class Response:
        def __init__(self, status_code, text="", headers=None) -> None:
            self.status_code = status_code
            self.text = text
            self.content = text.encode("utf-8")
            self.headers = headers or {}
            self.url = "https://example.com/page1"

    class Client:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def get(self, url, **kwargs):
            if "page1" in url:
                return Response(304)
            if "page2" in url:
                return Response(404)
            return Response(200, "<html><body><a href='/page2'>Link</a></body></html>")

    monkeypatch.setattr("app.connectors.website.httpx.AsyncClient", Client)
    connector = WebsiteConnector(config={"start_urls": ["https://example.com/start"]})

    checkpoint = {
        "pages": {
            "https://example.com/page1": {
                "canonical_url": "https://example.com/page1",
                "etag": "12345",
            },
            "https://example.com/page2": {
                "canonical_url": "https://example.com/page2",
            },
        }
    }

    discovered = [item async for item in connector.discover(checkpoint)]
    deleted_items = [d for d in discovered if d.deleted]

    assert any(d.source_id == "https://example.com/page2" for d in deleted_items)


def test_postgres_coerce_pk_val() -> None:
    assert _coerce_pk_val("123", "int") == 123
    assert _coerce_pk_val("45.6", "float") == 45.6
    assert _coerce_pk_val("abc-guid", "UUID") == "abc-guid"
    assert _coerce_pk_val(None, "int") is None


def test_postgres_cursor_from_row_preserves_prev_updated_at() -> None:
    prev_cursor = {"updated_at": "2026-08-25T10:00:00Z", "pk": 10, "pk_type": "int"}
    row = {"id": 11, "updated_at": None}
    cursor = _cursor_from_row(row, "id", "updated_at", prev_cursor)

    assert cursor["updated_at"] == "2026-08-25T10:00:00Z"
    assert cursor["pk"] == 11


def test_metrics_increment_and_render() -> None:
    increment("test_metric_total", 5.0, labels={"env": "test"})
    set_gauge("test_gauge", 42.0)
    observe("test_latency", 0.123)

    rendered = render_prometheus()
    assert "test_metric_total" in rendered or "test_gauge" in rendered
