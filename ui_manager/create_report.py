#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


OPTIONS_FILE = Path("/data/options.json")
REPORT_DIR = Path("/config/ui-manager/reports")
MAX_HISTORICAL_REPORTS = 20


def read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass

    return {}


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def is_enabled(options: dict[str, Any], key: str) -> bool:
    return options.get(key, True) is True


def frontend_status(
    options: dict[str, Any],
    option_key: str,
    version_file: Path,
    component_file: Path,
) -> tuple[str, str]:
    if not is_enabled(options, option_key):
        return "OMITIDO", "-"

    if not component_file.is_file():
        return "NO INSTALADO", "-"

    version = read_text(version_file)

    if not version:
        version = "desconocida"

    return "VERIFICADO", version


def integration_status(
    options: dict[str, Any],
    option_key: str,
    manifest_file: Path,
) -> tuple[str, str]:
    if not is_enabled(options, option_key):
        return "OMITIDO", "-"

    if not manifest_file.is_file():
        return "NO INSTALADO", "-"

    manifest = read_json(manifest_file)
    version = manifest.get("version", "desconocida")

    if not isinstance(version, str) or not version.strip():
        version = "desconocida"

    return "VERIFICADO", version


def prune_historical_reports() -> tuple[int, list[str]]:
    """
    Conserva solamente los reportes históricos más recientes.

    latest.txt no coincide con el patrón maintenance-*.txt,
    por lo que no se incluye en este límite.
    """
    historical_reports = sorted(
        (
            path
            for path in REPORT_DIR.glob("maintenance-*.txt")
            if path.is_file()
        ),
        key=lambda path: path.name,
        reverse=True,
    )

    reports_to_delete = historical_reports[
        MAX_HISTORICAL_REPORTS:
    ]

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


def main() -> int:
    restart_required = (
        len(sys.argv) > 1
        and sys.argv[1].strip().lower() == "true"
    )

    options = read_json(OPTIONS_FILE)

    components = [
        (
            "Mini Graph Card",
            *frontend_status(
                options,
                "mini_graph_card",
                Path(
                    "/config/www/ui-components/"
                    "mini-graph-card/version"
                ),
                Path(
                    "/config/www/ui-components/"
                    "mini-graph-card/"
                    "mini-graph-card-bundle.js"
                ),
            ),
        ),
        (
            "Mushroom",
            *frontend_status(
                options,
                "mushroom",
                Path(
                    "/config/www/ui-components/"
                    "mushroom/version"
                ),
                Path(
                    "/config/www/ui-components/"
                    "mushroom/mushroom.js"
                ),
            ),
        ),
        (
            "Modern Circular Gauge",
            *frontend_status(
                options,
                "modern_circular_gauge",
                Path(
                    "/config/www/ui-components/"
                    "modern-circular-gauge/version"
                ),
                Path(
                    "/config/www/ui-components/"
                    "modern-circular-gauge/"
                    "modern-circular-gauge.js"
                ),
            ),
        ),
        (
            "SonoffLAN",
            *integration_status(
                options,
                "sonofflan",
                Path(
                    "/config/custom_components/"
                    "sonoff/manifest.json"
                ),
            ),
        ),
        (
            "Spook",
            *integration_status(
                options,
                "spook",
                Path(
                    "/config/custom_components/"
                    "spook/manifest.json"
                ),
            ),
        ),
    ]

    requires_review = any(
        status == "NO INSTALADO"
        for _, status, _ in components
    )

    overall_result = (
        "REVISAR"
        if requires_review
        else "CORRECTO"
    )

    restart_text = (
        "REQUERIDO"
        if restart_required
        else "NO REQUERIDO"
    )

    now = datetime.now().astimezone()
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    formatted_date = now.strftime("%Y-%m-%d %H:%M:%S %z")

    lines = [
        "SMART HOME UI MANAGER",
        "REPORTE DE MANTENIMIENTO",
        "=" * 60,
        f"Fecha: {formatted_date}",
        f"Resultado general: {overall_result}",
        f"Reinicio de Home Assistant Core: {restart_text}",
        "",
        "COMPONENTES",
        "-" * 60,
    ]

    for name, status, version in components:
        lines.append(
            f"{name}: {status} | Versión: {version}"
        )

    lines.extend(
        [
            "",
            "CONFIGURACIÓN UTILIZADA",
            "-" * 60,
            (
                "Mini Graph Card: "
                f"{'activado' if is_enabled(options, 'mini_graph_card') else 'desactivado'}"
            ),
            (
                "Mushroom: "
                f"{'activado' if is_enabled(options, 'mushroom') else 'desactivado'}"
            ),
            (
                "Modern Circular Gauge: "
                f"{'activado' if is_enabled(options, 'modern_circular_gauge') else 'desactivado'}"
            ),
            (
                "SonoffLAN: "
                f"{'activado' if is_enabled(options, 'sonofflan') else 'desactivado'}"
            ),
            (
                "Spook: "
                f"{'activado' if is_enabled(options, 'spook') else 'desactivado'}"
            ),
            "",
        ]
    )

    report_content = "\n".join(lines)

    try:
        REPORT_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        timestamped_report = (
            REPORT_DIR
            / f"maintenance-{timestamp}.txt"
        )

        latest_report = REPORT_DIR / "latest.txt"

        timestamped_report.write_text(
            report_content,
            encoding="utf-8",
        )

        latest_report.write_text(
            report_content,
            encoding="utf-8",
        )

    except OSError as error:
        print(
            f"[report] ERROR: No se pudo guardar el reporte: {error}",
            file=sys.stderr,
            flush=True,
        )
        return 1

    deleted_count, cleanup_errors = (
        prune_historical_reports()
    )

    print(
        f"[report] Reporte guardado: {timestamped_report}",
        flush=True,
    )

    print(
        f"[report] Último reporte: {latest_report}",
        flush=True,
    )

    print(
        f"[report] Resultado general: {overall_result}",
        flush=True,
    )

    print(
        "[report] Reportes históricos conservados: "
        f"{MAX_HISTORICAL_REPORTS}",
        flush=True,
    )

    if deleted_count > 0:
        print(
            "[report] Reportes históricos eliminados: "
            f"{deleted_count}",
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
