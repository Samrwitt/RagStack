"""Connector factory registry."""

from __future__ import annotations

from app.connectors.github import GitHubConnector
from app.connectors.google_drive import GoogleDriveConnector
from app.connectors.postgres import PostgresConnector
from app.connectors.protocol import ConnectorConfigurationError, SourceConnector
from app.connectors.rest_api import RestApiConnector
from app.connectors.website import WebsiteConnector
from app.core.config import get_settings
from app.core.security import decrypt_json
from app.models.enums import SourceType
from app.models.source import SourceConnection


def build_connector(source: SourceConnection) -> SourceConnector:
    config = dict(source.config or {})
    if source.credentials_encrypted:
        settings = get_settings()
        config.update(
            decrypt_json(
                source.credentials_encrypted,
                key_material=settings.credential_key_material,
            )
        )
    if source.source_type == SourceType.WEBSITE.value:
        return WebsiteConnector(config=config)
    if source.source_type == SourceType.GITHUB.value:
        return GitHubConnector(config=config)
    if source.source_type == SourceType.POSTGRES.value:
        return PostgresConnector(config=config)
    if source.source_type == SourceType.REST_API.value:
        return RestApiConnector(config=config)
    if source.source_type == SourceType.GOOGLE_DRIVE.value:
        return GoogleDriveConnector(config=config)
    if source.source_type == SourceType.FILE_UPLOAD.value:
        raise ConnectorConfigurationError("file_upload sources do not support connector sync")
    raise ConnectorConfigurationError(f"unsupported source type: {source.source_type}")
