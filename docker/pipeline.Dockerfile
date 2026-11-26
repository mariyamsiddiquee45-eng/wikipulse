# syntax=docker/dockerfile:1

FROM python:3.12-slim@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv==0.13.10

WORKDIR /app
COPY pipeline/pyproject.toml pipeline/uv.lock pipeline/.python-version ./pipeline/
COPY pipeline/src ./pipeline/src

WORKDIR /app/pipeline
RUN uv sync --frozen --no-dev --no-install-package torch \
    && uv pip install --python /app/pipeline/.venv/bin/python --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu "torch==2.15.0" \
    && /app/pipeline/.venv/bin/python -c "import duckdb, lightgbm, torch; print(torch.__version__)"

COPY schemas /app/schemas
COPY labels /app/labels

RUN useradd --uid 10001 --create-home wikipulse \
    && mkdir -p /app/data \
    && chown -R wikipulse:wikipulse /app

ENV PATH="/app/pipeline/.venv/bin:${PATH}" \
    WIKIPULSE_DATA_DIR=/app/data

USER wikipulse
WORKDIR /app

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD ["/app/pipeline/.venv/bin/python", "-c", "import wikipulse"]

ENTRYPOINT ["wikipulse"]
CMD ["--help"]
