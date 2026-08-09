# syntax=docker/dockerfile:1.12

ARG BASE_IMAGE=hushmark/core:0.1.0
FROM ${BASE_IMAGE}

COPY --chown=10001:10001 \
  gliner_config.json \
  gliner_config.source.json \
  model_quantized.onnx \
  tokenizer.json \
  tokenizer_config.json \
  /models/gliner_multi_pii-v1/
