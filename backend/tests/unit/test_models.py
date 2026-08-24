from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


def test_declarative_base_is_usable() -> None:
    assert Base.metadata is not None


def test_mixins_expose_expected_columns() -> None:
    assert "id" in UUIDPrimaryKeyMixin.__annotations__
    assert "created_at" in TimestampMixin.__annotations__
    assert "updated_at" in TimestampMixin.__annotations__
