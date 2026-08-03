#!/usr/bin/env python3

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from packaging.version import InvalidVersion, Version


HOME_ASSISTANT_CONFIG_URL = os.environ.get(
    "UI_MANAGER_HA_CONFIG_URL",
    "http://supervisor/core/api/config",
)
HOME_ASSISTANT_VERSION_OVERRIDE = os.environ.get(
    "UI_MANAGER_HA_VERSION_OVERRIDE",
    "",
).strip()


class CompatibilityError(RuntimeError):
    pass


def parse_version(value: str) -> Version:
    text = value.strip()
    if not text:
        raise CompatibilityError("La versión está vacía")

    try:
        return Version(text)
    except InvalidVersion as error:
        raise CompatibilityError(f"Versión no válida: {text}") from error


def is_version_at_least(current: str, minimum: str) -> bool:
    return parse_version(current) >= parse_version(minimum)


def compatibility_status(current: str, minimum: str) -> str:
    if not minimum.strip():
        return "NO REQUERIDA"
    if not current.strip():
        return "NO VERIFICADA"
    return "COMPATIBLE" if is_version_at_least(current, minimum) else "INCOMPATIBLE"


def _extract_version(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise CompatibilityError("La API de Home Assistant no devolvió un objeto JSON")

    version = payload.get("version")
    if not isinstance(version, str) or not version.strip():
        raise CompatibilityError(
            "La API de Home Assistant no devolvió una versión utilizable"
        )

    normalized = version.strip()
    parse_version(normalized)
    return normalized


def fetch_home_assistant_version(timeout: int = 15) -> str:
    if HOME_ASSISTANT_VERSION_OVERRIDE:
        parse_version(HOME_ASSISTANT_VERSION_OVERRIDE)
        return HOME_ASSISTANT_VERSION_OVERRIDE

    token = os.environ.get("SUPERVISOR_TOKEN", "").strip()
    if not token:
        raise CompatibilityError("SUPERVISOR_TOKEN no está disponible")

    request = Request(
        HOME_ASSISTANT_CONFIG_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Smart-Home-UI-Manager/0.6.0",
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            raw_data = response.read()
    except HTTPError as error:
        raise CompatibilityError(
            f"Home Assistant respondió HTTP {error.code}"
        ) from error
    except URLError as error:
        raise CompatibilityError(
            f"No se pudo consultar Home Assistant: {error.reason}"
        ) from error
    except OSError as error:
        raise CompatibilityError(
            f"No se pudo consultar Home Assistant: {error}"
        ) from error

    try:
        payload = json.loads(raw_data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CompatibilityError(
            "Home Assistant devolvió una respuesta JSON no válida"
        ) from error

    return _extract_version(payload)
