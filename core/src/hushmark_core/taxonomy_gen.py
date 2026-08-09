# GENERATED — do not edit. Source: taxonomy/taxonomy.yaml

from __future__ import annotations

from typing import Final, Literal, TypedDict


class TaxonomyEntry(TypedDict):
    layer: Literal["deterministic", "ner"]
    kvkk_class: Literal["general", "special", "secret"]
    z_class: Literal["Z0", "Z1", "Z2", "Z3", "Z4", "Z5"]
    default_action: Literal["mask", "redact", "block", "allow"]
    tr_label: str


TAXONOMY_VERSION: Final = 1
ENTITY_TYPES: Final = ('TR_TCKN',
 'TR_VKN',
 'TR_IBAN',
 'IBAN_OTHER',
 'CREDIT_CARD',
 'TR_PHONE',
 'TR_PLATE',
 'TR_SGK',
 'EMAIL',
 'SECRET_API_KEY',
 'SECRET_JWT',
 'SECRET_PRIVATE_KEY',
 'PERSON',
 'ADDRESS',
 'ORG',
 'DOB',
 'HEALTH',
 'RELIGION',
 'ETHNICITY',
 'POLITICAL',
 'SEXUAL_LIFE',
 'CRIMINAL',
 'BIOMETRIC_REF',
 'UNION')
TAXONOMY: Final[dict[str, TaxonomyEntry]] = {
    "TR_TCKN": {
        "layer": "deterministic",
        "kvkk_class": "general",
        "z_class": "Z3",
        "default_action": "mask",
        "tr_label": "TCKN"
    },
    "TR_VKN": {
        "layer": "deterministic",
        "kvkk_class": "general",
        "z_class": "Z3",
        "default_action": "mask",
        "tr_label": "VKN"
    },
    "TR_IBAN": {
        "layer": "deterministic",
        "kvkk_class": "general",
        "z_class": "Z3",
        "default_action": "mask",
        "tr_label": "IBAN"
    },
    "IBAN_OTHER": {
        "layer": "deterministic",
        "kvkk_class": "general",
        "z_class": "Z3",
        "default_action": "mask",
        "tr_label": "IBAN"
    },
    "CREDIT_CARD": {
        "layer": "deterministic",
        "kvkk_class": "general",
        "z_class": "Z5",
        "default_action": "block",
        "tr_label": "KART"
    },
    "TR_PHONE": {
        "layer": "deterministic",
        "kvkk_class": "general",
        "z_class": "Z2",
        "default_action": "mask",
        "tr_label": "TEL"
    },
    "TR_PLATE": {
        "layer": "deterministic",
        "kvkk_class": "general",
        "z_class": "Z2",
        "default_action": "mask",
        "tr_label": "PLAKA"
    },
    "TR_SGK": {
        "layer": "deterministic",
        "kvkk_class": "general",
        "z_class": "Z3",
        "default_action": "mask",
        "tr_label": "SGK"
    },
    "EMAIL": {
        "layer": "deterministic",
        "kvkk_class": "general",
        "z_class": "Z2",
        "default_action": "mask",
        "tr_label": "EPOSTA"
    },
    "SECRET_API_KEY": {
        "layer": "deterministic",
        "kvkk_class": "secret",
        "z_class": "Z5",
        "default_action": "block",
        "tr_label": "SIR"
    },
    "SECRET_JWT": {
        "layer": "deterministic",
        "kvkk_class": "secret",
        "z_class": "Z5",
        "default_action": "block",
        "tr_label": "SIR"
    },
    "SECRET_PRIVATE_KEY": {
        "layer": "deterministic",
        "kvkk_class": "secret",
        "z_class": "Z5",
        "default_action": "block",
        "tr_label": "SIR"
    },
    "PERSON": {
        "layer": "ner",
        "kvkk_class": "general",
        "z_class": "Z2",
        "default_action": "mask",
        "tr_label": "KISI"
    },
    "ADDRESS": {
        "layer": "ner",
        "kvkk_class": "general",
        "z_class": "Z2",
        "default_action": "mask",
        "tr_label": "ADRES"
    },
    "ORG": {
        "layer": "ner",
        "kvkk_class": "general",
        "z_class": "Z1",
        "default_action": "allow",
        "tr_label": "KURUM"
    },
    "DOB": {
        "layer": "ner",
        "kvkk_class": "general",
        "z_class": "Z2",
        "default_action": "mask",
        "tr_label": "DOGUM"
    },
    "HEALTH": {
        "layer": "ner",
        "kvkk_class": "special",
        "z_class": "Z5",
        "default_action": "block",
        "tr_label": "SAGLIK"
    },
    "RELIGION": {
        "layer": "ner",
        "kvkk_class": "special",
        "z_class": "Z5",
        "default_action": "block",
        "tr_label": "INANC"
    },
    "ETHNICITY": {
        "layer": "ner",
        "kvkk_class": "special",
        "z_class": "Z5",
        "default_action": "block",
        "tr_label": "KOKEN"
    },
    "POLITICAL": {
        "layer": "ner",
        "kvkk_class": "special",
        "z_class": "Z5",
        "default_action": "block",
        "tr_label": "GORUS"
    },
    "SEXUAL_LIFE": {
        "layer": "ner",
        "kvkk_class": "special",
        "z_class": "Z5",
        "default_action": "block",
        "tr_label": "MAHREM"
    },
    "CRIMINAL": {
        "layer": "ner",
        "kvkk_class": "special",
        "z_class": "Z5",
        "default_action": "block",
        "tr_label": "SABIKA"
    },
    "BIOMETRIC_REF": {
        "layer": "ner",
        "kvkk_class": "special",
        "z_class": "Z5",
        "default_action": "block",
        "tr_label": "BIYOMETRI"
    },
    "UNION": {
        "layer": "ner",
        "kvkk_class": "special",
        "z_class": "Z5",
        "default_action": "block",
        "tr_label": "UYELIK"
    }
}
