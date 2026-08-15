"""FastAPI application for the internal core service."""

from __future__ import annotations

import asyncio
import secrets
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Literal

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.responses import Response

from hushmark_core import __version__
from hushmark_core.api.schemas import (
    AnalyzeItem,
    AnalyzeRequest,
    AnalyzeResponse,
    AvailableModel,
    EntitySpan,
    HealthResponse,
    MappingRecord,
    MaskItem,
    MaskRequest,
    MaskResponse,
    MetadataResponse,
)
from hushmark_core.config import get_settings
from hushmark_core.engine import get_engine
from hushmark_core.logging import configure_logging, log_event
from hushmark_core.masking import PlaceholderCollision, mask_text
from hushmark_core.ner.registry import list_available_models
from hushmark_core.taxonomy_gen import TAXONOMY_VERSION

CoreOutcome = Literal["ok", "error", "auth_failed", "body_too_large", "capacity_exceeded"]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    app.state.inference_semaphore = asyncio.Semaphore(settings.max_concurrency)
    get_engine()
    log_event({"event": "service_started", "status": 200})
    yield


app = FastAPI(
    title="hushmark core",
    version=__version__,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, __: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error": {"code": "HM-4001", "message": "malformed request"}},
    )


@app.exception_handler(PlaceholderCollision)
async def collision_error_handler(_: Request, __: PlaceholderCollision) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "HM-4102", "message": "placeholder collision in input"}},
    )


@app.middleware("http")
async def request_event_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    start = time.perf_counter()
    settings = get_settings()
    semaphore_acquired = False
    response: Response | None = None
    outcome: CoreOutcome = "ok"
    try:
        if request.url.path.startswith("/v1/"):
            if settings.service_token is not None:
                expected = f"Bearer {settings.service_token.get_secret_value()}".encode()
                supplied = request.headers.get("authorization", "").encode("latin-1")
                if not secrets.compare_digest(supplied, expected):
                    outcome = "auth_failed"
                    response = JSONResponse(
                        status_code=401,
                        content={
                            "error": {"code": "HM-4010", "message": "invalid core credential"}
                        },
                    )
                    return response
            content_length = request.headers.get("content-length")
            if content_length is not None and _content_length_exceeds(
                content_length, settings.body_limit_bytes
            ):
                outcome = "body_too_large"
                response = JSONResponse(
                    status_code=413,
                    content={"error": {"code": "HM-4001", "message": "request body too large"}},
                )
                return response
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > settings.body_limit_bytes:
                    outcome = "body_too_large"
                    response = JSONResponse(
                        status_code=413,
                        content={"error": {"code": "HM-4001", "message": "request body too large"}},
                    )
                    return response
                body.extend(chunk)
            request._body = bytes(body)
            try:
                await asyncio.wait_for(
                    request.app.state.inference_semaphore.acquire(),
                    timeout=settings.queue_timeout_ms / 1_000,
                )
                semaphore_acquired = True
            except TimeoutError:
                outcome = "capacity_exceeded"
                response = JSONResponse(
                    status_code=429,
                    content={"error": {"code": "HM-4290", "message": "core capacity exceeded"}},
                )
                return response
        response = await call_next(request)
        if response.status_code >= 400:
            outcome = "error"
        return response
    finally:
        if semaphore_acquired:
            request.app.state.inference_semaphore.release()
        log_event(
            {
                "event": "request_complete",
                "route": request.url.path,
                "method": request.method,
                "status": response.status_code if response is not None else 500,
                "duration_ms": round((time.perf_counter() - start) * 1000, 3),
                "outcome": outcome if response is not None else "error",
            }
        )


def _content_length_exceeds(value: str, limit: int) -> bool:
    try:
        return int(value) > limit
    except ValueError:
        return True


@app.post("/v1/analyze", response_model=AnalyzeResponse)
async def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    engine = get_engine()
    items = [
        AnalyzeItem(
            id=item.id,
            entities=[
                EntitySpan(
                    type=entity.type,
                    start=entity.start,
                    end=entity.end,
                    confidence=entity.confidence,
                    layer=entity.layer,
                )
                for entity in engine.analyze(item.text, payload.language)
            ],
        )
        for item in payload.items
    ]
    return AnalyzeResponse(
        items=items,
        model_id=engine.model_id,
        taxonomy_version=str(TAXONOMY_VERSION),
    )


@app.post("/v1/mask", response_model=MaskResponse, response_model_exclude_none=True)
async def mask(payload: MaskRequest) -> MaskResponse:
    engine = get_engine()
    session = payload.session or secrets.token_hex(16)
    items: list[MaskItem] = []
    for item in payload.items:
        result = mask_text(
            item.text,
            engine.analyze(item.text, payload.language),
            session=session,
            collision_mode=payload.collision_mode,
        )
        items.append(
            MaskItem(
                id=item.id,
                masked_text=result.masked_text,
                mappings=[
                    MappingRecord(
                        placeholder=mapping.placeholder,
                        type=mapping.type,
                        start=mapping.start,
                        end=mapping.end,
                        value=mapping.value if payload.include_values else None,
                        confidence=mapping.confidence,
                        layer=mapping.layer,
                    )
                    for mapping in result.mappings
                ],
            )
        )
    return MaskResponse(
        items=items,
        model_id=engine.model_id,
        taxonomy_version=str(TAXONOMY_VERSION),
    )


@lru_cache(maxsize=4)
def available_models_payload(registry_path: str) -> tuple[AvailableModel, ...]:
    return tuple(
        AvailableModel(
            id=model.id,
            architecture=model.architecture,
            backends=list(model.backends),
        )
        for model in list_available_models(Path(registry_path))
    )


@app.get("/v1/metadata", response_model=MetadataResponse)
async def metadata() -> MetadataResponse:
    engine = get_engine()
    return MetadataResponse(
        version=__version__,
        model_id=engine.model_id,
        model_sha256=engine.model_sha256,
        taxonomy_version=str(TAXONOMY_VERSION),
        backends=["torch", "onnx"],
        available_models=list(available_models_payload(str(get_settings().model_registry))),
    )


@app.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/readyz", response_model=HealthResponse)
async def readyz() -> HealthResponse | JSONResponse:
    if not get_engine().ready:
        return JSONResponse(status_code=503, content={"status": "loading"})
    return HealthResponse(status="ready")


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "hushmark_core.api:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )
