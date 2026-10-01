# The API server, with llama.cpp built in and both GGUFs fetched at first use into the
# model_data volume (see docker-compose.yml at the repo root).
#
# 3.13 because that is the interpreter the code is developed and tested on.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# build-essential + cmake: llama-cpp-python compiles llama.cpp from source on install.
# curl: the deploy script's in-container health probe.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential cmake libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
# CPU-only torch first: the default index resolves the CUDA build, ~2 GB of libraries an
# EC2 CPU instance can never use. requirements.txt's torch pin is then already satisfied.
RUN pip install --upgrade pip \
    && pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.6" \
    && pip install -r requirements.txt

COPY app ./app
COPY learnmate ./learnmate
COPY server.py ./server.py

RUN mkdir -p /app/models /app/data/hf_cache

EXPOSE 8000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
