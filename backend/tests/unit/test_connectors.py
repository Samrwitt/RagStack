from datetime import datetime
from uuid import uuid4

import pytest

from app.connectors.base import metadata_with_connector, permissions_from_config
from app.connectors.github import GitHubConnector
from app.connectors.google_drive import GoogleDriveConnector
from app.connectors.postgres import _cursor_from_row
from app.connectors.registry import build_connector
from app.connectors.rest_api import RestApiConnector
from app.connectors.website import WebsiteConnector
from app.models.enums import SourceType
from app.models.source import SourceConnection


def test_permissions_from_config_normalizes_values() -> None:
    permissions = permissions_from_config({"allowed_users": [1], "allowed_groups": ["eng"]})

    assert permissions.allowed_users == ["1"]
    assert permissions.allowed_groups == ["eng"]


def test_metadata_with_connector_preserves_source_metadata() -> None:
    assert metadata_with_connector("github", {"path": "README.md"}) == {
        "connector": "github",
        "path": "README.md",
    }


def test_registry_builds_configured_connector() -> None:
    source = SourceConnection(
        id=uuid4(),
        organization_id=uuid4(),
        workspace_id=uuid4(),
        name="Docs",
        source_type=SourceType.WEBSITE.value,
        config={"base_url": "https://example.test"},
        checkpoint={},
    )

    connector = build_connector(source)

    assert isinstance(connector, WebsiteConnector)


@pytest.mark.asyncio
async def test_rest_api_connector_fetches_discovered_items(monkeypatch) -> None:
    class Response:
        def __init__(self, payload, content: bytes = b"") -> None:  # noqa: ANN001
            self._payload = payload
            self.content = content

        def raise_for_status(self) -> None:
            return None

        def json(self):  # noqa: ANN201
            return self._payload

    class Client:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            pass

        async def __aenter__(self):  # noqa: ANN201
            return self

        async def __aexit__(self, *args) -> None:  # noqa: ANN002
            return None

        async def get(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
            return Response(
                {
                    "items": [
                        {
                            "id": "policy-1",
                            "title": "Policy",
                            "content": "Employees receive 22 leave days.",
                            "deleted": True,
                        }
                    ],
                    "next_cursor": None,
                }
            )

    monkeypatch.setattr("app.connectors.rest_api.httpx.AsyncClient", Client)
    connector = RestApiConnector(
        config={
            "base_url": "https://api.example.test",
            "items_path": "/items",
            "allowed_groups": ["hr"],
        }
    )

    discovered = [item async for item in connector.discover({})]
    fetched = await connector.fetch("policy-1")

    assert discovered[0].source_id == "policy-1"
    assert discovered[0].deleted is True
    assert fetched.data == b"Employees receive 22 leave days."
    assert fetched.permissions.allowed_groups == ["hr"]
    assert (await connector.checkpoint())["cursor"] is None


@pytest.mark.asyncio
async def test_github_connector_uses_tree_checkpoint_for_updates(monkeypatch) -> None:
    requests: list[tuple[str, dict]] = []

    class Response:
        def __init__(self, payload) -> None:  # noqa: ANN001
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self):  # noqa: ANN201
            return self._payload

    class Client:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            pass

        async def __aenter__(self):  # noqa: ANN201
            return self

        async def __aexit__(self, *args) -> None:  # noqa: ANN002
            return None

        async def get(self, url, params=None, **kwargs):  # noqa: ANN001, ANN003, ANN201
            requests.append((url, params or {}))
            if url.endswith("/git/trees/main"):
                return Response(
                    {
                        "sha": "tree-2",
                        "tree": [
                            {"type": "blob", "path": "README.md", "sha": "same"},
                            {"type": "blob", "path": "docs/guide.md", "sha": "new"},
                        ],
                    }
                )
            return Response([])

    monkeypatch.setattr("app.connectors.github.httpx.AsyncClient", Client)
    connector = GitHubConnector(
        config={
            "owner": "acme",
            "repo": "docs",
            "include_issues": False,
            "include_pull_requests": False,
        }
    )

    discovered = [
        item
        async for item in connector.discover(
            {
                "files": {
                    "shas": {
                        "README.md": "same",
                        "old.md": "gone",
                    }
                }
            }
        )
    ]

    assert [item.source_id for item in discovered] == [
        "github:file:acme/docs/docs/guide.md",
        "github:file:acme/docs/old.md",
    ]
    assert discovered[0].deleted is False
    assert discovered[1].deleted is True
    assert (await connector.checkpoint())["files"]["shas"] == {
        "README.md": "same",
        "docs/guide.md": "new",
    }
    assert requests[0][1] == {"recursive": "1"}


@pytest.mark.asyncio
async def test_google_drive_connector_reads_changes_and_deleted_tombstones(monkeypatch) -> None:
    class Response:
        def __init__(self, payload) -> None:  # noqa: ANN001
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self):  # noqa: ANN201
            return self._payload

    class Client:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            pass

        async def __aenter__(self):  # noqa: ANN201
            return self

        async def __aexit__(self, *args) -> None:  # noqa: ANN002
            return None

        async def get(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
            return Response(
                {
                    "newStartPageToken": "token-2",
                    "changes": [
                        {"fileId": "old", "removed": True},
                        {
                            "fileId": "doc",
                            "file": {
                                "id": "doc",
                                "name": "Handbook",
                                "mimeType": "text/plain",
                                "webViewLink": "https://drive/doc",
                                "modifiedTime": "2026-08-24T10:00:00Z",
                            },
                        },
                    ],
                }
            )

    monkeypatch.setattr("app.connectors.google_drive.httpx.AsyncClient", Client)
    connector = GoogleDriveConnector(config={"access_token": "token"})

    discovered = [item async for item in connector.discover({"start_page_token": "token-1"})]

    assert discovered[0].source_id == "old"
    assert discovered[0].deleted is True
    assert discovered[1].source_id == "doc"
    assert (await connector.checkpoint())["start_page_token"] == "token-2"


def test_postgres_checkpoint_cursor_is_json_safe() -> None:
    updated_at = datetime(2026, 8, 24, 10, 0)

    cursor = _cursor_from_row({"id": uuid4(), "updated_at": updated_at}, "id", "updated_at")

    assert cursor["updated_at"] == "2026-08-24T10:00:00"
    assert cursor["pk_type"] == "UUID"
