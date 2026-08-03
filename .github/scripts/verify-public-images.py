#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MANIFEST_ACCEPT = ", ".join(
    (
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    )
)


class VerificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ManifestResponse:
    payload: dict[str, Any]
    digest: str
    content_type: str


class RegistryClient:
    def __init__(self, registry: str = "ghcr.io") -> None:
        self.registry = registry
        self._tokens: dict[str, str] = {}

    def _token(self, repository: str) -> str:
        cached = self._tokens.get(repository)
        if cached:
            return cached

        query = urllib.parse.urlencode(
            {
                "service": self.registry,
                "scope": f"repository:{repository}:pull",
            }
        )
        url = f"https://{self.registry}/token?{query}"
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "smart-home-ui-manager-verifier/0.8.0"},
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.load(response)
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
            raise VerificationError(
                f"No se pudo obtener token público para {repository}: {error}"
            ) from error

        token = data.get("token")
        if not isinstance(token, str) or not token:
            raise VerificationError(
                f"GHCR no devolvió un token válido para {repository}"
            )

        self._tokens[repository] = token
        return token

    def _request(
        self,
        repository: str,
        path: str,
        *,
        accept: str,
        allow_not_found: bool = False,
    ) -> tuple[bytes, dict[str, str]] | None:
        token = self._token(repository)
        url = f"https://{self.registry}/v2/{repository}/{path}"
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": accept,
                "User-Agent": "smart-home-ui-manager-verifier/0.8.0",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                headers = {key.lower(): value for key, value in response.headers.items()}
                return response.read(), headers
        except urllib.error.HTTPError as error:
            if allow_not_found and error.code == 404:
                return None
            raise VerificationError(
                f"GHCR respondió HTTP {error.code} para {repository}/{path}"
            ) from error
        except (OSError, urllib.error.URLError) as error:
            raise VerificationError(
                f"No se pudo consultar {repository}/{path}: {error}"
            ) from error

    def manifest(
        self,
        repository: str,
        reference: str,
        *,
        allow_not_found: bool = False,
    ) -> ManifestResponse | None:
        result = self._request(
            repository,
            f"manifests/{reference}",
            accept=MANIFEST_ACCEPT,
            allow_not_found=allow_not_found,
        )
        if result is None:
            return None

        content, headers = result
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as error:
            raise VerificationError(
                f"Manifest inválido en {repository}:{reference}"
            ) from error

        if not isinstance(payload, dict):
            raise VerificationError(
                f"Manifest inesperado en {repository}:{reference}"
            )

        digest = headers.get("docker-content-digest", "")
        content_type = headers.get("content-type", "").split(";", 1)[0]
        if not digest:
            raise VerificationError(
                f"GHCR no informó el digest de {repository}:{reference}"
            )

        return ManifestResponse(payload, digest, content_type)

    def blob_json(self, repository: str, digest: str) -> dict[str, Any]:
        result = self._request(
            repository,
            f"blobs/{digest}",
            accept="application/octet-stream, application/json",
        )
        if result is None:
            raise VerificationError(f"No se encontró el blob {digest}")
        content, _headers = result
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as error:
            raise VerificationError(
                f"El blob {digest} no contiene JSON válido"
            ) from error
        if not isinstance(payload, dict):
            raise VerificationError(f"El blob {digest} tiene un formato inesperado")
        return payload


def _media_type(payload: dict[str, Any], fallback: str = "") -> str:
    value = payload.get("mediaType", fallback)
    return value if isinstance(value, str) else fallback


def _is_index(payload: dict[str, Any], content_type: str = "") -> bool:
    media_type = _media_type(payload, content_type)
    return media_type in {
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
    } or isinstance(payload.get("manifests"), list)


def _platforms(payload: dict[str, Any]) -> set[tuple[str, str]]:
    result: set[tuple[str, str]] = set()
    manifests = payload.get("manifests", [])
    if not isinstance(manifests, list):
        return result

    for descriptor in manifests:
        if not isinstance(descriptor, dict):
            continue
        platform = descriptor.get("platform", {})
        if not isinstance(platform, dict):
            continue
        os_name = platform.get("os")
        architecture = platform.get("architecture")
        if isinstance(os_name, str) and isinstance(architecture, str):
            result.add((os_name, architecture))
    return result


def _resolve_image_manifest(
    client: RegistryClient,
    repository: str,
    response: ManifestResponse,
    expected_oci_arch: str,
) -> ManifestResponse:
    if not _is_index(response.payload, response.content_type):
        return response

    manifests = response.payload.get("manifests", [])
    if not isinstance(manifests, list):
        raise VerificationError(f"Índice sin manifests en {repository}")

    for descriptor in manifests:
        if not isinstance(descriptor, dict):
            continue
        platform = descriptor.get("platform", {})
        if not isinstance(platform, dict):
            continue
        if (
            platform.get("os") == "linux"
            and platform.get("architecture") == expected_oci_arch
        ):
            digest = descriptor.get("digest")
            if not isinstance(digest, str) or not digest:
                continue
            nested = client.manifest(repository, digest)
            if nested is not None:
                return nested

    raise VerificationError(
        f"No se encontró la imagen linux/{expected_oci_arch} en {repository}"
    )


def _image_config(
    client: RegistryClient,
    repository: str,
    response: ManifestResponse,
    expected_oci_arch: str,
) -> dict[str, Any]:
    image_manifest = _resolve_image_manifest(
        client,
        repository,
        response,
        expected_oci_arch,
    )
    config = image_manifest.payload.get("config")
    if not isinstance(config, dict):
        raise VerificationError(f"Manifest sin configuración en {repository}")
    digest = config.get("digest")
    if not isinstance(digest, str) or not digest:
        raise VerificationError(f"Configuración sin digest en {repository}")
    return client.blob_json(repository, digest)


def _labels(config_blob: dict[str, Any]) -> dict[str, str]:
    config = config_blob.get("config", {})
    if not isinstance(config, dict):
        return {}
    raw_labels = config.get("Labels", {})
    if not isinstance(raw_labels, dict):
        return {}
    return {
        str(key): str(value)
        for key, value in raw_labels.items()
        if value is not None
    }


def _environment(config_blob: dict[str, Any]) -> set[str]:
    config = config_blob.get("config", {})
    if not isinstance(config, dict):
        return set()
    raw_env = config.get("Env", [])
    if not isinstance(raw_env, list):
        return set()
    return {str(item) for item in raw_env}


def _require_equal(actual: str | None, expected: str, description: str) -> None:
    if actual != expected:
        raise VerificationError(
            f"{description}: esperado {expected!r}; obtenido {actual!r}"
        )


def check_absent(owner: str, image: str, version: str) -> dict[str, Any]:
    client = RegistryClient()
    repositories = (
        f"{owner}/{image}",
        f"{owner}/amd64-{image}",
        f"{owner}/aarch64-{image}",
    )
    existing: list[str] = []

    for repository in repositories:
        manifest = client.manifest(repository, version, allow_not_found=True)
        if manifest is not None:
            existing.append(f"ghcr.io/{repository}:{version}")

    if existing:
        joined = "\n  - ".join(existing)
        raise VerificationError(
            "La versión ya está publicada y no debe sobrescribirse:\n"
            f"  - {joined}"
        )

    return {
        "result": "ABSENT",
        "version": version,
        "checked": [f"ghcr.io/{item}:{version}" for item in repositories],
    }


def verify_publication(
    owner: str,
    image: str,
    version: str,
    revision: str,
    source: str,
) -> dict[str, Any]:
    client = RegistryClient()
    generic_repository = f"{owner}/{image}"

    generic_version = client.manifest(generic_repository, version)
    generic_latest = client.manifest(generic_repository, "latest")
    if generic_version is None or generic_latest is None:
        raise VerificationError("No se encontró el manifiesto multi-arquitectura")

    _require_equal(
        generic_latest.digest,
        generic_version.digest,
        "latest no apunta al mismo manifiesto que la versión",
    )

    if not _is_index(generic_version.payload, generic_version.content_type):
        raise VerificationError("La imagen genérica no es multi-arquitectura")

    platforms = _platforms(generic_version.payload)
    required_platforms = {("linux", "amd64"), ("linux", "arm64")}
    missing_platforms = required_platforms - platforms
    if missing_platforms:
        raise VerificationError(
            "Faltan arquitecturas en el manifiesto: "
            + ", ".join(f"{os_name}/{arch}" for os_name, arch in missing_platforms)
        )

    architecture_results: dict[str, Any] = {}
    for hass_arch, oci_arch in (("amd64", "amd64"), ("aarch64", "arm64")):
        repository = f"{owner}/{hass_arch}-{image}"
        version_response = client.manifest(repository, version)
        latest_response = client.manifest(repository, "latest")
        if version_response is None or latest_response is None:
            raise VerificationError(f"No se encontró la imagen {hass_arch}")

        _require_equal(
            latest_response.digest,
            version_response.digest,
            f"latest de {hass_arch} no coincide con la versión",
        )

        config_blob = _image_config(
            client,
            repository,
            version_response,
            oci_arch,
        )
        labels = _labels(config_blob)
        environment = _environment(config_blob)

        expected_labels = {
            "io.hass.arch": hass_arch,
            "io.hass.version": version,
            "io.hass.type": "app",
            "org.opencontainers.image.title": "Smart Home UI Manager",
            "org.opencontainers.image.source": source,
            "org.opencontainers.image.version": version,
            "org.opencontainers.image.revision": revision,
        }
        for key, expected in expected_labels.items():
            _require_equal(labels.get(key), expected, f"Etiqueta {key} en {hass_arch}")

        required_env = {
            f"UI_MANAGER_APP_VERSION={version}",
            f"UI_MANAGER_BUILD_ARCH={hass_arch}",
            f"UI_MANAGER_BUILD_REVISION={revision}",
            f"UI_MANAGER_BUILD_SOURCE={source}",
            f"UI_MANAGER_IMAGE=ghcr.io/{owner}/{image}:{version}",
            "UI_MANAGER_PREBUILT=true",
        }
        missing_env = sorted(required_env - environment)
        if missing_env:
            raise VerificationError(
                f"Metadatos de entorno faltantes en {hass_arch}: "
                + ", ".join(missing_env)
            )

        created = labels.get("org.opencontainers.image.created", "")
        if not created or created in {"unknown", "development"}:
            raise VerificationError(
                f"Fecha OCI ausente o inválida en la imagen {hass_arch}"
            )

        architecture_results[hass_arch] = {
            "repository": f"ghcr.io/{repository}",
            "version_digest": version_response.digest,
            "latest_digest": latest_response.digest,
            "oci_architecture": config_blob.get("architecture", oci_arch),
            "labels_verified": len(expected_labels) + 1,
            "environment_verified": len(required_env),
        }

    return {
        "result": "CORRECTO",
        "version": version,
        "revision": revision,
        "source": source,
        "generic": {
            "repository": f"ghcr.io/{generic_repository}",
            "version_digest": generic_version.digest,
            "latest_digest": generic_latest.digest,
            "platforms": sorted(f"{os_name}/{arch}" for os_name, arch in platforms),
        },
        "architectures": architecture_results,
    }


def write_output(result: dict[str, Any], output: Path | None) -> None:
    content = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(content, flush=True)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verifica publicaciones públicas de Smart Home UI Manager en GHCR"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    absent_parser = subparsers.add_parser(
        "check-absent",
        help="Comprueba que una etiqueta de versión todavía no exista",
    )
    verify_parser = subparsers.add_parser(
        "verify",
        help="Verifica imágenes públicas, manifiesto y metadatos",
    )

    for item in (absent_parser, verify_parser):
        item.add_argument("--owner", required=True)
        item.add_argument("--image", required=True)
        item.add_argument("--version", required=True)
        item.add_argument("--output", type=Path)

    verify_parser.add_argument("--revision", required=True)
    verify_parser.add_argument("--source", required=True)
    verify_parser.add_argument("--retries", type=int, default=12)
    verify_parser.add_argument("--delay", type=int, default=10)

    args = parser.parse_args()

    try:
        if args.command == "check-absent":
            result = check_absent(args.owner, args.image, args.version)
            write_output(result, args.output)
            return 0

        last_error: VerificationError | None = None
        retries = max(args.retries, 1)
        for attempt in range(1, retries + 1):
            try:
                result = verify_publication(
                    args.owner,
                    args.image,
                    args.version,
                    args.revision,
                    args.source,
                )
                result["attempt"] = attempt
                write_output(result, args.output)
                return 0
            except VerificationError as error:
                last_error = error
                if attempt >= retries:
                    break
                print(
                    f"Intento {attempt}/{retries} no disponible todavía: {error}",
                    file=sys.stderr,
                    flush=True,
                )
                time.sleep(max(args.delay, 1))

        raise last_error or VerificationError("Verificación sin resultado")

    except VerificationError as error:
        print(f"ERROR: {error}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
