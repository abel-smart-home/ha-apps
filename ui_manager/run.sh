#!/usr/bin/with-contenv bashio

set -euo pipefail

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


bashio::log.info "Smart Home UI Manager iniciado correctamente"


# Mini Graph Card

install_frontend_component \
    "Mini Graph Card" \
    "0.13.0" \
    "/config/www/ui-components/mini-graph-card" \
    "mini-graph-card-bundle.js" \
    "https://github.com/kalkih/mini-graph-card/releases/download/v0.13.0/mini-graph-card-bundle.js" \
    "/local/ui-components/mini-graph-card/mini-graph-card-bundle.js"


# Mushroom

install_frontend_component \
    "Mushroom" \
    "5.2.2" \
    "/config/www/ui-components/mushroom" \
    "mushroom.js" \
    "https://github.com/piitaya/lovelace-mushroom/releases/download/v5.2.2/mushroom.js" \
    "/local/ui-components/mushroom/mushroom.js"


while true; do
    sleep 3600
done
