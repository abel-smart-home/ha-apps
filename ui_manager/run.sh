#!/usr/bin/with-contenv bashio

set -euo pipefail

INTEGRATION_CHANGED="false"


option_enabled() {
    local option_name="$1"
    local option_value

    option_value="$(bashio::config "${option_name}")"

    [[ "${option_value}" == "true" ]]
}


log_component_disabled() {
    local component_name="$1"

    bashio::log.info \
        "${component_name} está desactivado en la configuración"

    bashio::log.info \
        "No se instalará ni actualizará ${component_name}"
}


install_frontend_component() {
    local component_name="$1"
    local component_version="$2"
    local install_dir="$3"
    local file_name="$4"
    local download_url="$5"
    local resource_base="$6"

    local component_file="${install_dir}/${file_name}"
    local version_file="${install_dir}/version"
    local resource_url="${resource_base}?v=${component_version}"
    local current_version=""

    mkdir -p "${install_dir}"

    if [[ -f "${version_file}" ]]; then
        current_version="$(tr -d '\r\n' < "${version_file}")"
    fi

    if [[ -s "${component_file}" ]] \
        && [[ "${current_version}" == "${component_version}" ]]; then

        bashio::log.info \
            "${component_name} v${component_version} ya está instalado"
    else
        bashio::log.info \
            "Descargando ${component_name} v${component_version}"

        local temporary_file
        temporary_file="$(mktemp)"

        if curl \
            --fail \
            --location \
            --silent \
            --show-error \
            --retry 3 \
            --retry-delay 2 \
            "${download_url}" \
            --output "${temporary_file}"; then

            if [[ ! -s "${temporary_file}" ]]; then
                bashio::log.error \
                    "El archivo descargado de ${component_name} está vacío"

                rm -f "${temporary_file}"
                return 1
            fi

            mv "${temporary_file}" "${component_file}"
            chmod 0644 "${component_file}"

            printf '%s\n' \
                "${component_version}" \
                > "${version_file}"

            bashio::log.info \
                "${component_name} v${component_version} instalado correctamente"

            bashio::log.info \
                "Archivo: ${component_file}"
        else
            bashio::log.error \
                "No se pudo descargar ${component_name}"

            rm -f "${temporary_file}"
            return 1
        fi
    fi

    bashio::log.info \
        "Comprobando recurso de ${component_name}"

    if python3 /register_resource.py \
        "${resource_url}" \
        "${resource_base}" \
        "module"; then

        bashio::log.info \
            "Recurso de ${component_name} configurado correctamente"
    else
        bashio::log.warning \
            "${component_name} está instalado, pero no se pudo registrar el recurso"
    fi
}


install_custom_integration() {
    local integration_name="$1"
    local integration_id="$2"
    local integration_version="$3"
    local download_url="$4"
    local source_folder_name="$5"

    local destination="/config/custom_components/${integration_id}"
    local state_dir="/config/ui-manager/state"
    local version_file="${state_dir}/${integration_id}.version"
    local backup_root="/config/ui-manager/backups/${integration_id}"

    local installed_version=""
    local temporary_dir=""
    local archive_file=""
    local source_dir=""
    local staging_dir="${destination}.ui_manager_new"
    local previous_dir="${destination}.ui_manager_previous"
    local timestamp=""

    mkdir -p \
        "/config/custom_components" \
        "${state_dir}" \
        "${backup_root}"

    if [[ -f "${destination}/manifest.json" ]]; then
        installed_version="$(
            python3 -c '
import json
import sys

try:
    with open(sys.argv[1], "r", encoding="utf-8") as file:
        manifest = json.load(file)

    print(manifest.get("version", ""))
except Exception:
    print("")
' "${destination}/manifest.json" 2>/dev/null || true
        )"
    fi

    if [[ -d "${destination}" ]] \
        && [[ "${installed_version}" == "${integration_version}" ]]; then

        printf '%s\n' \
            "${integration_version}" \
            > "${version_file}"

        bashio::log.info \
            "${integration_name} v${integration_version} ya está instalado"

        return 0
    fi

    bashio::log.info \
        "Descargando ${integration_name} v${integration_version}"

    temporary_dir="$(mktemp -d)"
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
        return 1
    fi

    if [[ ! -s "${archive_file}" ]]; then
        bashio::log.error \
            "El archivo descargado de ${integration_name} está vacío"

        rm -rf "${temporary_dir}"
        return 1
    fi

    if ! unzip -tq "${archive_file}" >/dev/null; then
        bashio::log.error \
            "El archivo ZIP de ${integration_name} no es válido"

        rm -rf "${temporary_dir}"
        return 1
    fi

    mkdir -p "${temporary_dir}/extracted"

    unzip -q \
        "${archive_file}" \
        -d "${temporary_dir}/extracted"

    source_dir="$(
        find "${temporary_dir}/extracted" \
            -type d \
            -path "*/custom_components/${source_folder_name}" \
            -print \
            -quit
    )"

    # Algunos paquetes oficiales, como Spook, incluyen directamente
    # los archivos de la integración en la raíz del archivo ZIP.
    if [[ -z "${source_dir}" ]] \
        && [[ -f "${temporary_dir}/extracted/manifest.json" ]]; then

        source_dir="${temporary_dir}/extracted"
    fi

    if [[ -z "${source_dir}" ]] \
        || [[ ! -f "${source_dir}/manifest.json" ]]; then

        bashio::log.error \
            "No se encontró la integración ${integration_name} dentro del ZIP"

        rm -rf "${temporary_dir}"
        return 1
    fi

    rm -rf \
        "${staging_dir}" \
        "${previous_dir}"

    mkdir -p "${staging_dir}"

    cp -a \
        "${source_dir}/." \
        "${staging_dir}/"

    if [[ ! -f "${staging_dir}/manifest.json" ]]; then
        bashio::log.error \
            "La copia preparada de ${integration_name} no es válida"

        rm -rf \
            "${temporary_dir}" \
            "${staging_dir}"

        return 1
    fi

    if [[ -d "${destination}" ]]; then
        timestamp="$(date '+%Y%m%d-%H%M%S')"

        mkdir -p "${backup_root}/${timestamp}"

        cp -a \
            "${destination}/." \
            "${backup_root}/${timestamp}/"

        bashio::log.info \
            "Respaldo creado: ${backup_root}/${timestamp}"

        mv \
            "${destination}" \
            "${previous_dir}"
    fi

    if mv "${staging_dir}" "${destination}"; then
        rm -rf "${previous_dir}"

        printf '%s\n' \
            "${integration_version}" \
            > "${version_file}"

        INTEGRATION_CHANGED="true"

        bashio::log.info \
            "${integration_name} v${integration_version} instalado correctamente"

        bashio::log.info \
            "Carpeta: ${destination}"
    else
        bashio::log.error \
            "No se pudo activar ${integration_name}"

        rm -rf "${staging_dir}"

        if [[ -d "${previous_dir}" ]]; then
            mv \
                "${previous_dir}" \
                "${destination}"

            bashio::log.warning \
                "Se restauró la versión anterior de ${integration_name}"
        fi

        rm -rf "${temporary_dir}"
        return 1
    fi

    rm -rf "${temporary_dir}"
}


bashio::log.info "Smart Home UI Manager iniciado correctamente"
bashio::log.info "Leyendo configuración de componentes"


# Mini Graph Card

if option_enabled "mini_graph_card"; then
    install_frontend_component \
        "Mini Graph Card" \
        "0.13.0" \
        "/config/www/ui-components/mini-graph-card" \
        "mini-graph-card-bundle.js" \
        "https://github.com/kalkih/mini-graph-card/releases/download/v0.13.0/mini-graph-card-bundle.js" \
        "/local/ui-components/mini-graph-card/mini-graph-card-bundle.js"
else
    log_component_disabled "Mini Graph Card"
fi


# Mushroom

if option_enabled "mushroom"; then
    install_frontend_component \
        "Mushroom" \
        "5.2.2" \
        "/config/www/ui-components/mushroom" \
        "mushroom.js" \
        "https://github.com/piitaya/lovelace-mushroom/releases/download/v5.2.2/mushroom.js" \
        "/local/ui-components/mushroom/mushroom.js"
else
    log_component_disabled "Mushroom"
fi


# Modern Circular Gauge

if option_enabled "modern_circular_gauge"; then
    install_frontend_component \
        "Modern Circular Gauge" \
        "0.14.1" \
        "/config/www/ui-components/modern-circular-gauge" \
        "modern-circular-gauge.js" \
        "https://github.com/selvalt7/modern-circular-gauge/releases/download/v0.14.1/modern-circular-gauge.js" \
        "/local/ui-components/modern-circular-gauge/modern-circular-gauge.js"
else
    log_component_disabled "Modern Circular Gauge"
fi


# SonoffLAN

if option_enabled "sonofflan"; then
    install_custom_integration \
        "SonoffLAN" \
        "sonoff" \
        "3.12.2" \
        "https://github.com/AlexxIT/SonoffLAN/archive/refs/tags/v3.12.2.zip" \
        "sonoff"
else
    log_component_disabled "SonoffLAN"
fi


# Spook

if option_enabled "spook"; then
    install_custom_integration \
        "Spook" \
        "spook" \
        "5.0.0" \
        "https://github.com/frenck/spook/releases/download/v5.0.0/spook.zip" \
        "spook"
else
    log_component_disabled "Spook"
fi


if [[ "${INTEGRATION_CHANGED}" == "true" ]]; then
    bashio::log.warning \
        "Se instaló o actualizó una integración personalizada"

    bashio::log.warning \
        "Es necesario reiniciar Home Assistant Core"
fi


bashio::log.info \
    "Comprobación de componentes finalizada"


while true; do
    sleep 3600
done
