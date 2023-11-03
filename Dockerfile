FROM python:3.8-slim

LABEL vendor=neon.ai \
    ai.neon.name="neon-iris"

ENV OVOS_CONFIG_BASE_FOLDER neon
ENV OVOS_CONFIG_FILENAME diana.yaml
ENV XDG_CONFIG_HOME /config

ADD . /neon_iris
WORKDIR /neon_iris

RUN pip install wheel && \
    pip install .[docker]

COPY docker_overlay/ /

CMD ["iris", "start-gradio"]