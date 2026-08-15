# NER model selection

The detector model is selected with `HUSHMARK_CORE_MODEL_ID`. Every selectable model is
declared in `core/models.yaml` with pinned file sizes and SHA-256 digests; artifacts that
fail verification are refused at startup. `GET /v1/metadata` reports the active model and
the list of selectable models.

## Selectable models

| Model id                  | Architecture         | License    | Backends    | NER coverage | Notes                                    |
| ------------------------- | -------------------- | ---------- | ----------- | ------------ | ---------------------------------------- |
| `hushmark-tr` (default)   | gliner               | Apache-2.0 | torch, onnx | 12/12 types  | Turkish-trained production model         |
| `gliner_multi_pii-v1`     | gliner               | Apache-2.0 | torch, onnx | 12/12 types  | Upstream multilingual baseline           |
| `lfm2.5-encoder-350m-pii` | token-classification | lfm1.0     | torch       | 8/12 types   | Multilingual; **not trained on Turkish** |

`mdeberta-v3-base` also appears in the registry, but it is a tokenizer dependency only.
Selecting it fails at startup with an error that lists the selectable model ids.

The deterministic layer (TCKN, VKN, IBAN, credit card, phone, secrets, and the other
validator-backed types) runs identically regardless of the selected NER model.

## Switching models

- Environment: `HUSHMARK_CORE_MODEL_ID=<model-id>` (and `HUSHMARK_CORE_NER_BACKEND=torch`
  for models without a pinned ONNX export).
- Docker Compose (production): set `HUSHMARK_CORE_MODEL_ID` and `HUSHMARK_CORE_NER_BACKEND`
  in the compose environment; the defaults remain `hushmark-tr` and `onnx`.
- Helm: set `core.modelId`. The model files must be present in the model volume under
  `/models/<model-id>/` (see `docs/install-helm.md`).

Model files are fetched with:

```bash
uv run python scripts/fetch-models.py <model-id>
```

Without arguments the script fetches every model not marked `optional: true` in the
registry, which preserves the previous behavior and never downloads
`lfm2.5-encoder-350m-pii` implicitly.

## `lfm2.5-encoder-350m-pii` (LiquidAI LFM2.5-Encoder-350M-PII-Detector)

A 350M-parameter bidirectional encoder fine-tuned for PII token classification across
40 entity types and 16 languages, running on the torch backend with BIOES decoding.

Read these constraints before selecting it:

- **License (lfm1.0, LFM Open License v1.0).** Hushmark does not redistribute these
  weights in images, release artifacts, or the public mirror; `scripts/fetch-models.py`
  downloads them directly from the upstream Hugging Face repository under that license.
  The license restricts commercial use above an annual revenue threshold — review it
  before production use.
- **Not trained on Turkish.** Turkish is not among the model's training languages.
  Expect materially lower recall on Turkish text; `hushmark-tr` remains the default and
  the recommended model for Turkish traffic.
- **Partial taxonomy coverage (8/12 NER types).** The model has no labels for
  `ETHNICITY`, `CRIMINAL`, `BIOMETRIC_REF`, or `UNION`; those types are simply never
  detected when this model is selected. Model labels outside the hushmark taxonomy
  (emails, IBANs, card numbers, credentials, and similar) are dropped by the decoder —
  the deterministic layer owns those types.
- **Pinned remote code.** Loading executes the repository's `modeling_phase2_tc.py`
  via `trust_remote_code`. The file is size- and SHA-256-pinned in `core/models.yaml`,
  verified before the transformers import, and loaded from local files only with
  Hugging Face offline mode forced.
- **Uncalibrated thresholds.** Token-classification softmax scores are distributed
  differently from GLiNER span scores. The default `HUSHMARK_CORE_NER_THRESHOLD=0.55`
  is not calibrated for this model; re-tune thresholds against representative data
  when switching.

### Measured Turkish baseline

A full run against the locked Turkish synthetic benchmark (`hushmark-bench-v0`, 2016
examples, torch backend, default 0.55 threshold) is committed at
`bench/reports/lfm-eval.md`. Strict micro F1 is 0.749, but that number is carried by the
model-independent deterministic layer; the NER layer confirms the warning above —
PERSON strict F1 0.41, ADDRESS 0.74, DOB 0.89, ORG 0.08, and 0.00 for HEALTH,
SEXUAL_LIFE, and every type the model has no labels for. For comparison, the adopted
`hushmark-tr` model reports NER macro strict F1 0.9941 on the same benchmark
(`docs/model-card-hushmark-tr.md`).

Detection quality differs per model and language. Validate the selected model against
representative data with `bench/run.py` before relying on it.
