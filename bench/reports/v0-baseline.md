# hushmark-bench v0 baseline

> Bu rapor yalnızca sentetik benchmark ölçümüdür; bir uyumluluk veya anonimleştirme
> iddiası değildir. Geri döndürülebilir maskeleme teknik bir güvenlik tedbiridir.

Dataset: `hushmark-bench-v0.jsonl` · examples: 2016 · SHA-256: `6170b620faa349dbcbf2f2a973d5de20e35c6594e5626a2a589d20df5f67d642`

## Recall-first summary

<!-- prettier-ignore -->
| Engine | Strict recall | Strict precision | Strict F1 | Partial recall | Partial F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| core | 0.548 | 0.929 | 0.689 | 0.571 | 0.719 |
| presidio-default | 0.228 | 0.775 | 0.353 | 0.228 | 0.353 |

## core

Model: `gliner_multi_pii-v1` · backend: `onnx` · duration: 56.427s

<!-- prettier-ignore -->
| Type | Gold | Strict R | Strict P | Strict F1 | Partial R | Partial F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BIOMETRIC_REF | 96 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| CRIMINAL | 96 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| DOB | 288 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| POLITICAL | 96 | 0.000 | 0.000 | 0.000 | 0.010 | 0.021 |
| SEXUAL_LIFE | 96 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| HEALTH | 240 | 0.008 | 1.000 | 0.017 | 0.008 | 0.017 |
| ADDRESS | 288 | 0.010 | 0.500 | 0.020 | 0.017 | 0.034 |
| UNION | 96 | 0.052 | 0.333 | 0.090 | 0.146 | 0.252 |
| RELIGION | 96 | 0.083 | 1.000 | 0.154 | 0.083 | 0.154 |
| PERSON | 864 | 0.124 | 0.566 | 0.203 | 0.205 | 0.336 |
| ETHNICITY | 96 | 0.146 | 0.700 | 0.241 | 0.146 | 0.241 |
| ORG | 192 | 0.208 | 0.256 | 0.230 | 0.411 | 0.454 |
| CREDIT_CARD | 240 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| EMAIL | 336 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| IBAN_OTHER | 192 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| SECRET_API_KEY | 96 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| SECRET_JWT | 96 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| SECRET_PRIVATE_KEY | 48 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| TR_IBAN | 240 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| TR_PHONE | 336 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| TR_PLATE | 240 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| TR_SGK | 240 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| TR_TCKN | 432 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| TR_VKN | 192 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## presidio-default

Model: `presidio-builtins-en` · backend: `builtins` · duration: 2.148s

<!-- prettier-ignore -->
| Type | Gold | Strict R | Strict P | Strict F1 | Partial R | Partial F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ADDRESS | 288 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| BIOMETRIC_REF | 96 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| CRIMINAL | 96 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| DOB | 288 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| ETHNICITY | 96 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| HEALTH | 240 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| ORG | 192 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| PERSON | 864 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| POLITICAL | 96 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| RELIGION | 96 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| SECRET_API_KEY | 96 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| SECRET_JWT | 96 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| SECRET_PRIVATE_KEY | 48 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| SEXUAL_LIFE | 96 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| TR_PLATE | 240 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| TR_SGK | 240 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| TR_TCKN | 432 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| TR_VKN | 192 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| UNION | 96 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| TR_PHONE | 336 | 0.554 | 0.349 | 0.428 | 0.554 | 0.428 |
| CREDIT_CARD | 240 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| EMAIL | 336 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| IBAN_OTHER | 192 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| TR_IBAN | 240 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## Method

Strict matching requires identical type and code-point offsets. Partial matching
requires the same type and any positive span overlap. Each prediction can match at
most one gold span. Macro values average only types with gold support.
