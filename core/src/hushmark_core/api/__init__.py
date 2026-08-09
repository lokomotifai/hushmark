"""FastAPI application for the internal core service."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

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
from hushmark_core.taxonomy_gen import TAXONOMY_VERSION


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    get_engine()
    log_event({"event": "service_started", "status": 200})
    yield


app = FastAPI(
    title="hushmark core",
    version=__version__,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
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
    response = await call_next(request)
    log_event(
        {
            "event": "request_complete",
            "route": request.url.path,
            "method": request.method,
            "status": response.status_code,
            "duration_ms": round((time.perf_counter() - start) * 1000, 3),
        }
    )
    return response


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
    session = payload.session or "request"
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


@app.get("/v1/metadata", response_model=MetadataResponse)
async def metadata() -> MetadataResponse:
    engine = get_engine()
    return MetadataResponse(
        version=__version__,
        model_id=engine.model_id,
        model_sha256=engine.model_sha256,
        taxonomy_version=str(TAXONOMY_VERSION),
        backends=["torch", "onnx"],
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
