#!/usr/bin/with-contenv bashio

set -uo pipefail

INTEGRATION_CHANGED="false"
RESULTS_FILE="/tmp/ui_manager_results.tsv"

: > "${RESULTS_FILE}"


sanitize_field() {
    local value="${1:-}"

    value="${value//$'\t'/ }"
    value="${value//$'\r'/ }"
    value="${value//$'\n'/ }"

    printf '%s' "${value}"
}


record_result() {
    local component_id="$1"
    local component_name="$2"
    local component_type="$3"
    local desired_version="$4"
    local previous_version="$5"
    local final_version="$6"
    local status="$7"
    local message="$8"

    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$(sanitize_field "${component_id}")" \
        "$(sanitize_field "${component_name}")" \
        "$(sanitize_field "${component_type}")" \
        "$(sanitize_field "${desired_version}")" \
        "$(sanitize_field "${previous_version}")" \
        "$(sanitize_field "${final_version}")" \
        "$(sanitize_field "${status}")" \
        "$(sanitize_field "${message}")" \
        >> "${RESULTS_FILE}"
}


option_enabled() {
    local option_name="$1"
    local option_value="false"

    option_value="$(
        bashio::config "${option_name}" 2>/dev/null \
            || printf 'false'
    )"

    [[ "${option_value}" == "true" ]]
}


read_version_file() {
    local version_file="$1"

    if [[ -f "${version_file}" ]]; then
        tr -d '\r\n' < "${version_file}"
    fi
}


read_manifest_version() {
    local manifest_file="$1"

    if [[ ! -f "${manifest_file}" ]]; then
        return 0
    fi

    python3 - "${manifest_file}" <<'PY'
import json
import sys

manifest_path = sys.argv[1]

try:
    with open(manifest_path, "r", encoding="utf-8") as file:
        manifest = json.load(file)

    version = manifest.get("version", "")

    if isinstance(version, str):
        print(version.strip())
except Exception:
    print("")
PY
}


log_component_disabled() {
    local component_id="$1"
    local component_name="$2"
    local component_type="$3"
    local desired_version="$4"

    bashio::log.info \
        "${component_name} está desactivado en la configuración"

    bashio::log.info \
        "No se instalará ni actualizará ${component_name}"

    record_result \
        "${component_id}" \
        "${component_name}" \
        "${component_type}" \
        "${desired_version}" \
        "-" \
        "-" \
        "OMITIDO" \
        "Componente desactivado en la configuración"
}


install_frontend_component() {
    local component_id="$1"
    local component_name="$2"
    local component_version="$3"
    local install_dir="$4"
    local file_name="$5"
    local download_url="$6"
    local resource_base="$7"

    local component_file="${install_dir}/${file_name}"
    local version_file="${install_dir}/version"
    local resource_url="${resource_base}?v=${component_version}"

    local previous_version=""
    local final_version=""
    local temporary_file=""
    local result_status=""

    previous_version="$(read_version_file "${version_file}")"

    if [[ -z "${previous_version}" ]]; then
        if [[ -s "${component_file}" ]]; then
            previous_version="desconocida"
        else
            previous_version="-"
        fi
    fi

    if ! mkdir -p "${install_dir}"; then
        bashio::log.error \
            "No se pudo crear la carpeta de ${component_name}"

        record_result \
            "${component_id}" \
            "${component_name}" \
            "frontend" \
            "${component_version}" \
            "${previous_version}" \
            "${previous_version}" \
            "ERROR" \
            "No se pudo crear la carpeta de instalación"

        return 1
    fi

    if [[ -s "${component_file}" ]] \
        && [[ "${previous_version}" == "${component_version}" ]]; then

        bashio::log.info \
            "${component_name} v${component_version} ya está instalado"

        bashio::log.info \
            "Comprobando recurso de ${component_name}"

        if python3 /register_resource.py \
            "${resource_url}" \
            "${resource_base}" \
            "module"; then

            bashio::log.info \
                "Recurso de ${component_name} configurado correctamente"

            record_result \
                "${component_id}" \
                "${component_name}" \
                "frontend" \
                "${component_version}" \
                "${previous_version}" \
                "${component_version}" \
                "VERIFICADO" \
                "Archivo y recurso comprobados correctamente"

            return 0
        fi

        bashio::log.error \
            "No se pudo comprobar el recurso de ${component_name}"

        record_result \
            "${component_id}" \
            "${component_name}" \
            "frontend" \
            "${component_version}" \
            "${previous_version}" \
            "${previous_version}" \
            "ERROR" \
            "El archivo existe, pero no se pudo registrar el recurso"

        return 1
    fi

    bashio::log.info \
        "Descargando ${component_name} v${component_version}"

    if ! temporary_file="$(mktemp)"; then
        bashio::log.error \
            "No se pudo crear un archivo temporal para ${component_name}"

        record_result \
            "${component_id}" \
            "${component_name}" \
            "frontend" \
            "${component_version}" \
            "${previous_version}" \
            "${previous_version}" \
            "ERROR" \
            "No se pudo crear el archivo temporal"

        return 1
    fi

    if ! curl \
        --fail \
        --location \
        --silent \
        --show-error \
        --retry 3 \
        --retry-delay 2 \
        "${download_url}" \
        --output "${temporary_file}"; then

        bashio::log.error \
            "No se pudo descargar ${component_name}"

        rm -f "${temporary_file}"

        record_result \
            "${component_id}" \
            "${component_name}" \
            "frontend" \
            "${component_version}" \
            "${previous_version}" \
            "${previous_version}" \
            "ERROR" \
            "Falló la descarga; se conservó la versión anterior"

        return 1
    fi

    if [[ ! -s "${temporary_file}" ]]; then
        bashio::log.error \
            "El archivo descargado de ${component_name} está vacío"

        rm -f "${temporary_file}"

        record_result \
            "${component_id}" \
            "${component_name}" \
            "frontend" \
            "${component_version}" \
            "${previous_version}" \
            "${previous_version}" \
            "ERROR" \
            "La descarga produjo un archivo vacío"

        return 1
    fi

    if ! mv "${temporary_file}" "${component_file}"; then
        bashio::log.error \
            "No se pudo guardar ${component_name}"

        rm -f "${temporary_file}"

        record_result \
            "${component_id}" \
            "${component_name}" \
            "frontend" \
            "${component_version}" \
            "${previous_version}" \
            "${previous_version}" \
            "ERROR" \
            "No se pudo activar el archivo descargado"

        return 1
    fi

    if ! chmod 0644 "${component_file}"; then
        bashio::log.error \
            "No se pudieron establecer permisos para ${component_name}"

        record_result \
            "${component_id}" \
            "${component_name}" \
            "frontend" \
            "${component_version}" \
            "${previous_version}" \
            "${component_version}" \
            "ERROR" \
            "El archivo fue instalado, pero falló la asignación de permisos"

        return 1
    fi

    if ! printf '%s\n' \
        "${component_version}" \
        > "${version_file}"; then

        bashio::log.error \
            "No se pudo guardar la versión de ${component_name}"

        record_result \
            "${component_id}" \
            "${component_name}" \
            "frontend" \
            "${component_version}" \
            "${previous_version}" \
            "${component_version}" \
            "ERROR" \
            "El archivo fue instalado, pero no se guardó su versión"

        return 1
    fi

    final_version="${component_version}"

    bashio::log.info \
        "${component_name} v${component_version} instalado correctamente"

    bashio::log.info \
        "Archivo: ${component_file}"

    bashio::log.info \
        "Comprobando recurso de ${component_name}"

    if ! python3 /register_resource.py \
        "${resource_url}" \
        "${resource_base}" \
        "module"; then

        bashio::log.error \
            "No se pudo registrar el recurso de ${component_name}"

        record_result \
            "${component_id}" \
            "${component_name}" \
            "frontend" \
            "${component_version}" \
            "${previous_version}" \
            "${final_version}" \
            "ERROR" \
            "El archivo se actualizó, pero falló el registro del recurso"

        return 1
    fi

    bashio::log.info \
        "Recurso de ${component_name} configurado correctamente"

    if [[ "${previous_version}" == "-" ]]; then
        result_status="INSTALADO"
    else
        result_status="ACTUALIZADO"
    fi

    record_result \
        "${component_id}" \
        "${component_name}" \
        "frontend" \
        "${component_version}" \
        "${previous_version}" \
        "${final_version}" \
        "${result_status}" \
        "Componente y recurso configurados correctamente"

    return 0
}


install_custom_integration() {
    local integration_id="$1"
    local integration_name="$2"
    local integration_version="$3"
    local download_url="$4"
    local source_folder_name="$5"

    local destination="/config/custom_components/${integration_id}"
    local state_dir="/config/ui-manager/state"
    local version_file="${state_dir}/${integration_id}.version"
    local backup_root="/config/ui-manager/backups/${integration_id}"

    local previous_version=""
    local package_version=""
    local temporary_dir=""
    local archive_file=""
    local source_dir=""
    local staging_dir="${destination}.ui_manager_new"
    local previous_dir="${destination}.ui_manager_previous"
    local timestamp=""
    local result_status=""

    previous_version="$(
        read_manifest_version "${destination}/manifest.json"
    )"

    if [[ -z "${previous_version}" ]]; then
        if [[ -d "${destination}" ]]; then
            previous_version="desconocida"
        else
            previous_version="-"
        fi
    fi

    if [[ -d "${destination}" ]] \
        && [[ "${previous_version}" == "${integration_version}" ]]; then

        bashio::log.info \
            "${integration_name} v${integration_version} ya está instalado"

        record_result \
            "${integration_id}" \
            "${integration_name}" \
            "integration" \
            "${integration_version}" \
            "${previous_version}" \
            "${integration_version}" \
            "VERIFICADO" \
            "Manifest y versión comprobados correctamente"

        return 0
    fi

    if ! mkdir -p \
        "/config/custom_components" \
        "${state_dir}" \
        "${backup_root}"; then

        bashio::log.error \
            "No se pudieron crear las carpetas para ${integration_name}"

        record_result \
            "${integration_id}" \
            "${integration_name}" \
            "integration" \
            "${integration_version}" \
            "${previous_version}" \
            "${previous_version}" \
            "ERROR" \
            "No se pudieron crear las carpetas necesarias"

        return 1
    fi

    bashio::log.info \
        "Descargando ${integration_name} v${integration_version}"

    if ! temporary_dir="$(mktemp -d)"; then
        bashio::log.error \
            "No se pudo crear una carpeta temporal para ${integration_name}"

        record_result \
            "${integration_id}" \
            "${integration_name}" \
            "integration" \
            "${integration_version}" \
            "${previous_version}" \
            "${previous_version}" \
            "ERROR" \
            "No se pudo crear la carpeta temporal"

        return 1
    fi

    archive_file="${temporary_dir}/${integration_id}.zip"

    if ! curl \
        --fail \
        --location \
        --silent \
        --show-error \
        --retry 3 \
        --retry-delay 2 \
        "${download_url}" \
        --output "${archive_file}"; then

        bashio::log.error \
            "No se pudo descargar ${integration_name}"

        rm -rf "${temporary_dir}"

        record_result \
            "${integration_id}" \
            "${integration_name}" \
            "integration" \
            "${integration_version}" \
            "${previous_version}" \
            "${previous_version}" \
            "ERROR" \
            "Falló la descarga; se conservó la versión anterior"

        return 1
    fi

    if [[ ! -s "${archive_file}" ]]; then
        bashio::log.error \
            "El archivo descargado de ${integration_name} está vacío"

        rm -rf "${temporary_dir}"

        record_result \
            "${integration_id}" \
            "${integration_name}" \
            "integration" \
            "${integration_version}" \
            "${previous_version}" \
            "${previous_version}" \
            "ERROR" \
            "La descarga produjo un archivo vacío"

        return 1
    fi

    if ! unzip -tq "${archive_file}" >/dev/null; then
        bashio::log.error \
            "El archivo ZIP de ${integration_name} no es válido"

        rm -rf "${temporary_dir}"

        record_result \
            "${integration_id}" \
            "${integration_name}" \
            "integration" \
            "${integration_version}" \
            "${previous_version}" \
            "${previous_version}" \
            "ERROR" \
            "El archivo descargado no es un ZIP válido"

        return 1
    fi

    if ! mkdir -p "${temporary_dir}/extracted"; then
        rm -rf "${temporary_dir}"

        record_result \
            "${integration_id}" \
            "${integration_name}" \
            "integration" \
            "${integration_version}" \
            "${previous_version}" \
            "${previous_version}" \
            "ERROR" \
            "No se pudo preparar la carpeta de extracción"

        return 1
    fi

    if ! unzip -q \
        "${archive_file}" \
        -d "${temporary_dir}/extracted"; then

        bashio::log.error \
            "No se pudo extraer ${integration_name}"

        rm -rf "${temporary_dir}"

        record_result \
            "${integration_id}" \
            "${integration_name}" \
            "integration" \
            "${integration_version}" \
            "${previous_version}" \
            "${previous_version}" \
            "ERROR" \
            "Falló la extracción del archivo ZIP"

        return 1
    fi

    source_dir="$(
        find "${temporary_dir}/extracted" \
            -type d \
            -path "*/custom_components/${source_folder_name}" \
            -print \
            -quit
    )"

    if [[ -z "${source_dir}" ]] \
        && [[ -f "${temporary_dir}/extracted/manifest.json" ]]; then

        source_dir="${temporary_dir}/extracted"
    fi

    if [[ -z "${source_dir}" ]] \
        || [[ ! -f "${source_dir}/manifest.json" ]]; then

        bashio::log.error \
            "No se encontró ${integration_name} dentro del ZIP"

        rm -rf "${temporary_dir}"

        record_result \
            "${integration_id}" \
            "${integration_name}" \
            "integration" \
            "${integration_version}" \
            "${previous_version}" \
            "${previous_version}" \
            "ERROR" \
            "El ZIP no contiene la estructura esperada"

        return 1
    fi

    package_version="$(
        read_manifest_version "${source_dir}/manifest.json"
    )"

    if [[ "${package_version}" != "${integration_version}" ]]; then
        bashio::log.error \
            "La versión interna de ${integration_name} no coincide"

        bashio::log.error \
            "Esperada: ${integration_version}; recibida: ${package_version:-vacía}"

        rm -rf "${temporary_dir}"

        record_result \
            "${integration_id}" \
            "${integration_name}" \
            "integration" \
            "${integration_version}" \
            "${previous_version}" \
            "${previous_version}" \
            "ERROR" \
            "Versión interna inválida: ${package_version:-vacía}"

        return 1
    fi

    rm -rf \
        "${staging_dir}" \
        "${previous_dir}"

    if ! mkdir -p "${staging_dir}"; then
        rm -rf "${temporary_dir}"

        record_result \
            "${integration_id}" \
            "${integration_name}" \
            "integration" \
            "${integration_version}" \
            "${previous_version}" \
            "${previous_version}" \
            "ERROR" \
            "No se pudo crear la carpeta de preparación"

        return 1
    fi

    if ! cp -a \
        "${source_dir}/." \
        "${staging_dir}/"; then

        bashio::log.error \
            "No se pudo preparar ${integration_name}"

        rm -rf \
            "${temporary_dir}" \
            "${staging_dir}"

        record_result \
            "${integration_id}" \
            "${integration_name}" \
            "integration" \
            "${integration_version}" \
            "${previous_version}" \
            "${previous_version}" \
            "ERROR" \
            "Falló la copia a la carpeta de preparación"

        return 1
    fi

    if [[ -d "${destination}" ]]; then
        timestamp="$(date '+%Y%m%d-%H%M%S')"

        if ! mkdir -p "${backup_root}/${timestamp}"; then
            rm -rf \
                "${temporary_dir}" \
                "${staging_dir}"

            record_result \
                "${integration_id}" \
                "${integration_name}" \
                "integration" \
                "${integration_version}" \
                "${previous_version}" \
                "${previous_version}" \
                "ERROR" \
                "No se pudo crear el respaldo; actualización cancelada"

            return 1
        fi

        if ! cp -a \
            "${destination}/." \
            "${backup_root}/${timestamp}/"; then

            bashio::log.error \
                "No se pudo respaldar ${integration_name}"

            rm -rf \
                "${temporary_dir}" \
                "${staging_dir}" \
                "${backup_root:?}/${timestamp}"

            record_result \
                "${integration_id}" \
                "${integration_name}" \
                "integration" \
                "${integration_version}" \
                "${previous_version}" \
                "${previous_version}" \
                "ERROR" \
                "Falló el respaldo; se conservó la versión anterior"

            return 1
        fi

        bashio::log.info \
            "Respaldo creado: ${backup_root}/${timestamp}"

        if ! mv "${destination}" "${previous_dir}"; then
            rm -rf \
                "${temporary_dir}" \
                "${staging_dir}"

            record_result \
                "${integration_id}" \
                "${integration_name}" \
                "integration" \
                "${integration_version}" \
                "${previous_version}" \
                "${previous_version}" \
                "ERROR" \
                "No se pudo preparar el reemplazo de la integración"

            return 1
        fi
    fi

    if ! mv "${staging_dir}" "${destination}"; then
        bashio::log.error \
            "No se pudo activar ${integration_name}"

        rm -rf \
            "${destination}" \
            "${staging_dir}"

        if [[ -d "${previous_dir}" ]]; then
            mv "${previous_dir}" "${destination}" || true

            bashio::log.warning \
                "Se restauró la versión anterior de ${integration_name}"
        fi

        rm -rf "${temporary_dir}"

        record_result \
            "${integration_id}" \
            "${integration_name}" \
            "integration" \
            "${integration_version}" \
            "${previous_version}" \
            "${previous_version}" \
            "ERROR" \
            "Falló la activación; se restauró la versión anterior"

        return 1
    fi

    rm -rf "${previous_dir}"

    if ! printf '%s\n' \
        "${integration_version}" \
        > "${version_file}"; then

        INTEGRATION_CHANGED="true"

        rm -rf "${temporary_dir}"

        record_result \
            "${integration_id}" \
            "${integration_name}" \
            "integration" \
            "${integration_version}" \
            "${previous_version}" \
            "${integration_version}" \
            "ERROR" \
            "Integración instalada, pero no se pudo guardar su estado"

        return 1
    fi

    INTEGRATION_CHANGED="true"

    if [[ "${previous_version}" == "-" ]]; then
        result_status="INSTALADO"
    else
        result_status="ACTUALIZADO"
    fi

    bashio::log.info \
        "${integration_name} v${integration_version} instalado correctamente"

    bashio::log.info \
        "Carpeta: ${destination}"

    record_result \
        "${integration_id}" \
        "${integration_name}" \
        "integration" \
        "${integration_version}" \
        "${previous_version}" \
        "${integration_version}" \
        "${result_status}" \
        "Integración instalada y validada correctamente"

    rm -rf "${temporary_dir}"

    return 0
}


bashio::log.info \
    "Smart Home UI Manager iniciado correctamente"

bashio::log.info \
    "Leyendo configuración de componentes"


if option_enabled "mini_graph_card"; then
    install_frontend_component \
        "mini_graph_card" \
        "Mini Graph Card" \
        "0.13.0" \
        "/config/www/ui-components/mini-graph-card" \
        "mini-graph-card-bundle.js" \
        "https://github.com/kalkih/mini-graph-card/releases/download/v0.13.0/mini-graph-card-bundle.js" \
        "/local/ui-components/mini-graph-card/mini-graph-card-bundle.js"
else
    log_component_disabled \
        "mini_graph_card" \
        "Mini Graph Card" \
        "frontend" \
        "0.13.0"
fi


if option_enabled "mushroom"; then
    install_frontend_component \
        "mushroom" \
        "Mushroom" \
        "5.2.2" \
        "/config/www/ui-components/mushroom" \
        "mushroom.js" \
        "https://github.com/piitaya/lovelace-mushroom/releases/download/v5.2.2/mushroom.js" \
        "/local/ui-components/mushroom/mushroom.js"
else
    log_component_disabled \
        "mushroom" \
        "Mushroom" \
        "frontend" \
        "5.2.2"
fi


if option_enabled "modern_circular_gauge"; then
    install_frontend_component \
        "modern_circular_gauge" \
        "Modern Circular Gauge" \
        "0.14.1" \
        "/config/www/ui-components/modern-circular-gauge" \
        "modern-circular-gauge.js" \
        "https://github.com/selvalt7/modern-circular-gauge/releases/download/v0.14.1/modern-circular-gauge.js" \
        "/local/ui-components/modern-circular-gauge/modern-circular-gauge.js"
else
    log_component_disabled \
        "modern_circular_gauge" \
        "Modern Circular Gauge" \
        "frontend" \
        "0.14.1"
fi


if option_enabled "sonofflan"; then
    install_custom_integration \
        "sonoff" \
        "SonoffLAN" \
        "3.12.2" \
        "https://github.com/AlexxIT/SonoffLAN/archive/refs/tags/v3.12.2.zip" \
        "sonoff"
else
    log_component_disabled \
        "sonofflan" \
        "SonoffLAN" \
        "integration" \
        "3.12.2"
fi


if option_enabled "spook"; then
    install_custom_integration \
        "spook" \
        "Spook" \
        "5.0.0" \
        "https://github.com/frenck/spook/releases/download/v5.0.0/spook.zip" \
        "spook"
else
    log_component_disabled \
        "spook" \
        "Spook" \
        "integration" \
        "5.0.0"
fi


if [[ "${INTEGRATION_CHANGED}" == "true" ]]; then
    bashio::log.warning \
        "Se instaló o actualizó una integración personalizada"

    bashio::log.warning \
        "Es necesario reiniciar Home Assistant Core"
else
    bashio::log.info \
        "No es necesario reiniciar Home Assistant Core"
fi


if grep -q $'\tERROR\t' "${RESULTS_FILE}"; then
    bashio::log.warning \
        "Uno o más componentes presentaron errores"

    bashio::log.warning \
        "Revisa el reporte de mantenimiento"
fi


bashio::log.info \
    "Generando reporte de mantenimiento"

if python3 /create_report.py \
    "${INTEGRATION_CHANGED}" \
    "${RESULTS_FILE}"; then

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
