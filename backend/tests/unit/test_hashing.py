from app.ingestion.hashing import sha256_digest


def test_sha256_is_stable() -> None:
    digest = sha256_digest(b"annual leave is 22 days")
    assert digest == sha256_digest(b"annual leave is 22 days")
    assert len(digest) == 64


def test_sha256_detects_change() -> None:
    assert sha256_digest(b"18 days") != sha256_digest(b"22 days")
