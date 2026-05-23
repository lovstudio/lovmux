from __future__ import annotations

import base64
import json
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from urllib.parse import parse_qsl, urlencode

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask


UPSTREAM_BASE_URL = os.getenv(
    "ZENMUX_PROXY_UPSTREAM_BASE_URL",
    "https://zenmux.ai/api/anthropic",
).rstrip("/")
UPSTREAM_API_KEY = os.getenv("ZENMUX_PROXY_UPSTREAM_API_KEY", "").strip()
ROUTE_PREFIX = os.getenv("ZENMUX_PROXY_ROUTE_PREFIX", "anthropic/claude-route-")
LEGACY_SYNTHETIC_PREFIX = os.getenv("ZENMUX_PROXY_SYNTHETIC_PREFIX", "anthropic/")
DEFAULT_MODEL_HINT = os.getenv("ZENMUX_PROXY_DEFAULT_MODEL", "claude-sonnet-4.6").strip().lower()
TRUST_ENV_PROXY = os.getenv("ZENMUX_PROXY_TRUST_ENV", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
LOCAL_MODEL_SEARCH_PARAMS = {"q", "query", "search"}

HOP_BY_HOP_REQUEST_HEADERS = {
    "connection",
    "content-length",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}
HOP_BY_HOP_RESPONSE_HEADERS = {
    "connection",
    "content-encoding",
    "content-length",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}

SYNTHETIC_TO_ORIGINAL_MODEL: dict[str, str] = {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    timeout = httpx.Timeout(connect=10.0, read=None, write=60.0, pool=60.0)
    app.state.client = httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=False,
        trust_env=TRUST_ENV_PROXY,
    )
    try:
        yield
    finally:
        await app.state.client.aclose()


app = FastAPI(
    title="Lovmux",
    description="Zenmux Anthropic-compatible proxy for Claude third-party inference.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok", "service": "lovmux", "upstream": UPSTREAM_BASE_URL}


@app.head("/")
async def root_head() -> Response:
    return Response(status_code=200)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "upstream": UPSTREAM_BASE_URL}


@app.get("/v1/models")
async def list_models(request: Request) -> Response:
    client: httpx.AsyncClient = request.app.state.client
    try:
        upstream_response = await client.get(
            upstream_url(request.url.path, upstream_model_list_query(request.url.query)),
            headers=upstream_request_headers(request),
        )
    except httpx.HTTPError as exc:
        return upstream_error_response(exc)

    content_type = upstream_response.headers.get("content-type", "")
    if upstream_response.status_code >= 400 or "application/json" not in content_type:
        return Response(
            content=upstream_response.content,
            status_code=upstream_response.status_code,
            headers=response_headers(upstream_response.headers),
            media_type=content_type or None,
        )

    payload = upstream_response.json()
    rewritten_payload = rewrite_models_payload(payload)
    sort_models_payload(rewritten_payload)
    search_query = local_model_search_query(request)
    if search_query:
        rewritten_payload = filter_models_payload(rewritten_payload, search_query)
    return JSONResponse(
        content=rewritten_payload,
        status_code=upstream_response.status_code,
        headers=response_headers(upstream_response.headers),
    )


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def proxy(path: str, request: Request) -> Response:
    client: httpx.AsyncClient = request.app.state.client
    body = await rewritten_request_body(request)
    upstream_request = client.build_request(
        request.method,
        upstream_url(request.url.path, request.url.query),
        headers=upstream_request_headers(request),
        content=body,
    )
    try:
        upstream_response = await client.send(upstream_request, stream=True)
    except httpx.HTTPError as exc:
        return upstream_error_response(exc)

    return StreamingResponse(
        upstream_response.aiter_raw(),
        status_code=upstream_response.status_code,
        headers=response_headers(upstream_response.headers),
        media_type=upstream_response.headers.get("content-type"),
        background=BackgroundTask(upstream_response.aclose),
    )


def upstream_url(path: str, query: str | None = None) -> str:
    query_suffix = f"?{query}" if query else ""
    return f"{UPSTREAM_BASE_URL}{path}{query_suffix}"


def upstream_model_list_query(query: str | None) -> str:
    if not query:
        return ""

    params = [
        (key, value)
        for key, value in parse_qsl(query, keep_blank_values=True)
        if key.lower() not in LOCAL_MODEL_SEARCH_PARAMS
    ]
    return urlencode(params, doseq=True)


def local_model_search_query(request: Request) -> str:
    for key in LOCAL_MODEL_SEARCH_PARAMS:
        value = request.query_params.get(key)
        if value and value.strip():
            return value.strip()
    return ""


def upstream_request_headers(request: Request) -> dict[str, str]:
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in HOP_BY_HOP_REQUEST_HEADERS
    }
    if UPSTREAM_API_KEY:
        headers["x-api-key"] = UPSTREAM_API_KEY
        headers["authorization"] = f"Bearer {UPSTREAM_API_KEY}"
    return headers


def response_headers(headers: httpx.Headers) -> dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in HOP_BY_HOP_RESPONSE_HEADERS
    }


def upstream_error_response(exc: httpx.HTTPError) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={
            "error": {
                "type": exc.__class__.__name__,
                "message": str(exc) or "Failed to reach Zenmux upstream",
                "upstream": UPSTREAM_BASE_URL,
            }
        },
    )


async def rewritten_request_body(request: Request) -> bytes:
    body = await request.body()
    if not body:
        return body

    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type:
        return body

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return body

    changed = restore_top_level_model(payload)
    if not changed:
        return body

    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def restore_top_level_model(value: Any) -> bool:
    if not isinstance(value, dict):
        return False

    model = value.get("model")
    if not isinstance(model, str):
        return False

    restored = restore_model_id(model)
    if restored == model:
        return False

    value["model"] = restored
    return True


def rewrite_models_payload(payload: Any) -> Any:
    model_entries = find_model_entries(payload)
    for model in model_entries:
        original_id = model_id_from_entry(model)
        if not original_id:
            continue
        synthetic_id = expose_model_id(original_id)
        model["id"] = synthetic_id
        SYNTHETIC_TO_ORIGINAL_MODEL[synthetic_id] = original_id
    return payload


def sort_models_payload(payload: Any) -> None:
    model_entries = find_model_entries(payload)
    if not model_entries:
        return

    indexed = list(enumerate(model_entries))
    indexed.sort(key=lambda item: (model_priority(item[1]), item[0]))
    sorted_entries = [model for _, model in indexed]

    if isinstance(payload, list):
        payload[:] = sorted_entries
        return

    if not isinstance(payload, dict):
        return

    data = payload.get("data")
    if isinstance(data, list):
        payload["data"] = sorted_entries
    elif isinstance(data, dict) and isinstance(data.get("models"), list):
        data["models"] = sorted_entries
    elif isinstance(payload.get("models"), list):
        payload["models"] = sorted_entries


def model_priority(model: dict[str, Any]) -> int:
    original_id = restore_model_id(model.get("id", "")) if isinstance(model.get("id"), str) else ""
    searchable = " ".join(searchable_model_values(model)).lower()

    if DEFAULT_MODEL_HINT and DEFAULT_MODEL_HINT in original_id.lower():
        return 0
    if "claude-sonnet" in searchable:
        return 1
    if "anthropic/claude" in searchable or original_id.lower().startswith("claude-"):
        return 2
    return 10


def filter_models_payload(payload: Any, query: str) -> Any:
    filtered_entries = [
        model
        for model in find_model_entries(payload)
        if model_matches_search(model, query)
    ]

    if isinstance(payload, list):
        return filtered_entries

    if not isinstance(payload, dict):
        return payload

    data = payload.get("data")
    if isinstance(data, list):
        payload["data"] = filtered_entries
        return payload
    if isinstance(data, dict) and isinstance(data.get("models"), list):
        data["models"] = filtered_entries
        return payload
    if isinstance(payload.get("models"), list):
        payload["models"] = filtered_entries
        return payload

    return payload


def model_matches_search(model: dict[str, Any], query: str) -> bool:
    haystack = " ".join(searchable_model_values(model)).lower()
    return all(token in haystack for token in query.lower().split())


def searchable_model_values(model: dict[str, Any]) -> list[str]:
    values: list[str] = []

    for _key, value in model.items():
        if isinstance(value, str):
            values.append(value)

    synthetic_id = model.get("id")
    if isinstance(synthetic_id, str):
        original_id = restore_model_id(synthetic_id)
        values.append(original_id)
        values.extend(original_id.replace("/", " ").replace("-", " ").replace("_", " ").split())

    return values


def find_model_entries(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if not isinstance(payload, dict):
        return []

    data = payload.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        models = data.get("models")
        if isinstance(models, list):
            return [item for item in models if isinstance(item, dict)]

    models = payload.get("models")
    if isinstance(models, list):
        return [item for item in models if isinstance(item, dict)]

    return []


def model_id_from_entry(model: dict[str, Any]) -> str | None:
    for key in ("id", "slug", "model", "model_name", "modelName", "model_id", "modelId"):
        value = model.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def expose_model_id(model_id: str) -> str:
    lower = model_id.lower()
    if lower.startswith("anthropic/claude-") or lower.startswith("claude-"):
        return model_id
    return f"{ROUTE_PREFIX}{encode_model_id(model_id)}"


def restore_model_id(model_id: str) -> str:
    mapped = SYNTHETIC_TO_ORIGINAL_MODEL.get(model_id)
    if mapped:
        return mapped

    if model_id.startswith(ROUTE_PREFIX):
        encoded = model_id[len(ROUTE_PREFIX) :]
        decoded = decode_model_id(encoded)
        return decoded or model_id

    if not model_id.startswith(LEGACY_SYNTHETIC_PREFIX):
        return model_id

    candidate = model_id[len(LEGACY_SYNTHETIC_PREFIX) :]
    if candidate.lower().startswith("claude"):
        return model_id
    return candidate


def encode_model_id(model_id: str) -> str:
    return base64.urlsafe_b64encode(model_id.encode("utf-8")).decode("ascii").rstrip("=")


def decode_model_id(encoded: str) -> str | None:
    try:
        padding = "=" * (-len(encoded) % 4)
        return base64.urlsafe_b64decode(f"{encoded}{padding}").decode("utf-8")
    except Exception:
        return None
