#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import platform
from dataclasses import asdict, dataclass


UNKNOWN_VALUES = {"", "unknown", "development", "none", "null"}


@dataclass(frozen=True)
class BuildMetadata:
    version: str
    architecture: str
    revision: str
    created: str
    source: str
    image: str
    prebuilt: bool

    @property
    def short_revision(self) -> str:
        if self.revision.lower() in UNKNOWN_VALUES:
            return self.revision
        return self.revision[:12]

    @property
    def complete(self) -> bool:
        required = (
            self.version,
            self.architecture,
            self.revision,
            self.created,
            self.source,
            self.image,
        )
        return self.prebuilt and all(
            value.strip().lower() not in UNKNOWN_VALUES
            for value in required
        )


def _env(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


def get_build_metadata() -> BuildMetadata:
    architecture = _env(
        "UI_MANAGER_BUILD_ARCH",
        platform.machine() or "unknown",
    )
    prebuilt_text = _env("UI_MANAGER_PREBUILT", "false").lower()

    return BuildMetadata(
        version=_env("UI_MANAGER_APP_VERSION", "development"),
        architecture=architecture,
        revision=_env("UI_MANAGER_BUILD_REVISION", "unknown"),
        created=_env("UI_MANAGER_BUILD_DATE", "unknown"),
        source=_env(
            "UI_MANAGER_BUILD_SOURCE",
            "https://github.com/abel-smart-home/ha-apps",
        ),
        image=_env(
            "UI_MANAGER_IMAGE",
            "ghcr.io/abel-smart-home/smart-home-ui-manager:development",
        ),
        prebuilt=prebuilt_text == "true",
    )


def metadata_lines(metadata: BuildMetadata | None = None) -> list[str]:
    item = metadata or get_build_metadata()
    return [
        f"Versión de la app: {item.version}",
        f"Arquitectura de imagen: {item.architecture}",
        f"Commit de compilación: {item.short_revision}",
        f"Fecha de compilación: {item.created}",
        f"Repositorio de origen: {item.source}",
        f"Imagen ejecutada: {item.image}",
        f"Imagen precompilada: {'SÍ' if item.prebuilt else 'NO'}",
        f"Metadatos completos: {'SÍ' if item.complete else 'NO'}",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Muestra la trazabilidad de la imagen de Smart Home UI Manager"
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--log", action="store_true")
    args = parser.parse_args()

    metadata = get_build_metadata()

    if args.json:
        payload = asdict(metadata)
        payload["short_revision"] = metadata.short_revision
        payload["complete"] = metadata.complete
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    prefix = "[build] " if args.log else ""
    for line in metadata_lines(metadata):
        print(f"{prefix}{line}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
