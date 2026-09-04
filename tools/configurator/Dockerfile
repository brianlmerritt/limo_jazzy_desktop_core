FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock

RUN python -m pip install --no-cache-dir --requirement /tmp/requirements.lock

COPY limo_config /opt/limo-configurator/limo_config

ENV PYTHONPATH=/opt/limo-configurator

ENTRYPOINT ["python", "-m", "limo_config"]
