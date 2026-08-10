# syntax=docker/dockerfile:1.12

ARG PYTHON_IMAGE=python:3.12-slim@sha256:229a2c5bfa27522db7815ea81f9bed70af17ccb9de9fc7ad142b1877b5830d36

FROM ${PYTHON_IMAGE} AS build
ARG UV_VERSION=0.12.3
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /workspace
RUN python -m pip install --no-cache-dir "uv==${UV_VERSION}"
COPY pyproject.toml uv.lock .python-version ./
COPY bench/pyproject.toml bench/pyproject.toml
COPY core/pyproject.toml core/pyproject.toml
COPY sdk-py/pyproject.toml sdk-py/pyproject.toml
COPY tools/codegen/pyproject.toml tools/codegen/pyproject.toml
COPY core/src core/src
RUN uv sync --frozen --no-dev --no-editable --package hushmark-core

FROM build AS model-build
COPY core/models.yaml core/models.yaml
COPY tools/export-onnx.py tools/export-onnx.py
COPY models/hushmark-tr/gliner_config.json models/hushmark-tr/gliner_config.json
COPY models/hushmark-tr/model.onnx models/hushmark-tr/model.onnx
COPY models/hushmark-tr/tokenizer.json models/hushmark-tr/tokenizer.json
COPY models/hushmark-tr/tokenizer_config.json models/hushmark-tr/tokenizer_config.json
RUN uv run python tools/export-onnx.py \
      --model-id hushmark-tr \
      --output model.onnx \
      --verify-only

FROM ${PYTHON_IMAGE} AS runtime
ARG HUSHMARK_UID=10001
ARG HUSHMARK_GID=10001
RUN groupadd --gid "${HUSHMARK_GID}" hushmark \
    && useradd --uid "${HUSHMARK_UID}" --gid hushmark --no-create-home --shell /usr/sbin/nologin hushmark
RUN rm -rf /usr/local/lib/python3.12/site-packages/pip* /usr/local/bin/pip*
WORKDIR /opt/hushmark
COPY --from=build /opt/venv /opt/venv
COPY --chown=hushmark:hushmark core/models.yaml /opt/hushmark/core/models.yaml
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    HUSHMARK_CORE_MODEL_ROOT=/models \
    HUSHMARK_CORE_MODEL_REGISTRY=/opt/hushmark/core/models.yaml \
    HUSHMARK_CORE_NER_BACKEND=onnx
USER hushmark:hushmark
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=60s --retries=5 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).read()"]
ENTRYPOINT ["hushmark-core"]

FROM runtime AS model
COPY --from=model-build --chown=hushmark:hushmark /workspace/models /models

FROM runtime AS slim
VOLUME ["/models"]
