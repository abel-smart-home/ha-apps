#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import sys
from typing import Any

import websocket


WEBSOCKET_URL = "ws://supervisor/core/websocket"


def log(message: str) -> None:
    print(f"[resource] {message}", flush=True)


def fail(message: str) -> int:
    print(f"[resource] ERROR: {message}", file=sys.stderr, flush=True)
    return 1


def receive_json(connection: websocket.WebSocket) -> dict[str, Any]:
    raw_message = connection.recv()
    if isinstance(raw_message, bytes):
        raw_message = raw_message.decode("utf-8")

    message = json.loads(raw_message)

    if not isinstance(message, dict):
        raise ValueError("Home Assistant devolvió una respuesta no válida")

    return message


def wait_for_response(
    connection: websocket.WebSocket,
    request_id: int,
) -> dict[str, Any]:
    while True:
        message = receive_json(connection)

        if message.get("id") == request_id:
            return message


def list_resources(
    connection: websocket.WebSocket,
    request_id: int,
) -> list[dict[str, Any]]:
    connection.send(
        json.dumps(
            {
                "id": request_id,
                "type": "lovelace/resources",
            }
        )
    )

    response = wait_for_response(connection, request_id)
    if not response.get("success"):
        error = response.get("error", {})
        raise RuntimeError(
            error.get("message", "No se pudieron consultar los recursos")
        )

    resources = response.get("result")

    if not isinstance(resources, list):
        raise RuntimeError("La lista de recursos no tiene el formato esperado")

    return [
        resource
        for resource in resources
        if isinstance(resource, dict)
    ]


def matching_resources(
    resources: list[dict[str, Any]],
    base_url: str,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []

    for resource in resources:
        resource_url = str(resource.get("url", ""))
        resource_base_url = resource_url.split("?", maxsplit=1)[0]

        if resource_base_url == base_url:
            matches.append(resource)

    return matches


def main() -> int:
    if len(sys.argv) != 4:
        return fail(
            "Uso: register_resource.py URL URL_BASE TIPO"
        )

    desired_url = sys.argv[1]
    base_url = sys.argv[2]
    desired_type = sys.argv[3]

    supervisor_token = os.environ.get("SUPERVISOR_TOKEN")

    if not supervisor_token:
        return fail("No está disponible SUPERVISOR_TOKEN")

    connection: websocket.WebSocket | None = None
    try:
        connection = websocket.create_connection(
            WEBSOCKET_URL,
            timeout=15,
            suppress_origin=True,
        )

        authentication_required = receive_json(connection)

        if authentication_required.get("type") != "auth_required":
            return fail(
                "Home Assistant no inició el proceso de autenticación"
            )
        connection.send(
            json.dumps(
                {
                    "type": "auth",
                    "access_token": supervisor_token,
                }
            )
        )

        authentication_result = receive_json(connection)

        if authentication_result.get("type") != "auth_ok":
            return fail("Home Assistant rechazó la autenticación")
        request_id = 1
        resources = list_resources(connection, request_id)
        matches = matching_resources(resources, base_url)

        if len(matches) > 1:
            return fail(
                "Existen varios recursos con la misma ruta. "
                "No se realizó ningún cambio."
            )

        if matches:
            existing_resource = matches[0]
            existing_url = str(existing_resource.get("url", ""))
            existing_type = str(
                existing_resource.get(
                    "type",
                    existing_resource.get("res_type", ""),
                )
            )

            if (
                existing_url == desired_url
                and existing_type == desired_type
            ):
                log(f"El recurso ya está registrado: {desired_url}")
                return 0
            resource_id = existing_resource.get("id")

            if not resource_id:
                return fail(
                    "El recurso existente no tiene un identificador"
                )

            request_id += 1

            request = {
                "id": request_id,
                "type": "lovelace/resources/update",
                "resource_id": resource_id,
                "url": desired_url,
                "res_type": desired_type,
            }
            action = "actualizado"

        else:
            request_id += 1

            request = {
                "id": request_id,
                "type": "lovelace/resources/create",
                "url": desired_url,
                "res_type": desired_type,
            }

            action = "creado"

        connection.send(json.dumps(request))
        result = wait_for_response(connection, request_id)

        if not result.get("success"):
            error = result.get("error", {})
            return fail(
                error.get(
                    "message",
                    f"No se pudo guardar el recurso",
                )
            )

        # Verificar que el recurso quedó registrado.
        request_id += 1
        updated_resources = list_resources(connection, request_id)
        verified = any(
            str(resource.get("url", "")) == desired_url
            and str(
                resource.get(
                    "type",
                    resource.get("res_type", ""),
                )
            )
            == desired_type
            for resource in updated_resources
        )

        if not verified:
            return fail(
                "Home Assistant aceptó el cambio, "
                "pero no pudo verificarse"
            )
        log(f"Recurso {action} correctamente: {desired_url}")
        return 0

    except (
        OSError,
        RuntimeError,
        ValueError,
        json.JSONDecodeError,
        websocket.WebSocketException,
    ) as error:
        return fail(str(error))

    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
