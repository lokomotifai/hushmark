# Third-party notices

This file is an attribution summary, not a replacement for dependency license texts. Exact locked
versions are in `pnpm-lock.yaml` and `uv.lock`; container base references are digest-pinned in the
Dockerfiles and Helm values.

| Component                                | Use                                      | License / notice source                                                         |
| ---------------------------------------- | ---------------------------------------- | ------------------------------------------------------------------------------- |
| GLiNER and `urchade/gliner_multi_pii-v1` | NER runtime and incumbent weights        | Apache-2.0; pinned model registry metadata                                      |
| Microsoft mDeBERTa v3 base               | tokenizer/encoder files                  | MIT; pinned model registry metadata                                             |
| Presidio Analyzer                        | deterministic recognizer framework       | MIT                                                                             |
| FastAPI, Uvicorn, Pydantic               | core HTTP and validation                 | MIT/BSD family; lockfiles are authoritative                                     |
| Fastify, Zod, Undici                     | gateway HTTP, schema, upstream transport | MIT                                                                             |
| Next.js and React                        | console                                  | MIT                                                                             |
| PostgreSQL                               | policy and audit database                | PostgreSQL License                                                              |
| HashiCorp Vault                          | evaluation and Transit adapter target    | Business Source License / product terms by version; not redistributed as source |
| DejaVu Sans                              | PDF fonts                                | DejaVu Fonts License                                                            |
| Faker synthetic providers                | benchmark generation                     | MIT                                                                             |

Before external distribution, regenerate SBOMs, retain their license fields, inspect any unknown or
copyleft entries, and attach the relevant upstream license texts to the delivery bundle.
