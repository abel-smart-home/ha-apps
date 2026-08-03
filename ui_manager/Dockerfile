FROM ghcr.io/home-assistant/base:latest

ARG BUILD_ARCH
ARG BUILD_VERSION

LABEL \
    io.hass.name="Smart Home UI Manager" \
    io.hass.description="Instala, valida, diagnostica, genera inventarios y restaura componentes personalizados para Home Assistant" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="app" \
    io.hass.version="${BUILD_VERSION}"

RUN apk add --no-cache \
    curl \
    python3 \
    py3-packaging \
    py3-websocket-client

COPY run.sh /run.sh
COPY register_resource.py /register_resource.py
COPY component_manager.py /component_manager.py
COPY backup_manager.py /backup_manager.py
COPY backup_test.py /backup_test.py
COPY create_report.py /create_report.py
COPY checksum_utils.py /checksum_utils.py
COPY local_inventory.py /local_inventory.py
COPY compatibility_utils.py /compatibility_utils.py
COPY compatibility_test.py /compatibility_test.py
COPY preflight_utils.py /preflight_utils.py
COPY preflight.py /preflight.py
COPY preflight_test.py /preflight_test.py
COPY components.json /components.json

RUN chmod a+x \
    /run.sh \
    /register_resource.py \
    /component_manager.py \
    /backup_manager.py \
    /backup_test.py \
    /create_report.py \
    /checksum_utils.py \
    /local_inventory.py \
    /compatibility_utils.py \
    /compatibility_test.py \
    /preflight_utils.py \
    /preflight.py \
    /preflight_test.py

CMD ["/run.sh"]
