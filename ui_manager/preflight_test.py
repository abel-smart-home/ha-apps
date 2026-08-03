#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from preflight_utils import evaluate_free_space, run_preflight


CONFIG_ROOT = Path(os.environ.get("UI_MANAGER_CONFIG_ROOT", "/config"))
TEST_ROOT = CONFIG_ROOT / "ui-manager" / "test" / "preflight"


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main() -> int:
    TEST_ROOT.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix="ui-manager-preflight-",
        dir=TEST_ROOT,
    ) as temporary:
        root = Path(temporary)
        config_root = root / "config"
        config_root.mkdir(parents=True, exist_ok=True)
        report_dir = root / "reports"
        options_file = root / "options.json"
        valid_catalog = root / "components-valid.json"
        invalid_catalog = root / "components-invalid.json"

        write_json(
            options_file,
            {
                "minimum_free_space_mb": 50,
                "test_component": True,
            },
        )
        write_json(
            valid_catalog,
            {
                "schema_version": 2,
                "catalog_version": "test-0.6.0",
                "components": [
                    {
                        "id": "test_component",
                        "name": "Componente ficticio",
                        "option": "test_component",
                        "type": "frontend",
                        "version": "1.0.0",
                        "url": "https://example.invalid/test.js",
                        "sha256": "0" * 64,
                        "install_dir": "/config/www/test-component",
                        "filename": "test.js",
                        "resource_url": "/local/test-component/test.js",
                        "resource_type": "module",
                    }
                ],
            },
        )
        write_json(
            invalid_catalog,
            {
                "schema_version": 2,
                "catalog_version": "test-invalid",
                "components": [],
            },
        )

        old_token = os.environ.get("SUPERVISOR_TOKEN")
        os.environ["SUPERVISOR_TOKEN"] = "controlled-test-token"
        try:
            valid_summary = run_preflight(
                valid_catalog,
                mode="PRUEBA CONTROLADA",
                report_dir=report_dir / "valid",
                config_root=config_root,
                options_file=options_file,
                fetch_version=lambda: "2026.7.4",
                dns_check=lambda: (True, "DNS simulado correctamente"),
            )
            invalid_summary = run_preflight(
                invalid_catalog,
                mode="PRUEBA CONTROLADA",
                report_dir=report_dir / "invalid",
                config_root=config_root,
                options_file=options_file,
                fetch_version=lambda: "2026.7.4",
                dns_check=lambda: (True, "DNS simulado correctamente"),
            )
        finally:
            if old_token is None:
                os.environ.pop("SUPERVISOR_TOKEN", None)
            else:
                os.environ["SUPERVISOR_TOKEN"] = old_token

        free_space_pass = evaluate_free_space(1000, 100)
        free_space_fail = evaluate_free_space(50, 100)

        validations = [
            (
                "Catálogo válido aceptado",
                valid_summary.failures == 0,
                f"Fallos detectados: {valid_summary.failures}",
            ),
            (
                "Catálogo inválido bloqueado",
                invalid_summary.failures >= 1,
                f"Fallos detectados: {invalid_summary.failures}",
            ),
            (
                "Espacio suficiente aceptado",
                free_space_pass.status == "PASS",
                f"Estado: {free_space_pass.status}",
            ),
            (
                "Espacio insuficiente bloqueado",
                free_space_fail.status == "FAIL" and free_space_fail.critical,
                f"Estado: {free_space_fail.status}",
            ),
            (
                "Componentes reales modificados",
                not (CONFIG_ROOT / "custom_components" / "ui_manager_test").exists(),
                "NO",
            ),
        ]

        errors = sum(not passed for _, passed, _ in validations)
        result = "CORRECTO" if errors == 0 else "REVISAR"
        now = datetime.now().astimezone()
        timestamp = now.strftime("%Y%m%d-%H%M%S")
        formatted_date = now.strftime("%Y-%m-%d %H:%M:%S %z")

        lines = [
            "SMART HOME UI MANAGER",
            "PRUEBA CONTROLADA DE DIAGNÓSTICO 0.6.0",
            "=" * 76,
            f"Fecha: {formatted_date}",
            f"Resultado: {result}",
            "Modo: AISLADO",
            "Componentes reales modificados: NO",
            "",
            "VALIDACIONES",
            "-" * 76,
        ]

        for name, passed, detail in validations:
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
                f"Pruebas ejecutadas: {len(validations)}",
                f"Errores: {errors}",
                "El catálogo inválido fue detenido antes de modificar archivos.",
                "",
            ]
        )

        report_path = TEST_ROOT / f"preflight-test-{timestamp}.txt"
        latest_path = TEST_ROOT / "latest.txt"
        content = "\n".join(lines)
        report_path.write_text(content, encoding="utf-8")
        latest_path.write_text(content, encoding="utf-8")

        print(f"[preflight-test] Reporte guardado: {report_path}", flush=True)
        print(f"[preflight-test] Último reporte: {latest_path}", flush=True)
        print(f"[preflight-test] Resultado: {result}", flush=True)

        return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
