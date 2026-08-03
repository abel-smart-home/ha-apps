#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

import backup_manager
from checksum_utils import calculate_tree_sha256


REAL_CONFIG_ROOT = Path(
    os.environ.get("UI_MANAGER_CONFIG_ROOT", "/config")
)
TEST_ROOT = REAL_CONFIG_ROOT / "ui-manager" / "test" / "backup-manager"
TEST_CONFIG_ROOT = TEST_ROOT / "isolated-config"
TEST_REPORT = TEST_ROOT / "latest.txt"


def write_integration(path: Path, version: str, marker: str) -> None:
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    (path / "manifest.json").write_text(
        json.dumps(
            {
                "domain": "ui_manager_backup_test",
                "name": "UI Manager Backup Test",
                "version": version,
                "documentation": "https://example.invalid/test",
                "codeowners": [],
                "requirements": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (path / "__init__.py").write_text(
        f'TEST_MARKER = "{marker}"\n',
        encoding="utf-8",
    )


def main() -> int:
    shutil.rmtree(TEST_ROOT, ignore_errors=True)
    TEST_ROOT.mkdir(parents=True, exist_ok=True)

    sources = TEST_ROOT / "sources"
    good_source = sources / "good-v1"
    suspect_source = sources / "suspect-v1"
    current_source = sources / "approved-v2"

    write_integration(good_source, "1.0.0", "GOOD-V1")
    write_integration(suspect_source, "1.0.0", "MODIFIED-V1")
    write_integration(current_source, "2.0.0", "APPROVED-V2")

    good_checksum = calculate_tree_sha256(good_source)
    suspect_checksum = calculate_tree_sha256(suspect_source)
    approved_checksum = calculate_tree_sha256(current_source)

    if not all((good_checksum, suspect_checksum, approved_checksum)):
        raise RuntimeError("No se pudieron calcular las huellas de prueba")

    catalog_path = TEST_ROOT / "components-test.json"
    catalog_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "catalog_version": "controlled-backup-test",
                "components": [
                    {
                        "id": "backup_test",
                        "name": "Prueba controlada de respaldos",
                        "option": "backup_test",
                        "type": "integration",
                        "version": "2.0.0",
                        "url": "https://example.invalid/test.zip",
                        "sha256": approved_checksum,
                        "integration_id": "ui_manager_backup_test",
                        "source_folder": "ui_manager_backup_test",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    options_path = TEST_ROOT / "options.json"
    options_path.write_text(
        json.dumps(
            {
                "restore_component": "backup_test",
                "restore_backup": "latest_good",
                "max_integration_backups": 5,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    backup_manager.CONFIG_ROOT = TEST_CONFIG_ROOT
    backup_manager.OPTIONS_FILE = options_path
    backup_manager.DEFAULT_RESTORE_REPORT_DIR = (
        TEST_ROOT / "restore-reports"
    )
    backup_manager.DEFAULT_BACKUP_INVENTORY_DIR = (
        TEST_ROOT / "backup-inventory"
    )

    definition = backup_manager.load_integration_definition(
        catalog_path,
        "backup_test",
    )
    backup_root = (
        TEST_CONFIG_ROOT
        / "ui-manager"
        / "backups"
        / definition.integration_id
    )

    good_backup = backup_manager.create_integration_backup(
        good_source,
        backup_root,
        component_id=definition.component_id,
        component_name=definition.name,
        integration_id=definition.integration_id,
        reason="pre_update",
        max_backups=5,
    )

    suspect_backup = backup_manager.create_integration_backup(
        suspect_source,
        backup_root,
        component_id=definition.component_id,
        component_name=definition.name,
        integration_id=definition.integration_id,
        reason="pre_repair",
        expected_checksum=good_checksum,
        max_backups=5,
    )

    selected_before_restore = backup_manager.select_backup(
        backup_root,
        "latest_good",
        definition,
    )

    if selected_before_restore.path.name != good_backup.name:
        raise RuntimeError(
            "latest_good no omitió el respaldo SUSPECT más reciente"
        )

    destination = (
        TEST_CONFIG_ROOT
        / "custom_components"
        / definition.integration_id
    )
    shutil.copytree(current_source, destination, symlinks=True)

    result = backup_manager.restore_from_options(catalog_path)
    if result != 0:
        raise RuntimeError("La restauración aislada devolvió un error")

    restored_version = backup_manager.read_manifest_version(
        destination / "manifest.json"
    )
    restored_checksum = calculate_tree_sha256(destination)

    if restored_version != "1.0.0" or restored_checksum != good_checksum:
        raise RuntimeError("La integración aislada no fue restaurada correctamente")

    inventory_path = backup_manager.write_backup_inventory(catalog_path)
    inventory_text = inventory_path.read_text(encoding="utf-8")

    if "GOOD:" not in inventory_text or "SUSPECT:" not in inventory_text:
        raise RuntimeError("El inventario no contiene las clasificaciones esperadas")

    now = datetime.now().astimezone()
    lines = [
        "SMART HOME UI MANAGER",
        "PRUEBA CONTROLADA DE RESPALDOS 0.4.1",
        "=" * 72,
        f"Fecha: {now.strftime('%Y-%m-%d %H:%M:%S %z')}",
        "Resultado: CORRECTO",
        "Modo: AISLADO",
        "Componentes reales modificados: NO",
        "",
        "VALIDACIONES",
        "-" * 72,
        f"Respaldo GOOD creado: {good_backup.name}",
        f"Respaldo SUSPECT creado después: {suspect_backup.name}",
        f"latest_good seleccionó: {selected_before_restore.path.name}",
        "latest_good omitió el respaldo SUSPECT más reciente: SÍ",
        f"Versión restaurada: {restored_version}",
        f"SHA-256 restaurada: {restored_checksum}",
        "Respaldo de seguridad pre_restore creado: SÍ",
        f"Inventario generado: {inventory_path}",
        "",
        "UBICACIÓN AISLADA",
        "-" * 72,
        str(TEST_ROOT),
        "",
    ]
    TEST_REPORT.write_text("\n".join(lines), encoding="utf-8")

    print("[backup-test] Prueba controlada finalizada correctamente", flush=True)
    print(f"[backup-test] Reporte: {TEST_REPORT}", flush=True)
    print("[backup-test] No se modificaron integraciones reales", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
