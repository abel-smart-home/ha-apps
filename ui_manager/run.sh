#!/usr/bin/with-contenv bashio

bashio::log.info "Smart Home UI Manager iniciado correctamente"

TEST_FILE="/config/ui_manager_test.txt"

{
    echo "Smart Home UI Manager"
    echo "Acceso de escritura confirmado"
    date "+%Y-%m-%d %H:%M:%S"
} > "${TEST_FILE}"

if [[ -f "${TEST_FILE}" ]]; then
    bashio::log.info "Prueba de escritura completada: ${TEST_FILE}"
else
    bashio::log.error "No se pudo escribir en la carpeta de configuración"
    exit 1
fi

while true; do
    sleep 3600
done
