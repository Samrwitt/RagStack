"""Metrics endpoint."""

from fastapi import APIRouter, Response

from app.observability.metrics import render_prometheus

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("")
def metrics() -> Response:
    body = render_prometheus()
    return Response(content=body, media_type="text/plain; version=0.0.4")
