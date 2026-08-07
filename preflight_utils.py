#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import socket
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

from build_metadata import get_build_metadata, metadata_lines
from compatibility_utils import CompatibilityError, fetch_home_assistant_version
from component_manager import CatalogError, Component, load_catalog


CONFIG_ROOT = Path(os.environ.get("UI_MANAGER_CONFIG_ROOT", "/config"))
OPTIONS_FILE = Path(os.environ.get("UI_MANAGER_OPTIONS_FILE", "/data/options.json"))
REPORT_DIR = CONFIG_ROOT / "ui-manager" / "diagnostics"
MAX_REPORTS = 20


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    name: str
    status: str
    critical: bool
    detail: str


@dataclass(frozen=True)
class PreflightSummary:
    result: str
    failures: int
    warnings: int
    checks: tuple[CheckResult, ...]
    home_assistant_version: str
    report_path: Path | None
    latest_path: Path | None


class PreflightError(RuntimeError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}

    return data if isinstance(data, dict) else {}


def option_enabled(options: dict[str, Any], name: str) -> bool:
    return options.get(name, True) is True


def configured_minimum_free_space(options: dict[str, Any]) -> int:
    value = options.get("minimum_free_space_mb", 200)
    if isinstance(value, bool) or not isinstance(value, int):
        return 200
    return min(max(value, 50), 5000)


def directory_write_check(path: Path) -> tuple[bool, str]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=".ui-manager-write-test-",
            dir=path,
            delete=False,
        ) as file:
            file.write("ok\n")
            test_path = Path(file.name)
        test_path.unlink()
    except OSError as error:
        return False, str(error)

    return True, "Lectura y escritura disponibles"


def free_space_mb(path: Path) -> int:
    usage = shutil.disk_usage(path)
    return int(usage.free / (1024 * 1024))


def has_python_module(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def enabled_components_requiring_ha_version(
    components: Iterable[Component],
    options: dict[str, Any],
) -> list[Component]:
    return [
        component
        for component in components
        if component.min_home_assistant
        and option_enabled(options, component.option)
    ]


def can_resolve_github() -> tuple[bool, str]:
    try:
        addresses = socket.getaddrinfo(
            "github.com",
            443,
            type=socket.SOCK_STREAM,
        )
    except OSError as error:
        return False, str(error)

    if not addresses:
        return False, "No se obtuvieron direcciones DNS"

    return True, "Resolución DNS de github.com disponible"


def evaluate_free_space(available_mb: int, minimum_mb: int) -> CheckResult:
    if available_mb < minimum_mb:
        return CheckResult(
            "free_space",
            "Espacio libre en /config",
            "FAIL",
            True,
            (
                f"Disponibles: {available_mb} MB; "
                f"mínimo configurado: {minimum_mb} MB"
            ),
        )

    if available_mb < minimum_mb * 2:
        return CheckResult(
            "free_space",
            "Espacio libre en /config",
            "WARN",
            False,
            (
                f"Disponibles: {available_mb} MB; "
                f"mínimo configurado: {minimum_mb} MB"
            ),
        )

    return CheckResult(
        "free_space",
        "Espacio libre en /config",
        "PASS",
        False,
        (
            f"Disponibles: {available_mb} MB; "
            f"mínimo configurado: {minimum_mb} MB"
        ),
    )


def prune_reports(report_dir: Path = REPORT_DIR) -> int:
    reports = sorted(
        (
            path
            for path in report_dir.glob("diagnostic-*.txt")
            if path.is_file()
        ),
        key=lambda path: path.name,
        reverse=True,
    )

    deleted = 0
    for path in reports[MAX_REPORTS:]:
        try:
            path.unlink()
            deleted += 1
        except OSError:
            continue
    return deleted


def write_report(
    checks: Iterable[CheckResult],
    *,
    mode: str,
    home_assistant_version: str,
    minimum_free_space_mb: int,
    report_dir: Path = REPORT_DIR,
) -> tuple[Path, Path]:
    check_list = list(checks)
    failures = sum(item.status == "FAIL" for item in check_list)
    warnings = sum(item.status == "WARN" for item in check_list)
    overall = "REVISAR" if failures else ("ADVERTENCIAS" if warnings else "CORRECTO")

    now = datetime.now().astimezone()
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    formatted_date = now.strftime("%Y-%m-%d %H:%M:%S %z")

    build_metadata = get_build_metadata()

    lines = [
        "SMART HOME UI MANAGER",
        f"DIAGNÓSTICO PREVIO {build_metadata.version}",
        "=" * 76,
        f"Fecha: {formatted_date}",
        f"Modo: {mode}",
        f"Resultado: {overall}",
        f"Home Assistant Core: {home_assistant_version or 'no detectado'}",
        f"Espacio mínimo configurado: {minimum_free_space_mb} MB",
        "Componentes reales modificados: NO",
        "",
        "INFORMACIÓN DE COMPILACIÓN",
        "-" * 76,
        *metadata_lines(build_metadata),
        "",
        "VALIDACIONES",
        "-" * 76,
    ]

    for item in check_list:
        critical_text = "crítica" if item.critical else "informativa"
        lines.extend(
            [
                f"{item.name}: {item.status}",
                f"  ID: {item.check_id}",
                f"  Importancia: {critical_text}",
                f"  Detalle: {item.detail}",
                "",
            ]
        )

    lines.extend(
        [
            "RESUMEN",
            "-" * 76,
            f"Validaciones ejecutadas: {len(check_list)}",
            f"Fallos críticos: {failures}",
            f"Advertencias: {warnings}",
            "",
            "DECISIÓN",
            "-" * 76,
            (
                "El mantenimiento puede continuar."
                if failures == 0
                else "El mantenimiento debe detenerse antes de modificar componentes."
            ),
            "",
        ]
    )

    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"diagnostic-{timestamp}.txt"
    latest_path = report_dir / "latest.txt"
    content = "\n".join(lines)
    report_path.write_text(content, encoding="utf-8")
    latest_path.write_text(content, encoding="utf-8")
    prune_reports(report_dir)
    return report_path, latest_path


def run_preflight(
    catalog_path: Path,
    *,
    mode: str,
    report_dir: Path = REPORT_DIR,
    config_root: Path = CONFIG_ROOT,
    options_file: Path = OPTIONS_FILE,
    fetch_version: Callable[[], str] = fetch_home_assistant_version,
    dns_check: Callable[[], tuple[bool, str]] = can_resolve_github,
) -> PreflightSummary:
    options = read_json(options_file)
    minimum_space = configured_minimum_free_space(options)
    checks: list[CheckResult] = []
    components: list[Component] = []

    build_metadata = get_build_metadata()
    checks.append(
        CheckResult(
            "build_metadata",
            "Trazabilidad de la imagen",
            "PASS" if build_metadata.complete else "WARN",
            False,
            (
                "Versión, arquitectura, commit, fecha e imagen disponibles"
                if build_metadata.complete
                else "Uno o más metadatos de compilación no están disponibles"
            ),
        )
    )

    try:
        catalog_version, components = load_catalog(catalog_path)
        checks.append(
            CheckResult(
                "catalog",
                "Catálogo components.json",
                "PASS",
                True,
                (
                    f"Catálogo {catalog_version} válido; "
                    f"componentes: {len(components)}"
                ),
            )
        )
    except CatalogError as error:
        checks.append(
            CheckResult(
                "catalog",
                "Catálogo components.json",
                "FAIL",
                True,
                str(error),
            )
        )

    required_commands = ("python3", "curl")
    missing_commands = [name for name in required_commands if shutil.which(name) is None]
    checks.append(
        CheckResult(
            "commands",
            "Comandos requeridos",
            "FAIL" if missing_commands else "PASS",
            True,
            (
                "Faltan: " + ", ".join(missing_commands)
                if missing_commands
                else "python3 y curl disponibles"
            ),
        )
    )

    required_modules = ("packaging", "websocket")
    missing_modules = [name for name in required_modules if not has_python_module(name)]
    checks.append(
        CheckResult(
            "python_modules",
            "Módulos de Python",
            "FAIL" if missing_modules else "PASS",
            True,
            (
                "Faltan: " + ", ".join(missing_modules)
                if missing_modules
                else "packaging y websocket disponibles"
            ),
        )
    )

    if not config_root.exists():
        checks.append(
            CheckResult(
                "config_root",
                "Montaje /config",
                "FAIL",
                True,
                f"No existe: {config_root}",
            )
        )
    else:
        checks.append(
            CheckResult(
                "config_root",
                "Montaje /config",
                "PASS",
                True,
                f"Disponible: {config_root}",
            )
        )

    for check_id, name, path in (
        ("manager_directory", "Directorio de trabajo", config_root / "ui-manager"),
        ("frontend_directory", "Directorio de tarjetas", config_root / "www"),
        (
            "integration_directory",
            "Directorio de integraciones",
            config_root / "custom_components",
        ),
    ):
        writable, detail = directory_write_check(path)
        checks.append(
            CheckResult(
                check_id,
                name,
                "PASS" if writable else "FAIL",
                True,
                f"{path}: {detail}",
            )
        )

    try:
        available = free_space_mb(config_root)
        checks.append(evaluate_free_space(available, minimum_space))
    except OSError as error:
        checks.append(
            CheckResult(
                "free_space",
                "Espacio libre en /config",
                "FAIL",
                True,
                str(error),
            )
        )

    token_available = bool(os.environ.get("SUPERVISOR_TOKEN", "").strip())
    checks.append(
        CheckResult(
            "supervisor_token",
            "Token interno de Supervisor",
            "PASS" if token_available else "FAIL",
            True,
            (
                "SUPERVISOR_TOKEN disponible"
                if token_available
                else "SUPERVISOR_TOKEN no está disponible"
            ),
        )
    )

    home_assistant_version = ""
    version_required = enabled_components_requiring_ha_version(components, options)
    try:
        home_assistant_version = fetch_version()
        checks.append(
            CheckResult(
                "home_assistant_api",
                "Consulta de Home Assistant Core",
                "PASS",
                bool(version_required),
                f"Versión detectada: {home_assistant_version}",
            )
        )
    except CompatibilityError as error:
        checks.append(
            CheckResult(
                "home_assistant_api",
                "Consulta de Home Assistant Core",
                "FAIL" if version_required else "WARN",
                bool(version_required),
                str(error),
            )
        )

    dns_ok, dns_detail = dns_check()
    checks.append(
        CheckResult(
            "github_dns",
            "Resolución de GitHub",
            "PASS" if dns_ok else "WARN",
            False,
            dns_detail,
        )
    )

    failures = sum(item.status == "FAIL" for item in checks)
    warnings = sum(item.status == "WARN" for item in checks)
    result = "REVISAR" if failures else ("ADVERTENCIAS" if warnings else "CORRECTO")

    report_path: Path | None = None
    latest_path: Path | None = None
    try:
        report_path, latest_path = write_report(
            checks,
            mode=mode,
            home_assistant_version=home_assistant_version,
            minimum_free_space_mb=minimum_space,
            report_dir=report_dir,
        )
    except OSError as error:
        checks.append(
            CheckResult(
                "diagnostic_report",
                "Reporte de diagnóstico",
                "FAIL",
                True,
                str(error),
            )
        )
        failures += 1
        result = "REVISAR"

    return PreflightSummary(
        result=result,
        failures=failures,
        warnings=warnings,
        checks=tuple(checks),
        home_assistant_version=home_assistant_version,
        report_path=report_path,
        latest_path=latest_path,
    )
