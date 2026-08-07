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
DEFAULT_BACKUP_INVENTORY_DIR = (
    CONFIG_ROOT / "ui-manager" / "backups" / "inventory"
)
MAX_RESTORE_REPORTS = 20
MAX_INVENTORY_REPORTS = 20
DEFAULT_BACKUP_LIMIT = 5
MIN_BACKUP_LIMIT = 1
MAX_BACKUP_LIMIT = 20
BACKUP_NAME_PATTERN = re.compile(r"^\d{8}-\d{6}(?:-\d{2})?$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

HEALTH_GOOD = "GOOD"
HEALTH_SUSPECT = "SUSPECT"
HEALTH_UNKNOWN = "UNKNOWN"
VALID_HEALTH = {HEALTH_GOOD, HEALTH_SUSPECT, HEALTH_UNKNOWN}


@dataclass(frozen=True)
class IntegrationDefinition:
    component_id: str
    name: str
    integration_id: str
    approved_version: str
    approved_sha256: str


@dataclass(frozen=True)
class BackupInfo:
    path: Path
    version: str
    checksum: str
    metadata_status: str
    reason: str
    health: str
    created_at: str


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


def read_json_optional(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}

    return data if isinstance(data, dict) else {}


def read_options(path: Path | None = None) -> dict[str, Any]:
    target = path or OPTIONS_FILE
    return read_json_optional(target)


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
    data = read_json_optional(path)
    version = data.get("version")
    return version.strip() if isinstance(version, str) else ""


def next_backup_name(backup_root: Path) -> str:
    base = datetime.now().strftime("%Y%m%d-%H%M%S")
    if not (backup_root / base).exists() and not (
        backup_root / f"{base}.json"
    ).exists():
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
    backup_path.with_suffix(".json").unlink(missing_ok=True)


def metadata_health(metadata_path: Path) -> str:
    metadata = read_json_optional(metadata_path)
    health = str(metadata.get("health", "")).strip().upper()
    return health if health in VALID_HEALTH else ""


def newest_explicit_good_name(backups: list[Path]) -> str:
    for backup in backups:
        if metadata_health(backup.with_suffix(".json")) == HEALTH_GOOD:
            return backup.name
    return ""


def prune_backups(
    backup_root: Path,
    max_backups: int,
    protected_names: set[str] | None = None,
) -> tuple[int, list[str]]:
    """Conserva el límite y protege el respaldo GOOD más reciente."""
    protected_names = set(protected_names or set())
    backups = list_backup_directories(backup_root)

    latest_good = newest_explicit_good_name(backups)
    if latest_good:
        protected_names.add(latest_good)

    keep: set[str] = {
        path.name for path in backups if path.name in protected_names
    }

    for path in backups:
        if len(keep) >= normalize_backup_limit(max_backups):
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


def classify_new_backup(
    *,
    reason: str,
    checksum: str,
    expected_checksum: str,
) -> str:
    if reason == "pre_repair":
        return HEALTH_SUSPECT
    if reason == "pre_update":
        return HEALTH_GOOD
    if reason == "pre_restore":
        if expected_checksum and checksum == expected_checksum:
            return HEALTH_GOOD
        return HEALTH_UNKNOWN
    return HEALTH_UNKNOWN


def create_integration_backup(
    source: Path,
    backup_root: Path,
    *,
    component_id: str,
    component_name: str,
    integration_id: str,
    reason: str,
    max_backups: int,
    expected_checksum: str = "",
    protected_names: set[str] | None = None,
) -> Path:
    if not source.is_dir():
        raise BackupError(f"La carpeta a respaldar no existe: {source}")

    version = read_manifest_version(source / "manifest.json")
    if not version:
        raise BackupError("La integración a respaldar no tiene un manifest válido")

    checksum = calculate_tree_sha256(source)
    if not checksum:
        raise BackupError("No se pudo calcular la huella del respaldo")

    health = classify_new_backup(
        reason=reason,
        checksum=checksum,
        expected_checksum=expected_checksum,
    )

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
            "schema_version": 2,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "component_id": component_id,
            "component_name": component_name,
            "integration_id": integration_id,
            "reason": reason,
            "health": health,
            "version": version,
            "sha256": checksum,
            "expected_sha256": expected_checksum,
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

    log(
        "INFO",
        f"Respaldo {backup_name} clasificado como {health} ({reason})",
    )
    return backup_path


def load_integration_definitions(catalog_path: Path) -> list[IntegrationDefinition]:
    data = read_json(catalog_path)
    components = data.get("components")
    if not isinstance(components, list):
        raise BackupError("El catálogo no contiene una lista de componentes")

    definitions: list[IntegrationDefinition] = []
    for item in components:
        if not isinstance(item, dict) or item.get("type") != "integration":
            continue

        component_id = item.get("id")
        name = item.get("name")
        integration_id = item.get("integration_id")
        approved_version = item.get("version")
        approved_sha256 = item.get("sha256")

        if not all(
            isinstance(value, str) and value.strip()
            for value in (
                component_id,
                name,
                integration_id,
                approved_version,
                approved_sha256,
            )
        ):
            raise BackupError("Una integración del catálogo tiene datos incompletos")

        approved_sha256 = approved_sha256.strip().lower()
        if not SHA256_PATTERN.fullmatch(approved_sha256):
            raise BackupError(f"SHA-256 inválido para {component_id}")

        definitions.append(
            IntegrationDefinition(
                component_id=component_id.strip(),
                name=name.strip(),
                integration_id=integration_id.strip(),
                approved_version=approved_version.strip(),
                approved_sha256=approved_sha256,
            )
        )

    return definitions


def load_integration_definition(
    catalog_path: Path,
    component_id: str,
) -> IntegrationDefinition:
    for definition in load_integration_definitions(catalog_path):
        if definition.component_id == component_id:
            return definition
    raise BackupError(f"No existe la integración {component_id!r} en el catálogo")


def derive_health(
    *,
    metadata: dict[str, Any],
    checksum: str,
    definition: IntegrationDefinition,
) -> tuple[str, str]:
    if not metadata:
        if checksum == definition.approved_sha256:
            return HEALTH_GOOD, "legacy_match"
        return HEALTH_UNKNOWN, "legacy"

    schema_version = metadata.get("schema_version")
    reason = str(metadata.get("reason", "unknown")).strip() or "unknown"

    if schema_version == 2:
        health = str(metadata.get("health", HEALTH_UNKNOWN)).strip().upper()
        if health not in VALID_HEALTH:
            raise BackupError("La clasificación del respaldo no es válida")
        return health, reason

    if schema_version == 1:
        if reason == "pre_update":
            return HEALTH_GOOD, reason
        if reason == "pre_repair":
            return HEALTH_SUSPECT, reason
        return HEALTH_UNKNOWN, reason

    raise BackupError("Los metadatos del respaldo no son compatibles")


def validate_backup(
    backup_path: Path,
    definition: IntegrationDefinition,
) -> BackupInfo:
    version = read_manifest_version(backup_path / "manifest.json")
    if not version:
        raise BackupError("El respaldo no contiene un manifest.json válido")

    checksum = calculate_tree_sha256(backup_path)
    if not checksum:
        raise BackupError("No se pudo calcular la huella del respaldo")

    metadata_path = backup_path.with_suffix(".json")
    metadata = read_json_optional(metadata_path)
    metadata_status = "LEGACY"
    created_at = ""

    if metadata:
        schema_version = metadata.get("schema_version")
        if schema_version not in {1, 2}:
            raise BackupError("Los metadatos del respaldo no son compatibles")
        if metadata.get("component_id") != definition.component_id:
            raise BackupError("El respaldo pertenece a otro componente")
        if metadata.get("integration_id") != definition.integration_id:
            raise BackupError("El respaldo pertenece a otra integración")
        if metadata.get("version") != version:
            raise BackupError("La versión no coincide con sus metadatos")
        if metadata.get("sha256") != checksum:
            raise BackupError("La huella no coincide con sus metadatos")
        metadata_status = f"VALIDADO-v{schema_version}"
        created_at = str(metadata.get("created_at", ""))

    health, reason = derive_health(
        metadata=metadata,
        checksum=checksum,
        definition=definition,
    )

    return BackupInfo(
        path=backup_path,
        version=version,
        checksum=checksum,
        metadata_status=metadata_status,
        reason=reason,
        health=health,
        created_at=created_at,
    )


def select_backup(
    backup_root: Path,
    requested: str,
    definition: IntegrationDefinition,
) -> BackupInfo:
    backups = list_backup_directories(backup_root)
    if not backups:
        raise BackupError("No existen respaldos disponibles")

    requested = requested.strip() or "latest_good"

    if requested == "latest":
        return validate_backup(backups[0], definition)

    if requested == "latest_good":
        skipped: list[str] = []
        for backup in backups:
            try:
                info = validate_backup(backup, definition)
            except BackupError as error:
                skipped.append(f"{backup.name}: inválido ({error})")
                continue
            if info.health == HEALTH_GOOD:
                for item in skipped:
                    log("WARNING", f"latest_good omitió {item}")
                return info
            skipped.append(f"{backup.name}: {info.health} ({info.reason})")

        detail = "; ".join(skipped) if skipped else "sin candidatos"
        raise BackupError(
            "No existe un respaldo clasificado como GOOD. "
            f"Candidatos revisados: {detail}"
        )

    if not BACKUP_NAME_PATTERN.fullmatch(requested):
        raise BackupError(
            "restore_backup debe ser 'latest_good', 'latest' o un nombre "
            "YYYYMMDD-HHMMSS"
        )

    candidate = backup_root / requested
    if not candidate.is_dir():
        raise BackupError(f"No existe el respaldo {requested}")

    return validate_backup(candidate, definition)


def prune_text_reports(report_dir: Path, pattern: str, limit: int) -> None:
    reports = sorted(
        (path for path in report_dir.glob(pattern) if path.is_file()),
        key=lambda path: path.name,
        reverse=True,
    )
    for path in reports[limit:]:
        try:
            path.unlink()
        except OSError as error:
            log("WARNING", f"No se pudo eliminar {path.name}: {error}")


def write_restore_report(
    *,
    definition: IntegrationDefinition,
    requested_backup: str,
    selected_backup: BackupInfo,
    previous_version: str,
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
        f"Solicitud: {requested_backup}",
        f"Respaldo seleccionado: {selected_backup.path.name}",
        f"Clasificación: {selected_backup.health}",
        f"Motivo del respaldo: {selected_backup.reason}",
        f"Metadatos: {selected_backup.metadata_status}",
        f"Versión anterior: {previous_version or '-'}",
        f"Versión restaurada: {selected_backup.version or '-'}",
        f"SHA-256 restaurada: {selected_backup.checksum or '-'}",
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
    prune_text_reports(report_dir, "restore-*.txt", MAX_RESTORE_REPORTS)
    return report_path


def write_backup_inventory(
    catalog_path: Path,
    report_dir: Path | None = None,
) -> Path:
    definitions = load_integration_definitions(catalog_path)
    target_dir = report_dir or DEFAULT_BACKUP_INVENTORY_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now().astimezone()
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    report_path = target_dir / f"backup-inventory-{timestamp}.txt"
    latest_path = target_dir / "latest.txt"

    lines = [
        "SMART HOME UI MANAGER",
        "INVENTARIO DE RESPALDOS",
        "=" * 76,
        f"Fecha: {now.strftime('%Y-%m-%d %H:%M:%S %z')}",
        f"Límite configurado por integración: {configured_backup_limit()}",
        "",
    ]

    total = 0
    good = 0
    suspect = 0
    unknown = 0
    invalid = 0

    for definition in definitions:
        backup_root = (
            CONFIG_ROOT / "ui-manager" / "backups" / definition.integration_id
        )
        backups = list_backup_directories(backup_root)
        lines.extend(
            [
                definition.name,
                "-" * 76,
                f"ID de catálogo: {definition.component_id}",
                f"Dominio: {definition.integration_id}",
                f"Versión aprobada actual: {definition.approved_version}",
                f"Respaldos encontrados: {len(backups)}",
            ]
        )

        if not backups:
            lines.extend(["  Sin respaldos.", ""])
            continue

        for backup in backups:
            total += 1
            try:
                info = validate_backup(backup, definition)
            except BackupError as error:
                invalid += 1
                lines.extend(
                    [
                        f"  {backup.name}",
                        "    Estado: INVALID",
                        f"    Detalle: {error}",
                    ]
                )
                continue

            if info.health == HEALTH_GOOD:
                good += 1
            elif info.health == HEALTH_SUSPECT:
                suspect += 1
            else:
                unknown += 1

            lines.extend(
                [
                    f"  {backup.name}",
                    f"    Estado: {info.health}",
                    f"    Motivo: {info.reason}",
                    f"    Versión: {info.version}",
                    f"    SHA-256: {info.checksum}",
                    f"    Metadatos: {info.metadata_status}",
                    f"    Creado: {info.created_at or 'no disponible'}",
                ]
            )
        lines.append("")

    lines.extend(
        [
            "RESUMEN",
            "-" * 76,
            f"Total: {total}",
            f"GOOD: {good}",
            f"SUSPECT: {suspect}",
            f"UNKNOWN: {unknown}",
            f"INVALID: {invalid}",
            "",
            "SELECCIÓN RECOMENDADA",
            "-" * 76,
            "Usa restore_backup: latest_good para omitir SUSPECT, UNKNOWN e INVALID.",
            "Un respaldo específico todavía puede seleccionarse por nombre.",
            "",
        ]
    )

    content = "\n".join(lines)
    report_path.write_text(content, encoding="utf-8")
    latest_path.write_text(content, encoding="utf-8")
    prune_text_reports(
        target_dir,
        "backup-inventory-*.txt",
        MAX_INVENTORY_REPORTS,
    )
    return report_path


def restore_from_options(catalog_path: Path) -> int:
    options = read_options()
    component_id = str(options.get("restore_component", "")).strip()
    requested_backup = str(
        options.get("restore_backup", "latest_good")
    ).strip()
    max_backups = configured_backup_limit(options)

    if not component_id:
        raise BackupError("restore_component está vacío")

    definition = load_integration_definition(catalog_path, component_id)
    destination = CONFIG_ROOT / "custom_components" / definition.integration_id
    backup_root = CONFIG_ROOT / "ui-manager" / "backups" / definition.integration_id
    state_file = (
        CONFIG_ROOT / "ui-manager" / "state" / f"{definition.integration_id}.version"
    )
    selected_backup = select_backup(backup_root, requested_backup, definition)

    if selected_backup.health != HEALTH_GOOD and requested_backup in {
        "latest_good",
        "latest",
    }:
        log(
            "WARNING",
            f"El respaldo seleccionado está clasificado como {selected_backup.health}",
        )

    previous_version = read_manifest_version(destination / "manifest.json")
    staging_dir = destination.with_name(destination.name + ".ui_manager_restore")
    previous_dir = destination.with_name(destination.name + ".ui_manager_previous")
    safety_backup: Path | None = None

    shutil.rmtree(staging_dir, ignore_errors=True)
    shutil.rmtree(previous_dir, ignore_errors=True)
    shutil.copytree(selected_backup.path, staging_dir, symlinks=True)

    if calculate_tree_sha256(staging_dir) != selected_backup.checksum:
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
            expected_checksum=definition.approved_sha256,
            max_backups=max_backups,
            protected_names={selected_backup.path.name},
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
    if final_checksum != selected_backup.checksum:
        shutil.rmtree(destination, ignore_errors=True)
        if previous_dir.is_dir():
            previous_dir.rename(destination)
        raise BackupError("La integración restaurada no conserva la huella esperada")

    shutil.rmtree(previous_dir, ignore_errors=True)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(selected_backup.version + "\n", encoding="utf-8")

    prune_backups(
        backup_root,
        max_backups,
        protected_names={selected_backup.path.name},
    )

    report_path = write_restore_report(
        definition=definition,
        requested_backup=requested_backup,
        selected_backup=selected_backup,
        previous_version=previous_version,
        safety_backup=safety_backup,
        result="CORRECTO",
        detail="El respaldo fue restaurado correctamente",
    )

    inventory_path = write_backup_inventory(catalog_path)
    log("INFO", f"Integración restaurada: {definition.name} {selected_backup.version}")
    log("INFO", f"Reporte guardado: {report_path}")
    log("INFO", f"Inventario actualizado: {inventory_path}")
    log("WARNING", "Es necesario reiniciar Home Assistant Core")
    return 0


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    catalog_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_CATALOG

    try:
        if command == "restore":
            return restore_from_options(catalog_path)
        if command == "inventory":
            report_path = write_backup_inventory(catalog_path)
            log("INFO", f"Inventario guardado: {report_path}")
            return 0

        print(
            "Uso: backup_manager.py restore|inventory [components.json]",
            file=sys.stderr,
        )
        return 2
    except (BackupError, OSError) as error:
        log("ERROR", str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
