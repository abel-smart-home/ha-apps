#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from compatibility_utils import (
    CompatibilityError,
    compatibility_status,
    fetch_home_assistant_version,
    is_version_at_least,
    parse_version,
)


CONFIG_ROOT = Path(os.environ.get("UI_MANAGER_CONFIG_ROOT", "/config"))
REPORT_DIR = CONFIG_ROOT / "ui-manager" / "test" / "compatibility"
MAX_REPORTS = 20
COMPONENT_MANAGER = Path(
    os.environ.get("UI_MANAGER_COMPONENT_MANAGER", "/component_manager.py")
)


def prune_reports() -> None:
    reports = sorted(
        (path for path in REPORT_DIR.glob("compatibility-*.txt") if path.is_file()),
        key=lambda path: path.name,
        reverse=True,
    )
    for old_report in reports[MAX_REPORTS:]:
        old_report.unlink(missing_ok=True)


def run_manager_block_test() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="ui-manager-compat-") as temporary_name:
        root = Path(temporary_name)
        config_root = root / "config"
        config_root.mkdir(parents=True)
        options_file = root / "options.json"
        options_file.write_text(
            json.dumps({"blocked_test": True}),
            encoding="utf-8",
        )
        catalog_file = root / "components.json"
        results_file = root / "results.tsv"
        state_file = root / "state.json"

        catalog_file.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "catalog_version": "controlled-test-0.5.0",
                    "components": [
                        {
                            "id": "blocked_test",
                            "name": "Prueba de componente incompatible",
                            "option": "blocked_test",
                            "type": "frontend",
                            "version": "1.0.0",
                            "url": "https://example.invalid/should-not-download.js",
                            "sha256": "0" * 64,
                            "min_home_assistant": "9999.1.0",
                            "install_dir": "/config/www/ui-manager-test",
                            "filename": "blocked.js",
                            "resource_url": "/local/ui-manager-test/blocked.js",
                            "resource_type": "module",
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        environment = os.environ.copy()
        environment.update(
            {
                "UI_MANAGER_OPTIONS_FILE": str(options_file),
                "UI_MANAGER_CONFIG_ROOT": str(config_root),
                "UI_MANAGER_HA_VERSION_OVERRIDE": "2026.7.4",
                "UI_MANAGER_SKIP_RESOURCE_REGISTRATION": "true",
            }
        )

        process = subprocess.run(
            [
                sys.executable,
                str(COMPONENT_MANAGER),
                str(catalog_file),
                str(results_file),
                str(state_file),
            ],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        result_text = results_file.read_text(encoding="utf-8") if results_file.exists() else ""
        state = (
            json.loads(state_file.read_text(encoding="utf-8"))
            if state_file.exists()
            else {}
        )
        installed_file = config_root / "www" / "ui-manager-test" / "blocked.js"

        passed = (
            process.returncode == 2
            and "\tINCOMPATIBLE\t" in result_text
            and state.get("incompatible") == 1
            and state.get("home_assistant_version") == "2026.7.4"
            and not installed_file.exists()
        )

        detail = (
            "El componente incompatible fue omitido sin descarga ni instalación"
            if passed
            else (
                "Resultado inesperado. "
                f"Código={process.returncode}; estado={state}; "
                f"resultado={result_text.strip() or 'vacío'}"
            )
        )
        return passed, detail


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    version_cases = [
        ("2026.7.4", "2026.3.0", True),
        ("2026.7.4", "2026.8.0", False),
        ("2026.8.0b1", "2026.8.0", False),
        ("2026.8.0", "2026.8.0b1", True),
        ("2026.8.0rc1", "2026.8.0b9", True),
    ]

    for current, minimum, expected in version_cases:
        try:
            result = is_version_at_least(current, minimum)
            passed = result is expected
            detail = (
                f"{current} >= {minimum}: {result}; esperado: {expected}"
            )
        except CompatibilityError as error:
            passed = False
            detail = str(error)
        checks.append(("Comparación de versiones", passed, detail))

    try:
        parse_version("2026.7.4")
        checks.append(("Formato de versión válido", True, "2026.7.4 aceptada"))
    except CompatibilityError as error:
        checks.append(("Formato de versión válido", False, str(error)))

    try:
        parse_version("versión-inválida")
        checks.append(
            (
                "Rechazo de versión inválida",
                False,
                "La versión inválida fue aceptada",
            )
        )
    except CompatibilityError:
        checks.append(
            (
                "Rechazo de versión inválida",
                True,
                "La versión inválida fue rechazada",
            )
        )

    try:
        detected_version = fetch_home_assistant_version()
        checks.append(
            (
                "Lectura de Home Assistant Core",
                True,
                f"Versión detectada: {detected_version}",
            )
        )
    except CompatibilityError as error:
        detected_version = "no disponible"
        checks.append(("Lectura de Home Assistant Core", False, str(error)))

    checks.append(
        (
            "Estado sin requisito mínimo",
            compatibility_status(detected_version if detected_version != "no disponible" else "", "")
            == "NO REQUERIDA",
            "Los componentes sin mínimo no se bloquean",
        )
    )

    manager_passed, manager_detail = run_manager_block_test()
    checks.append(
        (
            "Bloqueo controlado antes de descargar",
            manager_passed,
            manager_detail,
        )
    )

    failures = sum(1 for _, passed, _ in checks if not passed)
    result = "CORRECTO" if failures == 0 else "REVISAR"
    now = datetime.now().astimezone()
    timestamp = now.strftime("%Y%m%d-%H%M%S")

    lines = [
        "SMART HOME UI MANAGER",
        "PRUEBA CONTROLADA DE COMPATIBILIDAD 0.5.0",
        "=" * 76,
        f"Fecha: {now.strftime('%Y-%m-%d %H:%M:%S %z')}",
        f"Resultado: {result}",
        "Modo: SOLO LECTURA / AISLADO",
        "Componentes reales modificados: NO",
        f"Versión real de Home Assistant detectada: {detected_version}",
        "",
        "VALIDACIONES",
        "-" * 76,
    ]

    for name, passed, detail in checks:
        lines.extend(
            [
                f"{name}: {'CORRECTO' if passed else 'ERROR'}",
                f"  {detail}",
            ]
        )

    lines.extend(
        [
            "",
            "RESUMEN",
            "-" * 76,
            f"Pruebas ejecutadas: {len(checks)}",
            f"Errores: {failures}",
            "El catálogo ficticio incompatible no fue descargado ni instalado.",
            "",
        ]
    )

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = REPORT_DIR / f"compatibility-{timestamp}.txt"
    latest = REPORT_DIR / "latest.txt"
    content = "\n".join(lines)
    report.write_text(content, encoding="utf-8")
    latest.write_text(content, encoding="utf-8")
    prune_reports()

    print(f"[compatibility-test] Reporte guardado: {report}", flush=True)
    print(f"[compatibility-test] Último reporte: {latest}", flush=True)
    print(f"[compatibility-test] Resultado: {result}", flush=True)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
