FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Build deps so wheels that need compilation (e.g. multidict/aiohttp) can build
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential gcc libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Prefer prebuilt wheels but still ok to build if needed
RUN python -m pip install --upgrade pip \
 && pip install --no-cache-dir --prefer-binary -r requirements.txt

COPY . .

EXPOSE 8080
