FROM ghcr.io/home-assistant/base:latest

RUN apk add --no-cache curl

COPY run.sh /

RUN chmod a+x /run.sh

CMD ["/run.sh"]
