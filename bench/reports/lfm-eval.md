# hushmark-bench v0 baseline

> Bu rapor yalnızca sentetik benchmark ölçümüdür; bir uyumluluk veya anonimleştirme
> iddiası değildir. Geri döndürülebilir maskeleme teknik bir güvenlik tedbiridir.

Dataset: `hushmark-bench-v0.jsonl` · examples: 2016 · SHA-256: `6170b620faa349dbcbf2f2a973d5de20e35c6594e5626a2a589d20df5f67d642`

## Recall-first summary

<!-- prettier-ignore -->
| Engine | Strict recall | Strict precision | Strict F1 | Partial recall | Partial F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| core | 0.673 | 0.844 | 0.749 | 0.753 | 0.838 |

## core

Model: `lfm2.5-encoder-350m-pii` · backend: `torch` · duration: 656.917s

<!-- prettier-ignore -->
| Type | Gold | Strict R | Strict P | Strict F1 | Partial R | Partial F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BIOMETRIC_REF | 96 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| CRIMINAL | 96 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| ETHNICITY | 96 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| HEALTH | 240 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| SEXUAL_LIFE | 96 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| UNION | 96 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| ORG | 192 | 0.047 | 0.237 | 0.078 | 0.188 | 0.313 |
| POLITICAL | 96 | 0.052 | 0.161 | 0.079 | 0.323 | 0.488 |
| RELIGION | 96 | 0.125 | 0.400 | 0.190 | 0.281 | 0.429 |
| PERSON | 864 | 0.405 | 0.422 | 0.413 | 0.729 | 0.744 |
| ADDRESS | 288 | 0.757 | 0.722 | 0.739 | 0.951 | 0.929 |
| DOB | 288 | 0.837 | 0.949 | 0.889 | 0.878 | 0.934 |
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

## Method

Strict matching requires identical type and code-point offsets. Partial matching
requires the same type and any positive span overlap. Each prediction can match at
most one gold span. Macro values average only types with gold support.
