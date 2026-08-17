# hushmark-bench · çok motorlu karşılaştırma

> Bu rapor sentetik bir veri kümesi üzerinde yapılmış bir ölçümdür; bir uyumluluk,
> anonimleştirme veya üstünlük iddiası değildir. Geri döndürülebilir maskeleme
> teknik bir güvenlik tedbiridir, KVKK anlamında anonimleştirme değildir.

Veri kümesi: `hushmark-bench-v0.jsonl` · örnek: 2016 · SHA-256: `6170b620faa349dbcbf2f2a973d5de20e35c6594e5626a2a589d20df5f67d642`

## Genel özet (recall öncelikli)

<!-- prettier-ignore -->
| Motor | Model | Çalışma | Strict R | Strict P | Strict F1 | Partial R |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| core-hushmark-tr-onnx | `hushmark-tr` | yerel | 0.995 | 0.996 | 0.996 | 0.997 |
| core-hushmark-tr-torch | `hushmark-tr` | yerel | 0.995 | 0.997 | 0.996 | 0.997 |
| openai-gpt-5-4-mini | `gpt-5.4-mini` | üçüncü taraf API | 0.865 | 0.851 | 0.858 | 0.978 |
| core-gliner-multi-pii-v1-torch | `gliner_multi_pii-v1` | yerel | 0.858 | 0.858 | 0.858 | 0.960 |
| gliner-raw-hushmark-tr | `hushmark-tr` | yerel | 0.617 | 0.931 | 0.742 | 0.630 |
| gliner-raw-gliner-multi-pii-v1 | `gliner_multi_pii-v1` | yerel | 0.537 | 0.661 | 0.593 | 0.672 |
| presidio-tr | `presidio-builtins+akdeniz27/bert-base-turkish-cased-ner` | yerel | 0.343 | 0.579 | 0.431 | 0.477 |
| presidio-default | `presidio-builtins-en` | yerel | 0.228 | 0.775 | 0.353 | 0.228 |

## Karar kriterleri

<!-- prettier-ignore -->
| Motor | TR kimlik recall | Özel nitelikli recall | Tip kapsamı | p50 gecikme | p95 gecikme |
| --- | ---: | ---: | ---: | ---: | ---: |
| core-hushmark-tr-onnx | 1.000 | 0.995 | 24/24 | 18.3 ms | 28.3 ms |
| core-hushmark-tr-torch | 1.000 | 0.995 | 24/24 | 41.5 ms | 49.7 ms |
| openai-gpt-5-4-mini | 0.971 | 0.691 | 24/24 | 1044.4 ms | 1476.0 ms |
| core-gliner-multi-pii-v1-torch | 1.000 | 0.640 | 24/24 | 44.4 ms | 51.8 ms |
| gliner-raw-hushmark-tr | 0.322 | 0.989 | 19/24 | 48.9 ms | 57.9 ms |
| gliner-raw-gliner-multi-pii-v1 | 0.457 | 0.583 | 22/24 | 48.7 ms | 55.1 ms |
| presidio-tr | 0.444 | 0.000 | 8/24 | 14.5 ms | 21.0 ms |
| presidio-default | 0.444 | 0.000 | 5/24 | 0.4 ms | 0.8 ms |

## Türkçe morfoloji dayanıklılığı (strict recall)

<!-- prettier-ignore -->
| Motor | plain | name_suffix | missing_diacritics | lowercase_context |
| --- | ---: | ---: | ---: | ---: |
| core-hushmark-tr-onnx | 0.995 | 0.996 | 0.991 | 0.998 |
| core-hushmark-tr-torch | 0.995 | 0.996 | 0.991 | 0.998 |
| openai-gpt-5-4-mini | 0.885 | 0.762 | 0.896 | 0.916 |
| core-gliner-multi-pii-v1-torch | 0.880 | 0.755 | 0.869 | 0.930 |
| gliner-raw-hushmark-tr | 0.617 | 0.626 | 0.596 | 0.628 |
| gliner-raw-gliner-multi-pii-v1 | 0.534 | 0.475 | 0.514 | 0.625 |
| presidio-tr | 0.378 | 0.258 | 0.357 | 0.381 |
| presidio-default | 0.229 | 0.228 | 0.222 | 0.234 |

## Tip bazlı strict recall

<!-- prettier-ignore -->
| Tip | Gold | core-hushmark-tr-onnx | core-hushmark-tr-torch | openai-gpt-5-4-mini | core-gliner-multi-pii-v1-torch | gliner-raw-hushmark-tr | gliner-raw-gliner-multi-pii-v1 | presidio-tr | presidio-default |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ADDRESS | 288 | 0.986 | 0.986 | 0.997 | 0.924 | 0.983 | 0.944 | 0.000 | 0.000 |
| BIOMETRIC_REF | 96 | 1.000 | 1.000 | 0.604 | 0.042 | 1.000 | 0.031 | 0.000 | 0.000 |
| CREDIT_CARD | 240 | 1.000 | 1.000 | 1.000 | 1.000 | 0.075 | 0.175 | 1.000 | 1.000 |
| CRIMINAL | 96 | 1.000 | 1.000 | 0.323 | 0.125 | 0.958 | 0.229 | 0.000 | 0.000 |
| DOB | 288 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 |
| EMAIL | 336 | 1.000 | 1.000 | 0.994 | 1.000 | 0.652 | 0.970 | 1.000 | 1.000 |
| ETHNICITY | 96 | 1.000 | 1.000 | 0.531 | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 |
| HEALTH | 240 | 1.000 | 1.000 | 0.938 | 0.917 | 1.000 | 0.721 | 0.000 | 0.000 |
| IBAN_OTHER | 192 | 1.000 | 1.000 | 0.979 | 1.000 | 0.000 | 0.062 | 1.000 | 1.000 |
| ORG | 192 | 0.979 | 0.979 | 0.786 | 0.573 | 0.979 | 0.557 | 0.797 | 0.000 |
| PERSON | 864 | 0.985 | 0.985 | 0.648 | 0.642 | 0.812 | 0.442 | 0.521 | 0.000 |
| POLITICAL | 96 | 1.000 | 1.000 | 0.740 | 0.562 | 0.990 | 0.479 | 0.000 | 0.000 |
| RELIGION | 96 | 1.000 | 1.000 | 1.000 | 0.958 | 1.000 | 0.938 | 0.000 | 0.000 |
| SECRET_API_KEY | 96 | 1.000 | 1.000 | 1.000 | 1.000 | 0.667 | 0.969 | 0.000 | 0.000 |
| SECRET_JWT | 96 | 1.000 | 1.000 | 0.990 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| SECRET_PRIVATE_KEY | 48 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| SEXUAL_LIFE | 96 | 0.948 | 0.948 | 1.000 | 0.885 | 0.948 | 0.906 | 0.000 | 0.000 |
| TR_IBAN | 240 | 1.000 | 1.000 | 0.996 | 1.000 | 0.129 | 0.754 | 1.000 | 1.000 |
| TR_PHONE | 336 | 1.000 | 1.000 | 1.000 | 1.000 | 0.994 | 1.000 | 0.554 | 0.554 |
| TR_PLATE | 240 | 1.000 | 1.000 | 0.996 | 1.000 | 0.829 | 0.762 | 0.000 | 0.000 |
| TR_SGK | 240 | 1.000 | 1.000 | 0.708 | 1.000 | 0.000 | 0.229 | 0.000 | 0.000 |
| TR_TCKN | 432 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| TR_VKN | 192 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| UNION | 96 | 1.000 | 1.000 | 0.021 | 0.219 | 1.000 | 0.156 | 0.000 | 0.000 |

## Yöntem

Strict eşleşme aynı tip ve birebir aynı kod noktası ofsetlerini gerektirir; partial
eşleşme aynı tip ve herhangi bir örtüşme ile sağlanır. Her tahmin en fazla bir gold
span ile eşleşir. `TR kimlik recall` deterministik kimlik tiplerinin (TCKN, VKN, IBAN,
SGK, plaka, telefon, e-posta, kart, sır) toplam micro recall değeridir. `Özel nitelikli
recall` KVKK m.6 kapsamındaki sağlık, din, etnik köken, siyasi görüş, cinsel hayat,
ceza mahkûmiyeti, biyometri ve sendika tiplerinin micro recall değeridir. Gecikme
değerleri tek iş parçacıklı CPU üzerinde örnek başına ölçülmüştür.
