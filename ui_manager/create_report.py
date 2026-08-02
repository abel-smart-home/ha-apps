#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from collections import Counter
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


def is_enabled(options: dict[str, Any], key: str) -> bool:
    return options.get(key, True) is True


def read_results(path: Path) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []

    try:
        lines = path.read_text(
            encoding="utf-8",
        ).splitlines()
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


def prune_historical_reports() -> tuple[int, list[str]]:
    historical_reports = sorted(
        (
            path
            for path in REPORT_DIR.glob(
                "maintenance-*.txt"
            )
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
                f"No se pudo eliminar "
                f"{report_path.name}: {error}"
            )

    return deleted_count, errors


def main() -> int:
    restart_required = (
        len(sys.argv) > 1
        and sys.argv[1].strip().lower() == "true"
    )

    results_file = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else Path("/tmp/ui_manager_results.tsv")
    )

    options = read_json(OPTIONS_FILE)
    results = read_results(results_file)

    status_counts = Counter(
        result["status"]
        for result in results
    )

    error_count = status_counts.get("ERROR", 0)
    installed_count = status_counts.get(
        "INSTALADO",
        0,
    )
    updated_count = status_counts.get(
        "ACTUALIZADO",
        0,
    )

    if not results:
        overall_result = "REVISAR"
    elif error_count > 0:
        overall_result = "REVISAR"
    elif installed_count > 0 or updated_count > 0:
        overall_result = "CAMBIOS APLICADOS"
    else:
        overall_result = "CORRECTO"

    restart_text = (
        "REQUERIDO"
        if restart_required
        else "NO REQUERIDO"
    )

    now = datetime.now().astimezone()
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    formatted_date = now.strftime(
        "%Y-%m-%d %H:%M:%S %z"
    )

    lines = [
        "SMART HOME UI MANAGER",
        "REPORTE DE MANTENIMIENTO",
        "=" * 68,
        f"Fecha: {formatted_date}",
        f"Resultado general: {overall_result}",
        (
            "Reinicio de Home Assistant Core: "
            f"{restart_text}"
        ),
        "",
        "RESUMEN",
        "-" * 68,
        (
            "Verificados: "
            f"{status_counts.get('VERIFICADO', 0)}"
        ),
        (
            "Instalados: "
            f"{status_counts.get('INSTALADO', 0)}"
        ),
        (
            "Actualizados: "
            f"{status_counts.get('ACTUALIZADO', 0)}"
        ),
        (
            "Omitidos: "
            f"{status_counts.get('OMITIDO', 0)}"
        ),
        (
            "Errores: "
            f"{status_counts.get('ERROR', 0)}"
        ),
        "",
        "COMPONENTES",
        "-" * 68,
    ]

    if not results:
        lines.extend(
            [
                "ERROR: No se recibieron resultados "
                "del proceso de mantenimiento.",
                "",
            ]
        )

    for result in results:
        lines.append(
            f"{result['name']}: {result['status']}"
        )

        lines.append(
            f"  Versión objetivo: "
            f"{result['desired'] or '-'}"
        )

        lines.append(
            f"  Versión anterior: "
            f"{result['previous'] or '-'}"
        )

        lines.append(
            f"  Versión final: "
            f"{result['final'] or '-'}"
        )

        if result["message"]:
            lines.append(
                f"  Detalle: {result['message']}"
            )

        lines.append("")

    lines.extend(
        [
            "CONFIGURACIÓN UTILIZADA",
            "-" * 68,
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
            "[report] ERROR: No se pudo guardar "
            f"el reporte: {error}",
            file=sys.stderr,
            flush=True,
        )
        return 1

    deleted_count, cleanup_errors = (
        prune_historical_reports()
    )

    print(
        f"[report] Reporte guardado: "
        f"{timestamped_report}",
        flush=True,
    )

    print(
        f"[report] Último reporte: "
        f"{latest_report}",
        flush=True,
    )

    print(
        f"[report] Resultado general: "
        f"{overall_result}",
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
