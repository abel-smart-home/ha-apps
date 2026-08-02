#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from checksum_utils import calculate_tree_sha256


OPTIONS_FILE = Path(os.environ.get("UI_MANAGER_OPTIONS_FILE", "/data/options.json"))
CONFIG_ROOT = Path(os.environ.get("UI_MANAGER_CONFIG_ROOT", "/config"))
DEFAULT_CATALOG = Path("/components.json")
DEFAULT_RESTORE_REPORT_DIR = CONFIG_ROOT / "ui-manager" / "restore-reports"
MAX_RESTORE_REPORTS = 20
DEFAULT_BACKUP_LIMIT = 5
MIN_BACKUP_LIMIT = 1
MAX_BACKUP_LIMIT = 20
BACKUP_NAME_PATTERN = re.compile(r"^\d{8}-\d{6}(?:-\d{2})?$")


@dataclass(frozen=True)
class IntegrationDefinition:
    component_id: str
    name: str
    integration_id: str


class BackupError(RuntimeError):
    pass


def log(level: str, message: str) -> None:
    print(f"[backup] {level}: {message}", flush=True)


def read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        raise BackupError(f"No se pudo leer {path}: {error}") from error

    if not isinstance(data, dict):
        raise BackupError(f"{path} debe contener un objeto JSON")

    return data


def read_options(path: Path = OPTIONS_FILE) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}

    return data if isinstance(data, dict) else {}


def normalize_backup_limit(value: object) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return DEFAULT_BACKUP_LIMIT

    return max(MIN_BACKUP_LIMIT, min(MAX_BACKUP_LIMIT, parsed))


def configured_backup_limit(options: dict[str, Any] | None = None) -> int:
    if options is None:
        options = read_options()
    return normalize_backup_limit(options.get("max_integration_backups"))


def read_manifest_version(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return ""

    version = data.get("version") if isinstance(data, dict) else ""
    return version.strip() if isinstance(version, str) else ""


def next_backup_name(backup_root: Path) -> str:
    base = datetime.now().strftime("%Y%m%d-%H%M%S")
    if not (backup_root / base).exists() and not (backup_root / f"{base}.json").exists():
        return base

    for suffix in range(1, 100):
        candidate = f"{base}-{suffix:02d}"
        if not (backup_root / candidate).exists() and not (
            backup_root / f"{candidate}.json"
        ).exists():
            return candidate

    raise BackupError("No se pudo generar un nombre único para el respaldo")


def list_backup_directories(backup_root: Path) -> list[Path]:
    if not backup_root.is_dir():
        return []

    return sorted(
        (
            path
            for path in backup_root.iterdir()
            if path.is_dir() and BACKUP_NAME_PATTERN.fullmatch(path.name)
        ),
        key=lambda path: path.name,
        reverse=True,
    )


def delete_backup(backup_path: Path) -> None:
    shutil.rmtree(backup_path)
    metadata_path = backup_path.with_suffix(".json")
    metadata_path.unlink(missing_ok=True)


def prune_backups(
    backup_root: Path,
    max_backups: int,
    protected_names: set[str] | None = None,
) -> tuple[int, list[str]]:
    protected_names = protected_names or set()
    backups = list_backup_directories(backup_root)
    keep: set[str] = {
        path.name for path in backups if path.name in protected_names
    }

    for path in backups:
        if len(keep) >= max_backups:
            break
        keep.add(path.name)

    deleted_count = 0
    errors: list[str] = []

    for backup_path in backups:
        if backup_path.name in keep:
            continue
        try:
            delete_backup(backup_path)
            deleted_count += 1
        except OSError as error:
            errors.append(f"No se pudo eliminar {backup_path.name}: {error}")

    return deleted_count, errors


def create_integration_backup(
    source: Path,
    backup_root: Path,
    *,
    component_id: str,
    component_name: str,
    integration_id: str,
    reason: str,
    max_backups: int,
    protected_names: set[str] | None = None,
) -> Path:
    if not source.is_dir():
        raise BackupError(f"La carpeta a respaldar no existe: {source}")

    manifest_path = source / "manifest.json"
    version = read_manifest_version(manifest_path)
    if not version:
        raise BackupError("La integración a respaldar no tiene un manifest válido")

    checksum = calculate_tree_sha256(source)
    if not checksum:
        raise BackupError("No se pudo calcular la huella del respaldo")

    backup_root.mkdir(parents=True, exist_ok=True)
    backup_name = next_backup_name(backup_root)
    backup_path = backup_root / backup_name
    metadata_path = backup_root / f"{backup_name}.json"

    try:
        shutil.copytree(source, backup_path, symlinks=True)
        copied_checksum = calculate_tree_sha256(backup_path)
        if copied_checksum != checksum:
            raise BackupError("La copia del respaldo no coincide con el origen")

        metadata = {
            "schema_version": 1,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "component_id": component_id,
            "component_name": component_name,
            "integration_id": integration_id,
            "reason": reason,
            "version": version,
            "sha256": checksum,
        }
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception:
        shutil.rmtree(backup_path, ignore_errors=True)
        metadata_path.unlink(missing_ok=True)
        raise

    protected = set(protected_names or set())
    protected.add(backup_name)
    deleted_count, errors = prune_backups(
        backup_root,
        normalize_backup_limit(max_backups),
        protected,
    )

    if deleted_count:
        log("INFO", f"Respaldos antiguos eliminados: {deleted_count}")
    for error in errors:
        log("WARNING", error)

    return backup_path


def load_integration_definition(
    catalog_path: Path,
    component_id: str,
) -> IntegrationDefinition:
    data = read_json(catalog_path)
    components = data.get("components")
    if not isinstance(components, list):
        raise BackupError("El catálogo no contiene una lista de componentes")

    for item in components:
        if not isinstance(item, dict) or item.get("id") != component_id:
            continue
        if item.get("type") != "integration":
            raise BackupError("El componente seleccionado no es una integración")

        name = item.get("name")
        integration_id = item.get("integration_id")
        if not isinstance(name, str) or not name.strip():
            raise BackupError("El componente no tiene un nombre válido")
        if not isinstance(integration_id, str) or not integration_id.strip():
            raise BackupError("El componente no tiene integration_id válido")

        return IntegrationDefinition(
            component_id=component_id,
            name=name.strip(),
            integration_id=integration_id.strip(),
        )

    raise BackupError(f"No existe la integración {component_id!r} en el catálogo")


def select_backup(backup_root: Path, requested: str) -> Path:
    backups = list_backup_directories(backup_root)
    if not backups:
        raise BackupError("No existen respaldos disponibles")

    requested = requested.strip() or "latest"
    if requested == "latest":
        return backups[0]

    if not BACKUP_NAME_PATTERN.fullmatch(requested):
        raise BackupError(
            "restore_backup debe ser 'latest' o un nombre YYYYMMDD-HHMMSS"
        )

    candidate = backup_root / requested
    if not candidate.is_dir():
        raise BackupError(f"No existe el respaldo {requested}")

    return candidate


def validate_backup(
    backup_path: Path,
    definition: IntegrationDefinition,
) -> tuple[str, str, str]:
    version = read_manifest_version(backup_path / "manifest.json")
    if not version:
        raise BackupError("El respaldo no contiene un manifest.json válido")

    checksum = calculate_tree_sha256(backup_path)
    if not checksum:
        raise BackupError("No se pudo calcular la huella del respaldo")

    metadata_path = backup_path.with_suffix(".json")
    metadata_status = "LEGACY"

    if metadata_path.is_file():
        metadata = read_json(metadata_path)
        if metadata.get("schema_version") != 1:
            raise BackupError("Los metadatos del respaldo no son compatibles")
        if metadata.get("component_id") != definition.component_id:
            raise BackupError("El respaldo pertenece a otro componente")
        if metadata.get("integration_id") != definition.integration_id:
            raise BackupError("El respaldo pertenece a otra integración")
        if metadata.get("version") != version:
            raise BackupError("La versión del respaldo no coincide con sus metadatos")
        expected_checksum = metadata.get("sha256")
        if expected_checksum != checksum:
            raise BackupError("La huella del respaldo no coincide con sus metadatos")
        metadata_status = "VALIDADO"

    return version, checksum, metadata_status


def prune_restore_reports(report_dir: Path) -> None:
    reports = sorted(
        (
            path
            for path in report_dir.glob("restore-*.txt")
            if path.is_file()
        ),
        key=lambda path: path.name,
        reverse=True,
    )

    for path in reports[MAX_RESTORE_REPORTS:]:
        try:
            path.unlink()
        except OSError as error:
            log("WARNING", f"No se pudo eliminar {path.name}: {error}")


def write_restore_report(
    *,
    definition: IntegrationDefinition,
    selected_backup: Path,
    previous_version: str,
    restored_version: str,
    restored_checksum: str,
    metadata_status: str,
    safety_backup: Path | None,
    result: str,
    detail: str,
) -> Path:
    report_dir = DEFAULT_RESTORE_REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now().astimezone()
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    report_path = report_dir / f"restore-{timestamp}.txt"
    latest_path = report_dir / "latest.txt"

    lines = [
        "SMART HOME UI MANAGER",
        "RESTAURACIÓN MANUAL DE RESPALDO",
        "=" * 68,
        f"Fecha: {now.strftime('%Y-%m-%d %H:%M:%S %z')}",
        f"Resultado: {result}",
        "Reinicio de Home Assistant Core: REQUERIDO",
        "",
        "INTEGRACIÓN",
        "-" * 68,
        f"Componente: {definition.name}",
        f"ID de catálogo: {definition.component_id}",
        f"Dominio: {definition.integration_id}",
        f"Respaldo seleccionado: {selected_backup.name}",
        f"Metadatos: {metadata_status}",
        f"Versión anterior: {previous_version or '-'}",
        f"Versión restaurada: {restored_version or '-'}",
        f"SHA-256 restaurada: {restored_checksum or '-'}",
        (
            f"Respaldo de seguridad previo: {safety_backup.name}"
            if safety_backup is not None
            else "Respaldo de seguridad previo: no aplica"
        ),
        f"Detalle: {detail}",
        "",
        "ADVERTENCIA",
        "-" * 68,
        (
            "El mantenimiento normal volverá a aplicar la versión aprobada en "
            "components.json. Antes de ejecutarlo, desactiva temporalmente el "
            "componente o publica un catálogo con la versión restaurada."
        ),
        "",
    ]

    content = "\n".join(lines)
    report_path.write_text(content, encoding="utf-8")
    latest_path.write_text(content, encoding="utf-8")
    prune_restore_reports(report_dir)
    return report_path


def restore_from_options(catalog_path: Path) -> int:
    options = read_options()
    component_id = str(options.get("restore_component", "")).strip()
    requested_backup = str(options.get("restore_backup", "latest")).strip()
    max_backups = configured_backup_limit(options)

    if not component_id:
        raise BackupError("restore_component está vacío")

    definition = load_integration_definition(catalog_path, component_id)
    destination = CONFIG_ROOT / "custom_components" / definition.integration_id
    backup_root = CONFIG_ROOT / "ui-manager" / "backups" / definition.integration_id
    state_file = CONFIG_ROOT / "ui-manager" / "state" / f"{definition.integration_id}.version"
    selected_backup = select_backup(backup_root, requested_backup)
    restored_version, restored_checksum, metadata_status = validate_backup(
        selected_backup,
        definition,
    )

    previous_version = read_manifest_version(destination / "manifest.json")
    staging_dir = destination.with_name(destination.name + ".ui_manager_restore")
    previous_dir = destination.with_name(destination.name + ".ui_manager_previous")
    safety_backup: Path | None = None

    shutil.rmtree(staging_dir, ignore_errors=True)
    shutil.rmtree(previous_dir, ignore_errors=True)
    shutil.copytree(selected_backup, staging_dir, symlinks=True)

    if calculate_tree_sha256(staging_dir) != restored_checksum:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise BackupError("La copia temporal del respaldo no coincide con el origen")

    if destination.is_dir():
        safety_backup = create_integration_backup(
            destination,
            backup_root,
            component_id=definition.component_id,
            component_name=definition.name,
            integration_id=definition.integration_id,
            reason="pre_restore",
            max_backups=max_backups,
            protected_names={selected_backup.name},
        )
        destination.rename(previous_dir)

    try:
        staging_dir.rename(destination)
    except OSError as error:
        shutil.rmtree(destination, ignore_errors=True)
        if previous_dir.is_dir():
            previous_dir.rename(destination)
        raise BackupError(f"No se pudo activar el respaldo: {error}") from error

    final_checksum = calculate_tree_sha256(destination)
    if final_checksum != restored_checksum:
        shutil.rmtree(destination, ignore_errors=True)
        if previous_dir.is_dir():
            previous_dir.rename(destination)
        raise BackupError("La integración restaurada no conserva la huella esperada")

    shutil.rmtree(previous_dir, ignore_errors=True)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(restored_version + "\n", encoding="utf-8")

    prune_backups(
        backup_root,
        max_backups,
        protected_names={selected_backup.name},
    )

    report_path = write_restore_report(
        definition=definition,
        selected_backup=selected_backup,
        previous_version=previous_version,
        restored_version=restored_version,
        restored_checksum=restored_checksum,
        metadata_status=metadata_status,
        safety_backup=safety_backup,
        result="CORRECTO",
        detail="El respaldo fue restaurado correctamente",
    )

    log("INFO", f"Integración restaurada: {definition.name} {restored_version}")
    log("INFO", f"Reporte guardado: {report_path}")
    log("WARNING", "Es necesario reiniciar Home Assistant Core")
    return 0


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    catalog_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_CATALOG

    if command != "restore":
        print("Uso: backup_manager.py restore [components.json]", file=sys.stderr)
        return 2

    try:
        return restore_from_options(catalog_path)
    except (BackupError, OSError) as error:
        log("ERROR", str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
