FROM ghcr.io/home-assistant/base:latest

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
