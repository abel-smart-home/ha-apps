#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from checksum_utils import (
    calculate_file_sha256,
    calculate_tree_sha256,
)


OPTIONS_FILE = Path("/data/options.json")
CONFIG_ROOT = Path("/config")
REPORT_DIR = Path("/config/ui-manager/checksum-candidates")
MAX_HISTORICAL_REPORTS = 20


class InventoryError(Exception):
    """Error de validación del inventario local."""


def read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass

    return {}


def read_option(options: dict[str, Any], key: str) -> str:
    value = options.get(key, "")

    if isinstance(value, str):
        return value.strip()

    return str(value).strip()


def normalize_inventory_type(value: str) -> str:
    normalized = value.strip().lower()

    frontend_values = {
        "frontend",
        "tarjeta",
        "archivo",
        "file",
    }

    integration_values = {
        "integration",
        "integracion",
        "integración",
        "carpeta",
        "tree",
    }

    if normalized in frontend_values:
        return "frontend"

    if normalized in integration_values:
        return "integration"

    raise InventoryError(
        "local_inventory_type debe ser frontend o integration"
    )


def resolve_config_path(raw_path: str) -> Path:
    if not raw_path:
        raise InventoryError(
            "local_inventory_path está vacío"
        )

    candidate = Path(raw_path)

    if not candidate.is_absolute():
        candidate = CONFIG_ROOT / raw_path.lstrip("/")

    try:
        resolved_candidate = candidate.resolve(strict=True)
        resolved_config_root = CONFIG_ROOT.resolve(strict=True)
    except OSError as error:
        raise InventoryError(
            f"No se pudo abrir la ruta indicada: {error}"
        ) from error

    if (
        resolved_candidate != resolved_config_root
        and resolved_config_root not in resolved_candidate.parents
    ):
        raise InventoryError(
            "La ruta debe permanecer dentro de /config"
        )

    return resolved_candidate


def prune_reports() -> tuple[int, list[str]]:
    reports = sorted(
        (
            path
            for path in REPORT_DIR.glob("inventory-*.txt")
            if path.is_file()
        ),
        key=lambda path: path.name,
        reverse=True,
    )

    reports_to_delete = reports[MAX_HISTORICAL_REPORTS:]
    deleted_count = 0
    errors: list[str] = []

    for report_path in reports_to_delete:
        try:
            report_path.unlink()
            deleted_count += 1
        except OSError as error:
            errors.append(
                f"No se pudo eliminar {report_path.name}: {error}"
            )

    return deleted_count, errors


def write_report(lines: list[str]) -> tuple[Path, Path, int, list[str]]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now().astimezone()
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    report_content = "\n".join(lines) + "\n"

    timestamped_report = REPORT_DIR / f"inventory-{timestamp}.txt"
    latest_report = REPORT_DIR / "latest.txt"

    timestamped_report.write_text(
        report_content,
        encoding="utf-8",
    )

    latest_report.write_text(
        report_content,
        encoding="utf-8",
    )

    deleted_count, cleanup_errors = prune_reports()

    return (
        timestamped_report,
        latest_report,
        deleted_count,
        cleanup_errors,
    )


def inventory_frontend(
    path: Path,
    configured_name: str,
    configured_version: str,
) -> dict[str, str]:
    if not path.is_file():
        raise InventoryError(
            "Para frontend, local_inventory_path debe apuntar a un archivo"
        )

    checksum = calculate_file_sha256(path)

    if not checksum:
        raise InventoryError(
            "No se pudo calcular el SHA-256 del archivo"
        )

    return {
        "result": "CORRECTO",
        "name": configured_name or path.stem,
        "type": "frontend",
        "version_configured": configured_version or "no indicada",
        "version_detected": "no disponible en el archivo",
        "domain": "no aplica",
        "checksum_type": "archivo",
        "checksum": checksum,
        "size": str(path.stat().st_size),
        "detail": (
            "El archivo fue leído en modo de solo lectura. "
            "No se instaló ni modificó ningún componente."
        ),
    }


def inventory_integration(
    path: Path,
    configured_name: str,
    configured_version: str,
) -> dict[str, str]:
    if not path.is_dir():
        raise InventoryError(
            "Para integration, local_inventory_path debe apuntar a una carpeta"
        )

    manifest_path = path / "manifest.json"

    if not manifest_path.is_file():
        raise InventoryError(
            "La carpeta indicada no contiene manifest.json"
        )

    manifest = read_json(manifest_path)

    if not manifest:
        raise InventoryError(
            "No se pudo leer manifest.json"
        )

    checksum = calculate_tree_sha256(path)

    if not checksum:
        raise InventoryError(
            "No se pudo calcular el SHA-256 del árbol de archivos"
        )

    detected_version = manifest.get("version", "")
    detected_name = manifest.get("name", "")
    detected_domain = manifest.get("domain", "")

    if not isinstance(detected_version, str):
        detected_version = ""

    if not isinstance(detected_name, str):
        detected_name = ""

    if not isinstance(detected_domain, str):
        detected_domain = ""

    result = "CORRECTO"
    detail_parts = [
        "La carpeta fue leída en modo de solo lectura.",
        "No se instaló ni modificó ningún componente.",
    ]

    if (
        configured_version
        and detected_version
        and configured_version != detected_version
    ):
        result = "REVISAR"
        detail_parts.append(
            "La versión indicada no coincide con manifest.json."
        )

    return {
        "result": result,
        "name": (
            configured_name
            or detected_name
            or detected_domain
            or path.name
        ),
        "type": "integration",
        "version_configured": configured_version or "no indicada",
        "version_detected": detected_version or "no indicada",
        "domain": detected_domain or path.name,
        "checksum_type": "árbol de archivos",
        "checksum": checksum,
        "size": "no aplica",
        "detail": " ".join(detail_parts),
    }


def main() -> int:
    options = read_json(OPTIONS_FILE)

    inventory_type = normalize_inventory_type(
        read_option(options, "local_inventory_type")
    )

    configured_name = read_option(
        options,
        "local_inventory_name",
    )

    configured_version = read_option(
        options,
        "local_inventory_version",
    )

    raw_path = read_option(
        options,
        "local_inventory_path",
    )

    try:
        target_path = resolve_config_path(raw_path)

        if inventory_type == "frontend":
            result = inventory_frontend(
                target_path,
                configured_name,
                configured_version,
            )
        else:
            result = inventory_integration(
                target_path,
                configured_name,
                configured_version,
            )

        now = datetime.now().astimezone()
        formatted_date = now.strftime("%Y-%m-%d %H:%M:%S %z")

        lines = [
            "SMART HOME UI MANAGER",
            "INVENTARIO LOCAL SHA-256",
            "=" * 68,
            f"Fecha: {formatted_date}",
            f"Resultado: {result['result']}",
            "Modo: SOLO LECTURA",
            "",
            "COMPONENTE",
            "-" * 68,
            f"Nombre: {result['name']}",
            f"Tipo: {result['type']}",
            f"Ruta: {target_path}",
            (
                "Versión indicada: "
                f"{result['version_configured']}"
            ),
            (
                "Versión detectada: "
                f"{result['version_detected']}"
            ),
            f"Dominio: {result['domain']}",
            f"Tipo de huella: {result['checksum_type']}",
            f"SHA-256: {result['checksum']}",
            f"Tamaño en bytes: {result['size']}",
            f"Detalle: {result['detail']}",
            "",
            "USO RECOMENDADO",
            "-" * 68,
            (
                "Compara esta huella con la obtenida en una segunda "
                "instalación de laboratorio que use la misma versión."
            ),
            (
                "Solo después de confirmar ambas huellas debe fijarse "
                "como valor aprobado en la app de mantenimiento."
            ),
        ]

        (
            timestamped_report,
            latest_report,
            deleted_count,
            cleanup_errors,
        ) = write_report(lines)

    except (InventoryError, OSError) as error:
        print(
            f"[inventory] ERROR: {error}",
            file=sys.stderr,
            flush=True,
        )
        return 1

    print(
        f"[inventory] Nombre: {result['name']}",
        flush=True,
    )

    print(
        f"[inventory] Tipo: {result['type']}",
        flush=True,
    )

    print(
        f"[inventory] Ruta: {target_path}",
        flush=True,
    )

    print(
        f"[inventory] SHA-256: {result['checksum']}",
        flush=True,
    )

    print(
        f"[inventory] Reporte guardado: {timestamped_report}",
        flush=True,
    )

    print(
        f"[inventory] Último inventario: {latest_report}",
        flush=True,
    )

    print(
        "[inventory] Reportes históricos conservados: "
        f"{MAX_HISTORICAL_REPORTS}",
        flush=True,
    )

    if deleted_count > 0:
        print(
            "[inventory] Reportes históricos eliminados: "
            f"{deleted_count}",
            flush=True,
        )

    for cleanup_error in cleanup_errors:
        print(
            f"[inventory] WARNING: {cleanup_error}",
            file=sys.stderr,
            flush=True,
        )

    return 0 if result["result"] == "CORRECTO" else 3


if __name__ == "__main__":
    raise SystemExit(main())
