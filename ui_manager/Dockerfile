FROM ghcr.io/home-assistant/base:latest

ARG BUILD_ARCH
ARG BUILD_VERSION

LABEL \
    io.hass.name="Smart Home UI Manager" \
    io.hass.description="Instala y administra componentes personalizados para Home Assistant" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="app" \
    io.hass.version="${BUILD_VERSION}"

RUN apk add --no-cache \
    curl \
    python3 \
    py3-websocket-client

COPY run.sh /run.sh
COPY register_resource.py /register_resource.py

RUN chmod a+x \
    /run.sh \
    /register_resource.py

CMD ["/run.sh"]
