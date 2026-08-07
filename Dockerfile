FROM ghcr.io/home-assistant/base:latest

ARG BUILD_ARCH="unknown"
ARG BUILD_VERSION="development"
ARG BUILD_REVISION="unknown"
ARG BUILD_DATE="unknown"
ARG BUILD_SOURCE="https://github.com/abel-smart-home/ha-apps"
ARG BUILD_IMAGE="ghcr.io/abel-smart-home/smart-home-ui-manager:development"

ENV \
    UI_MANAGER_APP_VERSION="${BUILD_VERSION}" \
    UI_MANAGER_BUILD_ARCH="${BUILD_ARCH}" \
    UI_MANAGER_BUILD_REVISION="${BUILD_REVISION}" \
    UI_MANAGER_BUILD_DATE="${BUILD_DATE}" \
    UI_MANAGER_BUILD_SOURCE="${BUILD_SOURCE}" \
    UI_MANAGER_IMAGE="${BUILD_IMAGE}" \
    UI_MANAGER_PREBUILT="true"

LABEL \
    io.hass.name="Smart Home UI Manager" \
    io.hass.description="Instala, valida, diagnostica, genera inventarios y restaura componentes personalizados para Home Assistant" \
    io.hass.url="https://github.com/abel-smart-home/ha-apps" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="app" \
    io.hass.version="${BUILD_VERSION}" \
    org.opencontainers.image.title="Smart Home UI Manager" \
    org.opencontainers.image.description="Mantenimiento controlado de tarjetas e integraciones personalizadas para Home Assistant" \
    org.opencontainers.image.source="${BUILD_SOURCE}" \
    org.opencontainers.image.url="${BUILD_SOURCE}" \
    org.opencontainers.image.version="${BUILD_VERSION}" \
    org.opencontainers.image.revision="${BUILD_REVISION}" \
    org.opencontainers.image.created="${BUILD_DATE}"

RUN apk add --no-cache \
    curl \
    python3 \
    py3-packaging \
    py3-websocket-client

COPY run.sh /run.sh
COPY register_resource.py /register_resource.py
COPY component_manager.py /component_manager.py
COPY backup_manager.py /backup_manager.py
COPY create_report.py /create_report.py
COPY checksum_utils.py /checksum_utils.py
COPY local_inventory.py /local_inventory.py
COPY compatibility_utils.py /compatibility_utils.py
COPY preflight_utils.py /preflight_utils.py
COPY preflight.py /preflight.py
COPY build_metadata.py /build_metadata.py
COPY components.json /components.json

RUN chmod a+x \
    /run.sh \
    /register_resource.py \
    /component_manager.py \
    /backup_manager.py \
    /create_report.py \
    /checksum_utils.py \
    /local_inventory.py \
    /compatibility_utils.py \
    /preflight_utils.py \
    /preflight.py \
    /build_metadata.py

CMD ["/run.sh"]
