from uuid import uuid4

import pytest

from app.connectors.base import metadata_with_connector, permissions_from_config
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
