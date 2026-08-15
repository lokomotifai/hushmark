from __future__ import annotations

import string
import time

import pytest
from hushmark_core.recognizers.credit_card import detect_credit_card, validate_credit_card
from hushmark_core.recognizers.email import validate_email
from hushmark_core.recognizers.iban import validate_iban
from hushmark_core.recognizers.phone import LANDLINE_PREFIXES, detect_tr_phone, validate_tr_phone
from hushmark_core.recognizers.plate import validate_tr_plate
from hushmark_core.recognizers.secrets import (
    detect_secrets,
    validate_api_key,
    validate_jwt,
    validate_private_key,
)
from hushmark_core.recognizers.sgk import detect_tr_sgk, validate_tr_sgk
from hushmark_core.recognizers.tckn import detect_tckn, validate_tckn
from hushmark_core.recognizers.vkn import calculate_vkn_checksum, detect_vkn, validate_vkn


def build_tckn(seed: int) -> str:
    first_nine = f"{seed:09d}"
    if first_nine[0] == "0":
        first_nine = "1" + first_nine[1:]
    digits = [int(char) for char in first_nine]
    tenth = (7 * sum(digits[0:9:2]) - sum(digits[1:8:2])) % 10
    eleventh = (sum(digits) + tenth) % 10
    return first_nine + str(tenth) + str(eleventh)


def mutate_last_digit(value: str) -> str:
    return value[:-1] + str((int(value[-1]) + 1) % 10)


def make_iban(country: str, bban: str) -> str:
    country_digits = "".join(str(ord(char) - 55) for char in country)
    remainder = int(bban + country_digits + "00") % 97
    return f"{country}{98 - remainder:02d}{bban}"


def add_luhn_digit(prefix: str) -> str:
    for digit in string.digits:
        candidate = prefix + digit
        if validate_credit_card(candidate):
            return candidate
    raise AssertionError("no Luhn digit found")


VALID_TCKN = [build_tckn(100_000_000 + index * 7_919) for index in range(20)]
VALID_VKN = [
    first_nine + str(calculate_vkn_checksum(first_nine))
    for first_nine in (f"{index * 43_219 + 10_000_000:09d}" for index in range(20))
]
VALID_TR_IBAN = [make_iban("TR", f"{index + 1:022d}") for index in range(20)]
VALID_OTHER_IBAN = [make_iban("DE", f"{index + 1:018d}") for index in range(20)]
VALID_CARDS = [add_luhn_digit(f"4{index + 1:014d}") for index in range(20)]
VALID_PHONES = [
    f"+90 {prefix} {index + 100:03d} {index + 2000:04d}"
    for index, prefix in enumerate(sorted(LANDLINE_PREFIXES)[:20])
]
VALID_PLATES = [f"{province:02d} AB {province + 100:03d}" for province in range(1, 21)]
VALID_SGK = [f"{index + 1:013d}" for index in range(20)]
VALID_EMAILS = [f"kullanici.{index}+destek@example{index}.com" for index in range(20)]
VALID_API_KEYS = [f"sk-hM{index:02d}A9_zY7qP4rT8uV2wX6cN5" for index in range(20)]
VALID_JWTS = [
    f"eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI{index:02d}In0.signature{index:02d}" for index in range(20)
]


@pytest.mark.parametrize("value", VALID_TCKN)
def test_tckn_accepts_valid_vectors(value: str) -> None:
    assert validate_tckn(value)


@pytest.mark.parametrize("value", [mutate_last_digit(value) for value in VALID_TCKN])
def test_tckn_rejects_invalid_checksum_vectors(value: str) -> None:
    assert not validate_tckn(value)


@pytest.mark.parametrize(
    "render",
    [
        lambda value: " ".join(value),
        lambda value: ".".join(value),
        lambda value: "\u200b".join(value),
        lambda value: "\u00a0".join(value),
        lambda value: "".join(chr(0x0660 + int(char)) for char in value),
        lambda value: "".join(chr(0xFF10 + int(char)) for char in value),
    ],
)
def test_tckn_detects_separator_and_unicode_variants(render) -> None:
    rendered = render("10000000078")
    hits = detect_tckn(f"TCKN: {rendered}")
    assert len(hits) == 1
    assert hits[0].end - hits[0].start == len(rendered)


@pytest.mark.parametrize("value", VALID_VKN)
def test_vkn_accepts_valid_vectors(value: str) -> None:
    assert validate_vkn(value)


@pytest.mark.parametrize("value", [mutate_last_digit(value) for value in VALID_VKN])
def test_vkn_rejects_invalid_checksum_vectors(value: str) -> None:
    assert not validate_vkn(value)


def test_vkn_detects_formatted_unicode_digits() -> None:
    value = VALID_VKN[0]
    rendered = "\u00a0".join(chr(0xFF10 + int(char)) for char in value)
    assert len(detect_vkn(f"VKN: {rendered}")) == 1


@pytest.mark.parametrize("value", VALID_TR_IBAN + VALID_OTHER_IBAN)
def test_iban_accepts_valid_vectors(value: str) -> None:
    formatted = " ".join(value[index : index + 4] for index in range(0, len(value), 4))
    assert validate_iban(value)
    assert validate_iban(formatted)


@pytest.mark.parametrize(
    "value", [value[:2] + "00" + value[4:] for value in VALID_TR_IBAN + VALID_OTHER_IBAN]
)
def test_iban_rejects_invalid_checksum_vectors(value: str) -> None:
    assert not validate_iban(value)


@pytest.mark.parametrize("value", VALID_CARDS)
def test_credit_card_accepts_valid_vectors(value: str) -> None:
    formatted = " ".join(value[index : index + 4] for index in range(0, len(value), 4))
    assert validate_credit_card(value)
    assert validate_credit_card(formatted)


@pytest.mark.parametrize("value", [mutate_last_digit(value) for value in VALID_CARDS])
def test_credit_card_rejects_invalid_checksum_vectors(value: str) -> None:
    assert not validate_credit_card(value)


@pytest.mark.parametrize("base", [0x0660, 0x06F0, 0xFF10])
def test_credit_card_detects_unicode_decimal_digits(base: int) -> None:
    value = VALID_CARDS[0]
    rendered = "".join(chr(base + int(char)) for char in value)
    hits = detect_credit_card(f"Kart: {rendered}")
    assert len(hits) == 1
    assert hits[0].end - hits[0].start == len(rendered)


@pytest.mark.parametrize("value", VALID_PHONES)
def test_phone_accepts_valid_vectors(value: str) -> None:
    assert validate_tr_phone(value)


@pytest.mark.parametrize("value", [f"+90 999 {index:07d}" for index in range(20)])
def test_phone_rejects_invalid_prefix_vectors(value: str) -> None:
    assert not validate_tr_phone(value)


@pytest.mark.parametrize("base", [0x0660, 0x06F0, 0xFF10])
def test_phone_detects_unicode_decimal_digits(base: int) -> None:
    value = "05321234567"
    rendered = "".join(chr(base + int(char)) for char in value)
    hits = detect_tr_phone(f"Telefon: {rendered}")
    assert len(hits) == 1
    assert hits[0].end - hits[0].start == len(rendered)


@pytest.mark.parametrize("value", VALID_PLATES)
def test_plate_accepts_valid_vectors(value: str) -> None:
    assert validate_tr_plate(value)


@pytest.mark.parametrize("value", [f"{province + 81} AB 123" for province in range(1, 21)])
def test_plate_rejects_invalid_province_vectors(value: str) -> None:
    assert not validate_tr_plate(value)


@pytest.mark.parametrize("value", VALID_SGK)
def test_sgk_accepts_valid_vectors(value: str) -> None:
    assert validate_tr_sgk(value)


@pytest.mark.parametrize("value", [f"{index + 1:012d}" for index in range(20)])
def test_sgk_rejects_invalid_length_vectors(value: str) -> None:
    assert not validate_tr_sgk(value)


def test_sgk_detects_formatted_digits_with_context() -> None:
    rendered = ".".join("0000000000001")
    hits = detect_tr_sgk(f"SGK sicil: {rendered}")
    assert len(hits) == 1
    assert hits[0].score == 0.88


@pytest.mark.parametrize("value", VALID_EMAILS)
def test_email_accepts_valid_vectors(value: str) -> None:
    assert validate_email(value)


@pytest.mark.parametrize("value", [f"kullanici..{index}@example.com" for index in range(20)])
def test_email_rejects_invalid_vectors(value: str) -> None:
    assert not validate_email(value)


@pytest.mark.parametrize("value", VALID_API_KEYS)
def test_api_key_accepts_high_entropy_vectors(value: str) -> None:
    assert validate_api_key(value)


@pytest.mark.parametrize("value", [f"sk-{'a' * 20}{index % 10}" for index in range(20)])
def test_api_key_rejects_low_entropy_vectors(value: str) -> None:
    assert not validate_api_key(value)


@pytest.mark.parametrize("value", VALID_JWTS)
def test_jwt_accepts_structural_vectors(value: str) -> None:
    assert validate_jwt(value)


@pytest.mark.parametrize("value", [f"not-a-jwt-{index}" for index in range(20)])
def test_jwt_rejects_invalid_vectors(value: str) -> None:
    assert not validate_jwt(value)


@pytest.mark.parametrize("index", range(20))
def test_private_key_accepts_matching_pem_vectors(index: int) -> None:
    payload = (f"QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo{index:02d}" * 2)[:64]
    value = f"-----BEGIN PRIVATE KEY-----\n{payload}\n-----END PRIVATE KEY-----"
    assert validate_private_key(value)


@pytest.mark.parametrize("index", range(20))
def test_private_key_rejects_mismatched_pem_vectors(index: int) -> None:
    payload = (f"QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo{index:02d}" * 2)[:64]
    value = f"-----BEGIN RSA PRIVATE KEY-----\n{payload}\n-----END PRIVATE KEY-----"
    assert not validate_private_key(value)


def test_private_key_scanner_rejects_adversarial_whitespace_in_linear_time() -> None:
    value = "-----BEGIN PRIVATE KEY-----\n" + ("\n" * 32_000)
    start = time.perf_counter()
    assert detect_secrets(value) == []
    assert time.perf_counter() - start < 0.5
