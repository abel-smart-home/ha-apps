#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from checksum_utils import calculate_file_sha256, calculate_tree_sha256


OPTIONS_FILE = Path(os.environ.get("UI_MANAGER_OPTIONS_FILE", "/data/options.json"))
CONFIG_ROOT = Path(os.environ.get("UI_MANAGER_CONFIG_ROOT", "/config"))
REPORT_DIR = CONFIG_ROOT / "ui-manager" / "reports"
MAX_HISTORICAL_REPORTS = 20
DEFAULT_CATALOG = Path("/components.json")


def read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}

    return data if isinstance(data, dict) else {}


def read_results(path: Path) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return results

    for line in lines:
        if not line.strip():
            continue

        fields = line.split("\t", 7)
        while len(fields) < 8:
            fields.append("")

        results.append(
            {
                "id": fields[0],
                "name": fields[1],
                "type": fields[2],
                "desired": fields[3],
                "previous": fields[4],
                "final": fields[5],
                "status": fields[6],
                "message": fields[7],
            }
        )

    return results


def load_catalog(path: Path) -> tuple[str, dict[str, dict[str, Any]]]:
    data = read_json(path)
    catalog_version = data.get("catalog_version", "desconocido")
    raw_components = data.get("components", [])

    if not isinstance(catalog_version, str):
        catalog_version = "desconocido"

    components: dict[str, dict[str, Any]] = {}
    if isinstance(raw_components, list):
        for item in raw_components:
            if not isinstance(item, dict):
                continue
            component_id = item.get("id")
            if isinstance(component_id, str) and component_id:
                components[component_id] = item

    return catalog_version, components


def map_config_path(path_text: str) -> Path:
    path = Path(path_text)
    try:
        relative = path.relative_to("/config")
    except ValueError:
        return path
    return CONFIG_ROOT / relative


def checksum_details(
    component: dict[str, Any],
) -> tuple[str, str, str]:
    expected = component.get("sha256", "")
    expected_checksum = expected if isinstance(expected, str) else ""
    component_type = component.get("type")

    if component_type == "frontend":
        install_dir = component.get("install_dir")
        filename = component.get("filename")
        if not isinstance(install_dir, str) or not isinstance(filename, str):
            return "archivo", expected_checksum, ""
        installed_path = map_config_path(install_dir) / filename
        return (
            "archivo",
            expected_checksum,
            calculate_file_sha256(installed_path),
        )

    if component_type == "integration":
        integration_id = component.get("integration_id")
        if not isinstance(integration_id, str):
            return "árbol de archivos", expected_checksum, ""
        installed_path = CONFIG_ROOT / "custom_components" / integration_id
        return (
            "árbol de archivos",
            expected_checksum,
            calculate_tree_sha256(installed_path),
        )

    return "no aplica", expected_checksum, ""


def integrity_status(
    result_status: str,
    expected_checksum: str,
    installed_checksum: str,
) -> str:
    if result_status == "OMITIDO":
        return "NO COMPROBADA"
    if not expected_checksum:
        return "NO APLICA"
    if not installed_checksum:
        return "NO DISPONIBLE"
    if installed_checksum == expected_checksum:
        return "COINCIDE"
    return "NO COINCIDE"


def is_enabled(options: dict[str, Any], option_name: str) -> bool:
    return options.get(option_name, True) is True


def prune_historical_reports() -> tuple[int, list[str]]:
    historical_reports = sorted(
        (
            path
            for path in REPORT_DIR.glob("maintenance-*.txt")
            if path.is_file()
        ),
        key=lambda path: path.name,
        reverse=True,
    )

    reports_to_delete = historical_reports[MAX_HISTORICAL_REPORTS:]
    deleted_count = 0
    errors: list[str] = []

    for report_path in reports_to_delete:
        try:
            report_path.unlink()
            deleted_count += 1
        except OSError as error:
            errors.append(f"No se pudo eliminar {report_path.name}: {error}")

    return deleted_count, errors


def main() -> int:
    restart_required = (
        len(sys.argv) > 1 and sys.argv[1].strip().lower() == "true"
    )
    results_file = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else Path("/tmp/ui_manager_results.tsv")
    )
    catalog_file = Path(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_CATALOG

    options = read_json(OPTIONS_FILE)
    results = read_results(results_file)
    catalog_version, catalog = load_catalog(catalog_file)

    status_counts = Counter(result["status"] for result in results)
    integrity_data: dict[str, tuple[str, str, str, str]] = {}
    integrity_failures = 0

    for result in results:
        component = catalog.get(result["id"], {})
        checksum_type, expected, installed = checksum_details(component)
        status_value = integrity_status(result["status"], expected, installed)
        integrity_data[result["id"]] = (
            checksum_type,
            expected,
            installed,
            status_value,
        )
        if status_value in {"NO COINCIDE", "NO DISPONIBLE"}:
            integrity_failures += 1

    error_count = status_counts.get("ERROR", 0)
    changed_count = sum(
        status_counts.get(status, 0)
        for status in ("INSTALADO", "ACTUALIZADO", "REPARADO")
    )

    if not results or error_count > 0 or integrity_failures > 0:
        overall_result = "REVISAR"
    elif changed_count > 0:
        overall_result = "CAMBIOS APLICADOS"
    else:
        overall_result = "CORRECTO"

    restart_text = "REQUERIDO" if restart_required else "NO REQUERIDO"
    now = datetime.now().astimezone()
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    formatted_date = now.strftime("%Y-%m-%d %H:%M:%S %z")

    lines = [
        "SMART HOME UI MANAGER",
        "REPORTE DE MANTENIMIENTO",
        "=" * 68,
        f"Fecha: {formatted_date}",
        f"Catálogo: {catalog_version}",
        f"Resultado general: {overall_result}",
        f"Reinicio de Home Assistant Core: {restart_text}",
        "",
        "RESUMEN",
        "-" * 68,
        f"Verificados: {status_counts.get('VERIFICADO', 0)}",
        f"Instalados: {status_counts.get('INSTALADO', 0)}",
        f"Actualizados: {status_counts.get('ACTUALIZADO', 0)}",
        f"Reparados: {status_counts.get('REPARADO', 0)}",
        f"Omitidos: {status_counts.get('OMITIDO', 0)}",
        f"Errores: {status_counts.get('ERROR', 0)}",
        f"Fallos de integridad actuales: {integrity_failures}",
        "",
        "COMPONENTES",
        "-" * 68,
    ]

    if not results:
        lines.extend(
            [
                "ERROR: No se recibieron resultados del mantenimiento.",
                "",
            ]
        )

    for result in results:
        checksum_type, expected, installed, integrity = integrity_data.get(
            result["id"],
            ("no aplica", "", "", "NO DISPONIBLE"),
        )

        lines.append(f"{result['name']}: {result['status']}")
        lines.append(f"  Versión objetivo: {result['desired'] or '-'}")
        lines.append(f"  Versión anterior: {result['previous'] or '-'}")
        lines.append(f"  Versión final: {result['final'] or '-'}")
        lines.append(f"  Tipo de huella: {checksum_type}")
        lines.append(f"  SHA-256 aprobada: {expected or 'no disponible'}")
        lines.append(f"  SHA-256 instalada: {installed or 'no disponible'}")
        lines.append(f"  Integridad: {integrity}")
        if result["message"]:
            lines.append(f"  Detalle: {result['message']}")
        lines.append("")

    lines.extend(["CONFIGURACIÓN UTILIZADA", "-" * 68])

    for component in catalog.values():
        name = component.get("name", component.get("id", "Componente"))
        option_name = component.get("option", "")
        if not isinstance(name, str):
            name = "Componente"
        if not isinstance(option_name, str) or not option_name:
            continue
        state = "activado" if is_enabled(options, option_name) else "desactivado"
        lines.append(f"{name}: {state}")

    lines.extend(
        [
            "",
            "INFORMACIÓN DEL CATÁLOGO",
            "-" * 68,
            "Versiones, URL, rutas y huellas se leen desde components.json.",
            "Las descargas con una huella diferente se rechazan.",
            "",
        ]
    )

    report_content = "\n".join(lines)

    try:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        timestamped_report = REPORT_DIR / f"maintenance-{timestamp}.txt"
        latest_report = REPORT_DIR / "latest.txt"
        timestamped_report.write_text(report_content, encoding="utf-8")
        latest_report.write_text(report_content, encoding="utf-8")
    except OSError as error:
        print(
            f"[report] ERROR: No se pudo guardar el reporte: {error}",
            file=sys.stderr,
            flush=True,
        )
        return 1

    deleted_count, cleanup_errors = prune_historical_reports()

    print(f"[report] Reporte guardado: {timestamped_report}", flush=True)
    print(f"[report] Último reporte: {latest_report}", flush=True)
    print(f"[report] Catálogo utilizado: {catalog_version}", flush=True)
    print(f"[report] Resultado general: {overall_result}", flush=True)
    print("[report] Validación SHA-256 activa", flush=True)
    print(
        f"[report] Reportes históricos conservados: {MAX_HISTORICAL_REPORTS}",
        flush=True,
    )

    if deleted_count > 0:
        print(
            f"[report] Reportes históricos eliminados: {deleted_count}",
            flush=True,
        )

    for cleanup_error in cleanup_errors:
        print(
            f"[report] WARNING: {cleanup_error}",
            file=sys.stderr,
            flush=True,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
