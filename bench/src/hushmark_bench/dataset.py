"""Deterministic synthetic data generation and JSONL validation."""

from __future__ import annotations

import base64
import hashlib
import json
import random
import re
import string
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from faker import Faker
from hushmark_core.taxonomy_gen import ENTITY_TYPES

from hushmark_bench.templates import DOMAINS, TEMPLATES, Template

PLACEHOLDER = re.compile(r"\{([A-Z_]+)\}")
MORPHOLOGIES = ("plain", "name_suffix", "missing_diacritics", "lowercase_context")
ASCII_TRANSLATION = str.maketrans(
    {
        "ç": "c",
        "Ç": "C",
        "ğ": "g",
        "Ğ": "G",
        "ı": "i",
        "İ": "I",
        "ö": "o",
        "Ö": "O",
        "ş": "s",
        "Ş": "S",
        "ü": "u",
        "Ü": "U",
    }
)
NER_VALUES = {
    "HEALTH": ("tip 2 diyabet", "hipertansiyon", "migren"),
    "RELIGION": ("Alevi", "Musevi", "Budist"),
    "ETHNICITY": ("Kürt kökenli", "Çerkes kökenli", "Roman kökenli"),
    "POLITICAL": ("sosyal demokrat", "muhafazakâr", "liberal"),
    "SEXUAL_LIFE": ("eşcinsel", "biseksüel", "heteroseksüel"),
    "CRIMINAL": ("hapis cezası kaydı", "adli para cezası", "denetimli serbestlik"),
    "BIOMETRIC_REF": ("parmak izi şablonu", "yüz tanıma kaydı", "retina taraması"),
    "UNION": ("Banka-Sen üyeliği", "Sağlık-İş üyeliği", "Birleşik Metal-İş üyeliği"),
}


def calculate_vkn_checksum(first_nine: str) -> int:
    total = 0
    for index, char in enumerate(first_nine):
        shifted = (int(char) + 9 - index) % 10
        contribution = (shifted * (2 ** (9 - index))) % 9
        total += 9 if shifted != 0 and contribution == 0 else contribution
    return (10 - total % 10) % 10


def validate_credit_card(value: str) -> bool:
    compact = value.replace(" ", "").replace("-", "")
    total = 0
    parity = len(compact) % 2
    for index, char in enumerate(compact):
        digit = int(char)
        if index % 2 == parity:
            digit = digit * 2 - 9 if digit > 4 else digit * 2
        total += digit
    return 13 <= len(compact) <= 19 and total % 10 == 0


@dataclass(frozen=True, slots=True)
class GoldEntity:
    type: str
    start: int
    end: int
    text: str


@dataclass(frozen=True, slots=True)
class Example:
    id: str
    domain: str
    template_id: str
    morphology: list[str]
    text: str
    entities: list[GoldEntity]


class ValueFactory:
    def __init__(self, seed: int) -> None:
        self.random = random.Random(seed)
        Faker.seed(seed)
        self.fake = Faker("tr_TR")
        self.index = 0

    def value(self, entity_type: str, morphology: str) -> str:
        self.index += 1
        factories = {
            "TR_TCKN": self.tckn,
            "TR_VKN": self.vkn,
            "TR_IBAN": self.tr_iban,
            "IBAN_OTHER": self.other_iban,
            "CREDIT_CARD": self.credit_card,
            "TR_PHONE": self.phone,
            "TR_PLATE": self.plate,
            "TR_SGK": self.sgk,
            "EMAIL": self.email,
            "SECRET_API_KEY": self.api_key,
            "SECRET_JWT": self.jwt,
            "SECRET_PRIVATE_KEY": self.private_key,
            "PERSON": self.fake.name,
            "ADDRESS": lambda: self.fake.address().replace("\n", ", "),
            "ORG": self.fake.company,
            "DOB": self.dob,
        }
        if entity_type in factories:
            value = factories[entity_type]()
        elif entity_type in NER_VALUES:
            value = self.random.choice(NER_VALUES[entity_type])
        else:
            raise ValueError(f"no synthetic value factory for {entity_type}")
        if entity_type == "PERSON" and morphology == "name_suffix":
            value += self.random.choice(("'ın", "'in", "'la", "'ye"))
        if morphology == "missing_diacritics" and entity_type not in deterministic_types():
            value = value.translate(ASCII_TRANSLATION)
        return value

    def digits(self, length: int) -> str:
        return "".join(self.random.choice(string.digits) for _ in range(length))

    def tckn(self) -> str:
        digits = [self.random.randint(1, 9), *[self.random.randint(0, 9) for _ in range(8)]]
        tenth = (7 * sum(digits[0:9:2]) - sum(digits[1:8:2])) % 10
        digits.append(tenth)
        digits.append(sum(digits) % 10)
        return "".join(str(digit) for digit in digits)

    def vkn(self) -> str:
        first_nine = "8" + self.digits(8)
        return first_nine + str(calculate_vkn_checksum(first_nine))

    def tr_iban(self) -> str:
        bban = self.digits(22)
        check = 98 - int(f"{bban}292700") % 97
        return f"TR{check:02d}{bban}"

    def other_iban(self) -> str:
        return self.random.choice(("GB82WEST12345698765432", "DE89370400440532013000"))

    def credit_card(self) -> str:
        prefix = "4" + self.digits(14)
        for check in string.digits:
            candidate = prefix + check
            if validate_credit_card(candidate):
                return " ".join(candidate[index : index + 4] for index in range(0, 16, 4))
        raise AssertionError("a Luhn check digit always exists")

    def phone(self) -> str:
        prefix = f"5{self.random.randint(0, 9)}{self.random.randint(0, 9)}"
        return f"+90 {prefix} {self.digits(3)} {self.digits(2)} {self.digits(2)}"

    def plate(self) -> str:
        letters = "".join(self.random.choice("ABCEKMRST") for _ in range(2))
        return f"{self.random.randint(1, 81):02d} {letters} {self.random.randint(100, 999)}"

    def sgk(self) -> str:
        while True:
            candidate = self.digits(13)
            if not validate_credit_card(candidate):
                return candidate

    def email(self) -> str:
        return f"kisi{self.index}@ornek{self.index % 17}.com"

    def api_key(self) -> str:
        alphabet = string.ascii_letters + string.digits + "_-"
        return "sk-" + "".join(self.random.choice(alphabet) for _ in range(32))

    def jwt(self) -> str:
        payload = base64.urlsafe_b64encode(self.random.randbytes(18)).decode().rstrip("=")
        signature = base64.urlsafe_b64encode(self.random.randbytes(24)).decode().rstrip("=")
        return f"eyJhbGciOiJIUzI1NiJ9.{payload}.{signature}"

    def private_key(self) -> str:
        body = base64.b64encode(self.random.randbytes(48)).decode()
        return f"-----BEGIN PRIVATE KEY-----\n{body}\n-----END PRIVATE KEY-----"

    def dob(self) -> str:
        value = date(1950, 1, 1) + timedelta(days=self.random.randint(0, 19_000))
        return value.strftime("%d.%m.%Y")


def deterministic_types() -> frozenset[str]:
    return frozenset(
        {
            "TR_TCKN",
            "TR_VKN",
            "TR_IBAN",
            "IBAN_OTHER",
            "CREDIT_CARD",
            "TR_PHONE",
            "TR_PLATE",
            "TR_SGK",
            "EMAIL",
            "SECRET_API_KEY",
            "SECRET_JWT",
            "SECRET_PRIVATE_KEY",
        }
    )


def render(template: Template, factory: ValueFactory, morphology: str, row: int) -> Example:
    chunks: list[str] = []
    entities: list[GoldEntity] = []
    cursor = 0
    for match in PLACEHOLDER.finditer(template.pattern):
        literal = template.pattern[cursor : match.start()]
        if morphology == "lowercase_context":
            literal = literal.lower()
        chunks.append(literal)
        entity_type = match.group(1)
        value = factory.value(entity_type, morphology)
        start = sum(len(chunk) for chunk in chunks)
        chunks.append(value)
        entities.append(GoldEntity(entity_type, start, start + len(value), value))
        cursor = match.end()
    literal = template.pattern[cursor:]
    if morphology == "lowercase_context":
        literal = literal.lower()
    chunks.append(literal)
    text = "".join(chunks)
    return Example(
        id=f"v0-{row:04d}",
        domain=template.domain,
        template_id=template.id,
        morphology=[morphology],
        text=text,
        entities=entities,
    )


def generate_examples(seed: int, repetitions: int = 8) -> Iterator[Example]:
    templates_per_domain = {
        domain: sum(template.domain == domain for template in TEMPLATES) for domain in DOMAINS
    }
    if len(DOMAINS) != 6 or any(count < 40 for count in templates_per_domain.values()):
        raise AssertionError("benchmark requires at least 40 templates in each of six domains")
    factory = ValueFactory(seed)
    row = 0
    for repetition in range(repetitions):
        for template in TEMPLATES:
            morphology = MORPHOLOGIES[(row + repetition) % len(MORPHOLOGIES)]
            yield render(template, factory, morphology, row)
            row += 1


def write_dataset(path: Path, seed: int, repetitions: int = 8) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(asdict(example), ensure_ascii=False, separators=(",", ":"))
        for example in generate_examples(seed, repetitions)
    ]
    content = "\n".join(lines) + "\n"
    path.write_text(content, encoding="utf-8")
    return hashlib.sha256(content.encode()).hexdigest()


def write_lock(lock_path: Path, digest: str, data_path: Path) -> None:
    lock_path.write_text(f"{digest}  bench/data/{data_path.name}\n", encoding="utf-8")


def load_dataset(path: Path) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        raw = json.loads(line)
        if not isinstance(raw, dict) or not isinstance(raw.get("text"), str):
            raise ValueError(f"invalid example at line {line_number}")
        entities = raw.get("entities")
        if not isinstance(entities, list):
            raise ValueError(f"invalid entities at line {line_number}")
        for entity in entities:
            if not isinstance(entity, dict) or entity.get("type") not in ENTITY_TYPES:
                raise ValueError(f"invalid entity at line {line_number}")
            start, end = entity.get("start"), entity.get("end")
            if not isinstance(start, int) or not isinstance(end, int):
                raise ValueError(f"invalid offsets at line {line_number}")
            if raw["text"][start:end] != entity.get("text"):
                raise ValueError(f"gold offset mismatch at line {line_number}")
        examples.append(raw)
    return examples
