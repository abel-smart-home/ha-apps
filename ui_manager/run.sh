#!/usr/bin/with-contenv bashio

set -uo pipefail

CATALOG_FILE="/components.json"
RESULTS_FILE="/tmp/ui_manager_results.tsv"
STATE_FILE="/tmp/ui_manager_state.json"


read_state_value() {
    local key="$1"
    local default_value="$2"

    python3 - "${STATE_FILE}" "${key}" "${default_value}" <<'PY'
import json
import sys

path, key, default = sys.argv[1:4]

try:
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)
except Exception:
    print(default)
    raise SystemExit(0)

value = data.get(key, default)

if isinstance(value, bool):
    print("true" if value else "false")
else:
    print(value)
PY
}


bashio::log.info \
    "Smart Home UI Manager iniciado correctamente"


if bashio::config.true "local_inventory_enabled"; then
    bashio::log.warning \
        "Modo de inventario local SHA-256 activado"

    bashio::log.info \
        "No se instalarán, actualizarán ni repararán componentes"

    if python3 /local_inventory.py; then
        bashio::log.info \
            "Inventario local finalizado correctamente"
    else
        inventory_exit_code="$?"

        bashio::log.warning \
            "El inventario local terminó con observaciones o errores"

        bashio::log.warning \
            "Código de salida: ${inventory_exit_code}"
    fi

    bashio::log.info \
        "La aplicación se detendrá"

    exit 0
fi


bashio::log.info \
    "Validando catálogo de componentes"

if ! python3 /component_manager.py \
    --validate-only \
    "${CATALOG_FILE}"; then

    bashio::log.error \
        "El catálogo components.json no es válido"

    bashio::log.error \
        "No se ejecutará el mantenimiento"

    exit 1
fi


bashio::log.info \
    "Ejecutando mantenimiento desde components.json"

manager_exit_code=0

python3 /component_manager.py \
    "${CATALOG_FILE}" \
    "${RESULTS_FILE}" \
    "${STATE_FILE}" \
    || manager_exit_code="$?"

integration_changed="$(
    read_state_value \
        "integration_changed" \
        "false"
)"

error_count="$(
    read_state_value \
        "errors" \
        "1"
)"

catalog_version="$(
    read_state_value \
        "catalog_version" \
        "desconocido"
)"

bashio::log.info \
    "Catálogo procesado: ${catalog_version}"


if [[ "${integration_changed}" == "true" ]]; then
    bashio::log.warning \
        "Se instaló, actualizó o reparó una integración personalizada"

    bashio::log.warning \
        "Es necesario reiniciar Home Assistant Core"
else
    bashio::log.info \
        "No es necesario reiniciar Home Assistant Core"
fi


if [[ "${error_count}" != "0" ]] \
    || [[ "${manager_exit_code}" != "0" ]]; then

    bashio::log.warning \
        "Uno o más componentes presentaron errores"

    bashio::log.warning \
        "Revisa el reporte de mantenimiento"
fi


bashio::log.info \
    "Generando reporte de mantenimiento"

if python3 /create_report.py \
    "${integration_changed}" \
    "${RESULTS_FILE}" \
    "${CATALOG_FILE}"; then

    bashio::log.info \
        "Reporte de mantenimiento generado correctamente"
else
    bashio::log.warning \
        "No se pudo generar el reporte de mantenimiento"
fi


bashio::log.info \
    "Comprobación de componentes finalizada"

bashio::log.info \
    "Mantenimiento finalizado. La aplicación se detendrá."
