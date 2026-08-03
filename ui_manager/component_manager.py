#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from checksum_utils import calculate_file_sha256, calculate_tree_sha256
from backup_manager import (
    BackupError,
    configured_backup_limit,
    create_integration_backup,
    prune_backups,
)


DEFAULT_CATALOG = Path("/components.json")
DEFAULT_RESULTS = Path("/tmp/ui_manager_results.tsv")
DEFAULT_STATE = Path("/tmp/ui_manager_state.json")
OPTIONS_FILE = Path(os.environ.get("UI_MANAGER_OPTIONS_FILE", "/data/options.json"))
CONFIG_ROOT = Path(os.environ.get("UI_MANAGER_CONFIG_ROOT", "/config"))
REGISTER_RESOURCE = Path(
    os.environ.get("UI_MANAGER_REGISTER_RESOURCE", "/register_resource.py")
)
SKIP_RESOURCE_REGISTRATION = (
    os.environ.get("UI_MANAGER_SKIP_RESOURCE_REGISTRATION", "false").lower()
    == "true"
)

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID_PATTERN = re.compile(r"^[a-z0-9_]+$")


@dataclass(frozen=True)
class Component:
    component_id: str
    name: str
    option: str
    component_type: str
    version: str
    url: str
    sha256: str
    install_dir: str = ""
    filename: str = ""
    resource_url: str = ""
    resource_type: str = "module"
    integration_id: str = ""
    source_folder: str = ""


class CatalogError(ValueError):
    pass


def log(level: str, message: str) -> None:
    print(f"[manager] {level}: {message}", flush=True)


def sanitize_field(value: object) -> str:
    return str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ")


def record_result(
    results_file: Path,
    component: Component,
    previous_version: str,
    final_version: str,
    status_value: str,
    message: str,
) -> None:
    fields = [
        component.component_id,
        component.name,
        component.component_type,
        component.version,
        previous_version,
        final_version,
        status_value,
        message,
    ]

    results_file.parent.mkdir(parents=True, exist_ok=True)
    with results_file.open("a", encoding="utf-8") as file:
        file.write("\t".join(sanitize_field(field) for field in fields))
        file.write("\n")


def read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        raise CatalogError(f"No se pudo leer {path}: {error}") from error

    if not isinstance(data, dict):
        raise CatalogError(f"{path} debe contener un objeto JSON")

    return data


def read_options() -> dict[str, Any]:
    try:
        with OPTIONS_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}

    return data if isinstance(data, dict) else {}


def required_text(item: dict[str, Any], key: str, component_id: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CatalogError(
            f"El componente {component_id!r} requiere el campo {key!r}"
        )
    return value.strip()


def validate_config_path(path_text: str, field_name: str, component_id: str) -> None:
    path = Path(path_text)
    if not path.is_absolute() or not path_text.startswith("/config/"):
        raise CatalogError(
            f"{component_id}: {field_name} debe estar dentro de /config"
        )


def load_catalog(path: Path) -> tuple[str, list[Component]]:
    data = read_json(path)

    if data.get("schema_version") != 1:
        raise CatalogError("schema_version debe ser 1")

    catalog_version = data.get("catalog_version")
    if not isinstance(catalog_version, str) or not catalog_version.strip():
        raise CatalogError("catalog_version es obligatorio")

    raw_components = data.get("components")
    if not isinstance(raw_components, list) or not raw_components:
        raise CatalogError("components debe ser una lista no vacía")

    components: list[Component] = []
    seen_ids: set[str] = set()
    seen_options: set[str] = set()

    for index, raw_item in enumerate(raw_components, start=1):
        if not isinstance(raw_item, dict):
            raise CatalogError(f"components[{index}] debe ser un objeto")

        component_id = required_text(raw_item, "id", f"posición {index}")
        if not SAFE_ID_PATTERN.fullmatch(component_id):
            raise CatalogError(f"ID de componente no válido: {component_id}")
        if component_id in seen_ids:
            raise CatalogError(f"ID duplicado: {component_id}")
        seen_ids.add(component_id)

        name = required_text(raw_item, "name", component_id)
        option = required_text(raw_item, "option", component_id)
        if not SAFE_ID_PATTERN.fullmatch(option):
            raise CatalogError(f"Opción no válida para {component_id}: {option}")
        if option in seen_options:
            raise CatalogError(f"Opción duplicada en el catálogo: {option}")
        seen_options.add(option)

        component_type = required_text(raw_item, "type", component_id)
        if component_type not in {"frontend", "integration"}:
            raise CatalogError(
                f"Tipo no válido para {component_id}: {component_type}"
            )

        version = required_text(raw_item, "version", component_id)
        url = required_text(raw_item, "url", component_id)
        if not url.startswith("https://"):
            raise CatalogError(f"La URL de {component_id} debe usar HTTPS")

        sha256 = required_text(raw_item, "sha256", component_id).lower()
        if not SHA256_PATTERN.fullmatch(sha256):
            raise CatalogError(f"SHA-256 no válido para {component_id}")

        common = {
            "component_id": component_id,
            "name": name,
            "option": option,
            "component_type": component_type,
            "version": version,
            "url": url,
            "sha256": sha256,
        }

        if component_type == "frontend":
            install_dir = required_text(raw_item, "install_dir", component_id)
            validate_config_path(install_dir, "install_dir", component_id)

            filename = required_text(raw_item, "filename", component_id)
            if Path(filename).name != filename:
                raise CatalogError(f"filename no válido para {component_id}")

            resource_url = required_text(raw_item, "resource_url", component_id)
            if not resource_url.startswith("/local/"):
                raise CatalogError(
                    f"resource_url de {component_id} debe comenzar con /local/"
                )

            resource_type = str(raw_item.get("resource_type", "module")).strip()
            if resource_type not in {"module", "css"}:
                raise CatalogError(
                    f"resource_type no válido para {component_id}: {resource_type}"
                )

            components.append(
                Component(
                    **common,
                    install_dir=install_dir,
                    filename=filename,
                    resource_url=resource_url,
                    resource_type=resource_type,
                )
            )
            continue

        integration_id = required_text(raw_item, "integration_id", component_id)
        source_folder = required_text(raw_item, "source_folder", component_id)
        if not SAFE_ID_PATTERN.fullmatch(integration_id):
            raise CatalogError(
                f"integration_id no válido para {component_id}: {integration_id}"
            )
        if not SAFE_ID_PATTERN.fullmatch(source_folder):
            raise CatalogError(
                f"source_folder no válido para {component_id}: {source_folder}"
            )

        components.append(
            Component(
                **common,
                integration_id=integration_id,
                source_folder=source_folder,
            )
        )

    return catalog_version.strip(), components


def map_config_path(path_text: str) -> Path:
    path = Path(path_text)
    relative = path.relative_to("/config")
    return CONFIG_ROOT / relative


def read_version_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def read_manifest_version(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return ""

    version = data.get("version") if isinstance(data, dict) else ""
    return version.strip() if isinstance(version, str) else ""


def download(url: str, destination: Path) -> bool:
    command = [
        "curl",
        "--fail",
        "--location",
        "--silent",
        "--show-error",
        "--retry",
        "3",
        "--retry-delay",
        "2",
        "--connect-timeout",
        "20",
        "--max-time",
        "300",
        "--user-agent",
        "Smart-Home-UI-Manager/0.4.0",
        url,
        "--output",
        str(destination),
    ]
    return subprocess.run(command, check=False).returncode == 0


def register_resource(component: Component) -> bool:
    if SKIP_RESOURCE_REGISTRATION:
        return True

    resource_with_version = f"{component.resource_url}?v={component.version}"
    command = [
        sys.executable,
        str(REGISTER_RESOURCE),
        resource_with_version,
        component.resource_url,
        component.resource_type,
    ]
    return subprocess.run(command, check=False).returncode == 0


def install_frontend(component: Component, results_file: Path) -> bool:
    install_dir = map_config_path(component.install_dir)
    component_file = install_dir / component.filename
    version_file = install_dir / "version"

    try:
        install_dir.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        log("ERROR", f"No se pudo crear la carpeta de {component.name}: {error}")
        record_result(
            results_file,
            component,
            "-",
            "-",
            "ERROR",
            "No se pudo crear la carpeta de instalación",
        )
        return False

    had_existing_file = component_file.is_file() and component_file.stat().st_size > 0
    previous_version = read_version_file(version_file)
    if not previous_version:
        previous_version = "desconocida" if had_existing_file else "-"

    previous_checksum = (
        calculate_file_sha256(component_file) if had_existing_file else ""
    )

    if previous_checksum == component.sha256:
        result_status = "VERIFICADO"
        if previous_version != component.version:
            try:
                version_file.write_text(component.version + "\n", encoding="utf-8")
                result_status = "REPARADO"
            except OSError as error:
                log(
                    "ERROR",
                    f"No se pudo corregir la versión registrada de {component.name}: {error}",
                )
                record_result(
                    results_file,
                    component,
                    previous_version,
                    previous_version,
                    "ERROR",
                    "La huella coincide, pero no se pudo corregir el archivo de versión",
                )
                return False

        log("INFO", f"{component.name} v{component.version} ya está instalado")
        log("INFO", f"Integridad SHA-256 de {component.name} verificada")
        log("INFO", f"Comprobando recurso de {component.name}")

        if not register_resource(component):
            log("ERROR", f"No se pudo comprobar el recurso de {component.name}")
            record_result(
                results_file,
                component,
                previous_version,
                component.version,
                "ERROR",
                "La huella coincide, pero no se pudo registrar el recurso",
            )
            return False

        log("INFO", f"Recurso de {component.name} configurado correctamente")
        record_result(
            results_file,
            component,
            previous_version,
            component.version,
            result_status,
            "Archivo, huella SHA-256 y recurso comprobados correctamente",
        )
        return True

    if had_existing_file:
        log(
            "WARNING",
            f"La huella instalada de {component.name} no coincide con la aprobada",
        )
        log("WARNING", f"Se intentará reparar {component.name}")

    log("INFO", f"Descargando {component.name} v{component.version}")

    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{component.filename}.ui-manager.",
            dir=install_dir,
        )
        os.close(descriptor)
        temporary_path = Path(temporary_name)

        if not download(component.url, temporary_path):
            raise RuntimeError("Falló la descarga")

        if temporary_path.stat().st_size == 0:
            raise RuntimeError("La descarga produjo un archivo vacío")

        downloaded_checksum = calculate_file_sha256(temporary_path)
        if downloaded_checksum != component.sha256:
            raise RuntimeError(
                "Huella SHA-256 inválida: "
                f"esperada {component.sha256}, recibida "
                f"{downloaded_checksum or 'no disponible'}"
            )

        temporary_path.chmod(0o644)
        os.replace(temporary_path, component_file)
        temporary_path = None
        version_file.write_text(component.version + "\n", encoding="utf-8")
    except (OSError, RuntimeError) as error:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        log("ERROR", f"No se pudo instalar {component.name}: {error}")
        record_result(
            results_file,
            component,
            previous_version,
            previous_version,
            "ERROR",
            f"{error}; se conservó el archivo anterior",
        )
        return False

    log("INFO", f"{component.name} v{component.version} instalado correctamente")
    log("INFO", f"Integridad SHA-256 de {component.name} verificada")
    log("INFO", f"Comprobando recurso de {component.name}")

    if not register_resource(component):
        log("ERROR", f"No se pudo registrar el recurso de {component.name}")
        record_result(
            results_file,
            component,
            previous_version,
            component.version,
            "ERROR",
            "El archivo se instaló, pero falló el registro del recurso",
        )
        return False

    log("INFO", f"Recurso de {component.name} configurado correctamente")

    if not had_existing_file:
        status_value = "INSTALADO"
    elif previous_version == component.version:
        status_value = "REPARADO"
    else:
        status_value = "ACTUALIZADO"

    record_result(
        results_file,
        component,
        previous_version,
        component.version,
        status_value,
        "Componente, huella SHA-256 y recurso configurados correctamente",
    )
    return True


def safe_extract_zip(archive_path: Path, destination: Path) -> None:
    destination_resolved = destination.resolve()

    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            member_path = destination / info.filename
            member_resolved = member_path.resolve()

            if not member_resolved.is_relative_to(destination_resolved):
                raise RuntimeError("El ZIP contiene una ruta insegura")

            file_mode = (info.external_attr >> 16) & 0o170000
            if file_mode == stat.S_IFLNK:
                raise RuntimeError("El ZIP contiene enlaces simbólicos no permitidos")

            if info.is_dir():
                member_path.mkdir(parents=True, exist_ok=True)
                continue

            member_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, member_path.open("wb") as target:
                shutil.copyfileobj(source, target)


def find_integration_source(extracted_root: Path, source_folder: str) -> Path | None:
    direct_manifest = extracted_root / "manifest.json"
    if direct_manifest.is_file():
        return extracted_root

    candidates: list[Path] = []
    for path in extracted_root.rglob(source_folder):
        if not path.is_dir() or not (path / "manifest.json").is_file():
            continue
        if path.parent.name == "custom_components":
            candidates.append(path)

    if not candidates:
        return None

    return sorted(candidates, key=lambda item: item.as_posix())[0]


def install_integration(component: Component, results_file: Path) -> tuple[bool, bool]:
    destination = CONFIG_ROOT / "custom_components" / component.integration_id
    state_dir = CONFIG_ROOT / "ui-manager" / "state"
    version_file = state_dir / f"{component.integration_id}.version"
    backup_root = CONFIG_ROOT / "ui-manager" / "backups" / component.integration_id
    staging_dir = destination.with_name(destination.name + ".ui_manager_new")
    previous_dir = destination.with_name(destination.name + ".ui_manager_previous")

    deleted_backups, cleanup_errors = prune_backups(
        backup_root,
        configured_backup_limit(),
    )
    if deleted_backups:
        log(
            "INFO",
            f"{component.name}: respaldos antiguos eliminados: {deleted_backups}",
        )
    for cleanup_error in cleanup_errors:
        log("WARNING", f"{component.name}: {cleanup_error}")

    had_existing_destination = destination.is_dir()
    previous_version = read_manifest_version(destination / "manifest.json")
    if not previous_version:
        previous_version = "desconocida" if had_existing_destination else "-"

    previous_checksum = (
        calculate_tree_sha256(destination) if had_existing_destination else ""
    )

    if (
        previous_version == component.version
        and previous_checksum == component.sha256
    ):
        log("INFO", f"{component.name} v{component.version} ya está instalado")
        log("INFO", f"Integridad SHA-256 de {component.name} verificada")
        record_result(
            results_file,
            component,
            previous_version,
            component.version,
            "VERIFICADO",
            "Manifest, versión y huella SHA-256 comprobados correctamente",
        )
        return True, False

    if had_existing_destination and previous_checksum != component.sha256:
        log(
            "WARNING",
            f"La huella instalada de {component.name} no coincide con la aprobada",
        )
        log("WARNING", f"Se intentará reparar {component.name}")

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        state_dir.mkdir(parents=True, exist_ok=True)
        backup_root.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        log("ERROR", f"No se pudieron crear carpetas para {component.name}: {error}")
        record_result(
            results_file,
            component,
            previous_version,
            previous_version,
            "ERROR",
            "No se pudieron crear las carpetas necesarias",
        )
        return False, False

    log("INFO", f"Descargando {component.name} v{component.version}")

    try:
        with tempfile.TemporaryDirectory(prefix="ui-manager-") as temporary_name:
            temporary_dir = Path(temporary_name)
            archive_file = temporary_dir / f"{component.integration_id}.zip"
            extracted_root = temporary_dir / "extracted"
            extracted_root.mkdir()

            if not download(component.url, archive_file):
                raise RuntimeError("Falló la descarga")
            if archive_file.stat().st_size == 0:
                raise RuntimeError("La descarga produjo un archivo vacío")
            if not zipfile.is_zipfile(archive_file):
                raise RuntimeError("El archivo descargado no es un ZIP válido")

            safe_extract_zip(archive_file, extracted_root)
            source_dir = find_integration_source(
                extracted_root,
                component.source_folder,
            )
            if source_dir is None:
                raise RuntimeError("El ZIP no contiene la estructura esperada")

            package_version = read_manifest_version(source_dir / "manifest.json")
            if package_version != component.version:
                raise RuntimeError(
                    "Versión interna inválida: "
                    f"esperada {component.version}, recibida "
                    f"{package_version or 'vacía'}"
                )

            package_checksum = calculate_tree_sha256(source_dir)
            if package_checksum != component.sha256:
                raise RuntimeError(
                    "Huella SHA-256 inválida: "
                    f"esperada {component.sha256}, recibida "
                    f"{package_checksum or 'no disponible'}"
                )

            shutil.rmtree(staging_dir, ignore_errors=True)
            shutil.rmtree(previous_dir, ignore_errors=True)
            shutil.copytree(source_dir, staging_dir, symlinks=True)

            backup_path: Path | None = None
            if had_existing_destination:
                backup_reason = (
                    "pre_repair"
                    if previous_version == component.version
                    and previous_checksum != component.sha256
                    else "pre_update"
                )
                backup_path = create_integration_backup(
                    destination,
                    backup_root,
                    component_id=component.component_id,
                    component_name=component.name,
                    integration_id=component.integration_id,
                    reason=backup_reason,
                    expected_checksum=(
                        component.sha256
                        if backup_reason == "pre_repair"
                        else ""
                    ),
                    max_backups=configured_backup_limit(),
                )
                log(
                    "INFO",
                    f"Respaldo creado: {backup_path} ({backup_reason})",
                )
                destination.rename(previous_dir)

            try:
                staging_dir.rename(destination)
            except OSError:
                shutil.rmtree(destination, ignore_errors=True)
                if previous_dir.is_dir():
                    previous_dir.rename(destination)
                    log("WARNING", f"Se restauró la versión anterior de {component.name}")
                raise

            shutil.rmtree(previous_dir, ignore_errors=True)

            try:
                version_file.write_text(
                    component.version + "\n",
                    encoding="utf-8",
                )
            except OSError as error:
                log(
                    "WARNING",
                    "La integración quedó instalada, pero no se pudo "
                    f"guardar el archivo de estado de {component.name}: {error}",
                )

    except (OSError, RuntimeError, zipfile.BadZipFile, BackupError) as error:
        shutil.rmtree(staging_dir, ignore_errors=True)
        if previous_dir.is_dir() and not destination.exists():
            try:
                previous_dir.rename(destination)
            except OSError:
                pass
        log("ERROR", f"No se pudo instalar {component.name}: {error}")
        record_result(
            results_file,
            component,
            previous_version,
            previous_version,
            "ERROR",
            f"{error}; se conservó la versión anterior",
        )
        return False, False

    if not had_existing_destination:
        status_value = "INSTALADO"
    elif previous_version == component.version:
        status_value = "REPARADO"
    else:
        status_value = "ACTUALIZADO"

    log("INFO", f"{component.name} v{component.version} instalado correctamente")
    log("INFO", f"Integridad SHA-256 de {component.name} verificada")
    record_result(
        results_file,
        component,
        previous_version,
        component.version,
        status_value,
        "Integración, manifest y huella SHA-256 validados correctamente",
    )
    return True, True


def write_state(
    state_file: Path,
    catalog_version: str,
    integration_changed: bool,
    errors: int,
) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps(
            {
                "catalog_version": catalog_version,
                "integration_changed": integration_changed,
                "errors": errors,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "--validate-only":
        catalog_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_CATALOG
        catalog_version, components = load_catalog(catalog_path)
        print(
            f"Catálogo válido: {catalog_version}; componentes: {len(components)}"
        )
        return 0

    catalog_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CATALOG
    results_file = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_RESULTS
    state_file = Path(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_STATE

    results_file.parent.mkdir(parents=True, exist_ok=True)
    results_file.write_text("", encoding="utf-8")

    try:
        catalog_version, components = load_catalog(catalog_path)
    except CatalogError as error:
        log("ERROR", f"Catálogo inválido: {error}")
        write_state(state_file, "desconocido", False, 1)
        return 1

    options = read_options()
    integration_changed = False
    errors = 0

    log("INFO", f"Catálogo cargado: {catalog_version}")
    log("INFO", f"Componentes definidos: {len(components)}")

    for component in components:
        enabled = options.get(component.option, True) is True
        if not enabled:
            log("INFO", f"{component.name} está desactivado en la configuración")
            record_result(
                results_file,
                component,
                "-",
                "-",
                "OMITIDO",
                "Componente desactivado en la configuración",
            )
            continue

        try:
            if component.component_type == "frontend":
                success = install_frontend(component, results_file)
                changed = False
            else:
                success, changed = install_integration(component, results_file)
                integration_changed = integration_changed or changed
        except Exception as error:  # noqa: BLE001 - evita detener otros componentes
            log("ERROR", f"Fallo inesperado en {component.name}: {error}")
            record_result(
                results_file,
                component,
                "desconocida",
                "desconocida",
                "ERROR",
                f"Fallo inesperado: {error}",
            )
            success = False

        if not success:
            errors += 1

    try:
        write_state(
            state_file,
            catalog_version,
            integration_changed,
            errors,
        )
    except OSError as error:
        log("ERROR", f"No se pudo guardar el estado del mantenimiento: {error}")
        return 1

    return 0 if errors == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
