FROM python:3.8-slim

LABEL vendor=neon.ai \
    ai.neon.name="neon-iris"

ENV OVOS_CONFIG_BASE_FOLDER neon
ENV OVOS_CONFIG_FILENAME neon.yaml
ENV XDG_CONFIG_HOME /config

RUN apt update && \
    apt install -y ffmpeg

ADD . /neon_iris
WORKDIR /neon_iris

RUN pip install wheel && \
    pip install .[gradio]

COPY docker_overlay/ /

CMD ["iris", "start-gradio"]