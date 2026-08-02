#!/usr/bin/with-contenv bashio

set -e

CARD_NAME="Mini Graph Card"
CARD_VERSION="0.13.0"

INSTALL_DIR="/config/www/ui-components/mini-graph-card"
CARD_FILE="${INSTALL_DIR}/mini-graph-card-bundle.js"
VERSION_FILE="${INSTALL_DIR}/version"

DOWNLOAD_URL="https://github.com/kalkih/mini-graph-card/releases/download/v${CARD_VERSION}/mini-graph-card-bundle.js"

bashio::log.info "Smart Home UI Manager iniciado correctamente"

# Eliminar el archivo usado anteriormente para la prueba de escritura.
rm -f /config/ui_manager_test.txt

# Crear las carpetas necesarias.
mkdir -p "${INSTALL_DIR}"

CURRENT_VERSION=""

if [[ -f "${VERSION_FILE}" ]]; then
    CURRENT_VERSION="$(cat "${VERSION_FILE}")"
fi

if [[ -f "${CARD_FILE}" ]] && [[ "${CURRENT_VERSION}" == "${CARD_VERSION}" ]]; then
    bashio::log.info "${CARD_NAME} v${CARD_VERSION} ya está instalado"
else
    bashio::log.info "Descargando ${CARD_NAME} v${CARD_VERSION}"

    TEMP_FILE="$(mktemp)"

    if curl \
        --fail \
        --location \
        --silent \
        --show-error \
        "${DOWNLOAD_URL}" \
        --output "${TEMP_FILE}"; then

        if [[ ! -s "${TEMP_FILE}" ]]; then
            bashio::log.error "El archivo descargado está vacío"
            rm -f "${TEMP_FILE}"
            exit 1
        fi

        mv "${TEMP_FILE}" "${CARD_FILE}"
        chmod 0644 "${CARD_FILE}"

        echo "${CARD_VERSION}" > "${VERSION_FILE}"

        bashio::log.info "${CARD_NAME} v${CARD_VERSION} instalado correctamente"
        bashio::log.info "Archivo: ${CARD_FILE}"
    else
        bashio::log.error "No se pudo descargar ${CARD_NAME}"
        rm -f "${TEMP_FILE}"
        exit 1
    fi
fi

while true; do
    sleep 3600
done
