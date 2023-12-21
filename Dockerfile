# Stage 1: Use a base image to install ffmpeg
FROM jrottenberg/ffmpeg:4.1 as ffmpeg-base

# Stage 2: Build the final image
FROM python:3.8-slim

# Label for vendor
LABEL vendor=neon.ai \
    ai.neon.name="neon-iris"

# Build argument for specifying extras
ARG EXTRAS

ENV OVOS_CONFIG_BASE_FOLDER=neon \
    OVOS_CONFIG_FILENAME=neon.yaml \
    XDG_CONFIG_HOME=/config

# Copy ffmpeg binaries from the ffmpeg-base stage
COPY --from=ffmpeg-base /usr/local/bin/ /usr/local/bin/
COPY --from=ffmpeg-base /usr/local/lib/ /usr/local/lib/

RUN mkdir -p /neon_iris/requirements
COPY ./requirements/* /neon_iris/requirements

RUN pip install wheel && pip install -r /neon_iris/requirements/requirements.txt
RUN if [ "$EXTRAS" = "gradio" ]; then \
        pip install -r /neon_iris/requirements/gradio.txt; \
    elif [ "$EXTRAS" = "web_sat" ]; then \
        pip install -r /neon_iris/requirements/web_sat.txt; \
    else \
        pip install -r /neon_iris/requirements/requirements.txt; \
    fi

WORKDIR /neon_iris
ADD . /neon_iris
RUN pip install .

COPY docker_overlay/ /

# Expose port 8000 for websat
EXPOSE 8000

ENTRYPOINT ["iris"]

# Default command
CMD ["-h"]
