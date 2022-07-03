FROM python:3.9.1-alpine

ENV port 9766



LABEL org.label-schema.schema-version="1.0" \
      org.label-schema.name="homeconnect_webthing" \
      org.label-schema.description=" " \
      org.label-schema.url="https://github.com/grro/homeconnect_webthing" \
      org.label-schema.docker.cmd="docker run -p 9766:9766 grro/homeconnect_webthing"


RUN apk add build-base
ADD . /tmp/
WORKDIR /tmp/
RUN  python /tmp/setup.py install
WORKDIR /
RUN rm -r /tmp/

CMD homeconnect --command listen --port $port