# Third-party notices

This file is an attribution summary, not a replacement for dependency license texts. Exact locked
versions are in `pnpm-lock.yaml` and `uv.lock`; pinned model metadata is in `core/models.yaml`.

| Component                                | Use                                          | License / notice source                     |
| ---------------------------------------- | -------------------------------------------- | ------------------------------------------- |
| GLiNER and `urchade/gliner_multi_pii-v1` | NER runtime and incumbent weights            | Apache-2.0; pinned model registry metadata  |
| Microsoft mDeBERTa v3 base               | Tokenizer/encoder files                      | MIT; pinned model registry metadata         |
| Presidio Analyzer                        | Deterministic recognizer framework           | MIT                                         |
| FastAPI, Uvicorn, Pydantic               | Core HTTP and validation                     | MIT/BSD family; lockfiles are authoritative |
| Fastify, Zod, Undici                     | Gateway HTTP, schema, and upstream transport | MIT                                         |
| Faker synthetic providers                | Benchmark generation                         | MIT                                         |

For every external distribution, regenerate SBOMs, retain their license fields, inspect any unknown
or copyleft entries, and attach the relevant upstream license texts to the delivery bundle.
