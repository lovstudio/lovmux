#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from typing import Any


DEFAULT_MODELS_URL = "https://zenmux.ai/api/anthropic/v1/models?limit=1000"
DEFAULT_GATEWAY_BASE_URL = "https://zenmux.ai/api/anthropic"
DEFAULT_API_KEY_PLACEHOLDER = "PASTE_YOUR_ZENMUX_API_KEY_HERE"
DEFAULT_MODEL_HINT = "claude-sonnet-4.6"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Claude App third-party inference JSON for Zenmux.",
    )
    parser.add_argument("--models-url", default=DEFAULT_MODELS_URL)
    parser.add_argument("--gateway-base-url", default=DEFAULT_GATEWAY_BASE_URL)
    parser.add_argument("--api-key-placeholder", default=DEFAULT_API_KEY_PLACEHOLDER)
    parser.add_argument("--fetch-api-key", default="", help="Optional API key used only when fetching /v1/models.")
    parser.add_argument("--default-model", default=DEFAULT_MODEL_HINT)
    parser.add_argument("--max-models", type=int, default=0)
    parser.add_argument("--format", choices=("config", "models"), default="config")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--output", default="-")
    args = parser.parse_args()

    payload = fetch_json(args.models_url, args.fetch_api_key)
    models = build_inference_models(payload, args.default_model, args.max_models)

    if args.format == "models":
        output: Any = models
    else:
        output = {
            "inferenceProvider": "gateway",
            "inferenceCredentialKind": "static",
            "inferenceGatewayBaseUrl": args.gateway_base_url,
            "inferenceGatewayApiKey": args.api_key_placeholder,
            "inferenceGatewayAuthScheme": "bearer",
            "modelDiscoveryEnabled": False,
            "inferenceModels": models,
        }

    text = json.dumps(
        output,
        ensure_ascii=False,
        separators=(",", ":") if args.compact else None,
        indent=None if args.compact else 2,
    )
    write_output(args.output, f"{text}\n")
    print(f"Generated {len(models)} model entries.", file=sys.stderr)
    return 0


def fetch_json(url: str, api_key: str) -> Any:
    headers = {"accept": "application/json"}
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"
        headers["x-api-key"] = api_key

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def build_inference_models(payload: Any, default_model_hint: str, max_models: int) -> list[dict[str, str]]:
    entries = find_model_entries(payload)
    unique: dict[str, tuple[int, dict[str, str]]] = {}

    for index, entry in enumerate(entries):
        model_id = model_id_from_entry(entry)
        if not model_id:
            continue

        unique.setdefault(
            model_id,
            (
                index,
                {
                    "name": model_id,
                    "labelOverride": display_name_from_entry(entry, model_id),
                },
            ),
        )

    indexed_models = list(unique.values())
    indexed_models.sort(key=lambda item: (*model_priority(item[1], default_model_hint), item[0]))
    models = [model for _index, model in indexed_models]

    if max_models > 0:
        return models[:max_models]
    return models


def find_model_entries(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if not isinstance(payload, dict):
        return []

    data = payload.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and isinstance(data.get("models"), list):
        return [item for item in data["models"] if isinstance(item, dict)]
    if isinstance(payload.get("models"), list):
        return [item for item in payload["models"] if isinstance(item, dict)]
    return []


def model_id_from_entry(entry: dict[str, Any]) -> str:
    for key in ("id", "slug", "model", "model_name", "modelName", "model_id", "modelId"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def display_name_from_entry(entry: dict[str, Any], model_id: str) -> str:
    for key in ("display_name", "displayName", "name", "label"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return model_id


def model_priority(model: dict[str, str], default_model_hint: str) -> tuple[int]:
    name = model["name"].lower()
    label = model.get("labelOverride", "").lower()
    haystack = f"{name} {label}"
    hint = default_model_hint.strip().lower()

    if hint and hint in haystack:
        return (0,)
    if "claude-sonnet" in haystack:
        return (1,)
    if "anthropic/claude" in haystack or name.startswith("claude-"):
        return (2,)
    return (10,)


def write_output(path: str, text: str) -> None:
    if path == "-":
        print(text, end="")
        return

    with open(path, "w", encoding="utf-8") as file:
        file.write(text)


if __name__ == "__main__":
    raise SystemExit(main())
