FROM python:3.10-slim

# Label for vendor
LABEL vendor=neon.ai \
    ai.neon.name="neon-iris"

# Build argument for specifying extras
ARG EXTRAS

ENV OVOS_CONFIG_BASE_FOLDER=neon \
    OVOS_CONFIG_FILENAME=neon.yaml \
    XDG_CONFIG_HOME=/config
# Set the ARG value as an environment variable
ENV EXTRAS=${EXTRAS}

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

RUN apt-get update \
  && apt-get install -y libsndfile1 libasound2 ffmpeg \
  && apt-get --purge autoremove -y \
  && apt-get clean \
  && rm -rf "${HOME}"/.cache /var/lib/apt /var/log/{apt,dpkg.log}

# Create a non-root user with a home directory and change ownership of necessary directories

RUN groupadd -r neon && useradd -r -m -g neon neon \
    && mkdir -p /config/neon \
    && chown -R neon:neon /neon_iris /usr/local/bin /config

# Use the non-root user to run the container
USER neon

ENTRYPOINT ["/neon_iris/entrypoint.sh"]
