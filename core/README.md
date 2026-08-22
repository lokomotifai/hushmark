# hushmark-core

Turkish-first PII detection and reversible masking engine used by the self-hosted Hushmark
gateway.

```bash
pip install hushmark-core
```

The package includes deterministic Turkish validators and the model runtime. Production model
weights are distributed separately and must be installed according to the model card and verified
against the published digest before selecting the ONNX backend.

The private `hushmark-berturk-112m` challenger has a native integrity-checked PyTorch backend.
See [`docs/model-card-hushmark-berturk-112m.md`](../docs/model-card-hushmark-berturk-112m.md) for its
fixed Hugging Face revision, installation command, configuration, evaluation, and limitations.

Reversible masking is a technical security measure. It is not anonymization or a guarantee of
legal compliance, and detection can miss or misclassify content. Evaluate the published benchmark
and representative local data before production use.

Licensed under Apache-2.0.

The HTTP service is authenticated by default. Set a 32-character-or-longer
`HUSHMARK_CORE_SERVICE_TOKEN`, or opt into unauthenticated local development with
`HUSHMARK_CORE_ALLOW_UNAUTHENTICATED=true` while binding only to loopback.
