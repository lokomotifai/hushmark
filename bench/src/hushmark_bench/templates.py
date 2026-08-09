"""Synthetic benchmark template bank: seven templates in each of six domains."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Template:
    id: str
    domain: str
    pattern: str


BASE_TEMPLATES: tuple[Template, ...] = (
    Template(
        "banking-01", "banking", "{PERSON} için TCKN {TR_TCKN} ile hesap açıldı; IBAN {TR_IBAN}."
    ),
    Template(
        "banking-02", "banking", "{ORG} müşterisinin VKN bilgisi {TR_VKN}, e-posta adresi {EMAIL}."
    ),
    Template(
        "banking-03", "banking", "{PERSON} kartı {CREDIT_CARD} için {TR_PHONE} numarasından aradı."
    ),
    Template(
        "banking-04", "banking", "Para transferi {IBAN_OTHER} hesabına, alıcı adresi {ADDRESS}."
    ),
    Template("banking-05", "banking", "Müşteri {PERSON}, doğum tarihi {DOB}; plaka {TR_PLATE}."),
    Template(
        "banking-06", "banking", "Şüpheli erişim anahtarı {SECRET_API_KEY}; hesap sahibi {PERSON}."
    ),
    Template("banking-07", "banking", "Oturum belirteci {SECRET_JWT}; müşteri TCKN {TR_TCKN}."),
    Template("insurance-01", "insurance", "Sigortalı {PERSON}, SGK sicil {TR_SGK}, tanı {HEALTH}."),
    Template(
        "insurance-02", "insurance", "Poliçe sahibi {PERSON}; adres {ADDRESS}; telefon {TR_PHONE}."
    ),
    Template("insurance-03", "insurance", "Araç {TR_PLATE}, kart {CREDIT_CARD}, şirket {ORG}."),
    Template("insurance-04", "insurance", "Hak sahibi TCKN {TR_TCKN}, doğum tarihi {DOB}."),
    Template(
        "insurance-05", "insurance", "Sağlık beyanı {HEALTH}; iletişim {EMAIL}; kişi {PERSON}."
    ),
    Template("insurance-06", "insurance", "Lehtar hesabı {TR_IBAN}; dini inanç beyanı {RELIGION}."),
    Template(
        "insurance-07", "insurance", "Yurt dışı ödeme {IBAN_OTHER}; etnik köken beyanı {ETHNICITY}."
    ),
    Template("hr-01", "hr", "Çalışan {PERSON}, TCKN {TR_TCKN}, SGK sicil {TR_SGK}."),
    Template("hr-02", "hr", "Aday {PERSON}; e-posta {EMAIL}; ikamet {ADDRESS}."),
    Template("hr-03", "hr", "Personel {PERSON}, doğum tarihi {DOB}, telefon {TR_PHONE}."),
    Template("hr-04", "hr", "Sendika üyeliği {UNION}; çalışan VKN kaydı {TR_VKN}."),
    Template("hr-05", "hr", "Sağlık notu {HEALTH}; personel kartı {CREDIT_CARD}."),
    Template("hr-06", "hr", "Siyasi görüş beyanı {POLITICAL}; çalışan {PERSON}; plaka {TR_PLATE}."),
    Template("hr-07", "hr", "Biyometrik kayıt notu {BIOMETRIC_REF}; iş e-postası {EMAIL}."),
    Template("legal-01", "legal", "Müvekkil {PERSON}, TCKN {TR_TCKN}, adres {ADDRESS}."),
    Template("legal-02", "legal", "Şirket {ORG}, VKN {TR_VKN}, IBAN {TR_IBAN}."),
    Template("legal-03", "legal", "Adli sicil bilgisi {CRIMINAL}; ilgili kişi {PERSON}."),
    Template("legal-04", "legal", "Dosya iletişimi {EMAIL}, telefon {TR_PHONE}, plaka {TR_PLATE}."),
    Template(
        "legal-05", "legal", "Özel hayat beyanı {SEXUAL_LIFE}; doğum tarihi {DOB}; TCKN {TR_TCKN}."
    ),
    Template(
        "legal-06", "legal", "Delil içindeki özel anahtar:\n{SECRET_PRIVATE_KEY}\nDosya {TR_SGK}."
    ),
    Template(
        "legal-07", "legal", "Yetki belirteci {SECRET_JWT}; vekil {PERSON}; hesap {IBAN_OTHER}."
    ),
    Template("health-01", "health", "Hasta {PERSON}, TCKN {TR_TCKN}, tanı {HEALTH}."),
    Template("health-02", "health", "Hasta adresi {ADDRESS}; telefon {TR_PHONE}; SGK {TR_SGK}."),
    Template("health-03", "health", "Doğum tarihi {DOB}; e-posta {EMAIL}; reçete tanısı {HEALTH}."),
    Template("health-04", "health", "Dini hassasiyet {RELIGION}; hasta {PERSON}; IBAN {TR_IBAN}."),
    Template("health-05", "health", "Etnik köken {ETHNICITY}; iletişim kartı {CREDIT_CARD}."),
    Template("health-06", "health", "Biyometrik referans {BIOMETRIC_REF}; kayıt TCKN {TR_TCKN}."),
    Template("health-07", "health", "Mahrem yaşam notu {SEXUAL_LIFE}; hasta telefonu {TR_PHONE}."),
    Template("support-01", "support", "Merhaba, ben {PERSON}; TCKN {TR_TCKN}, sorunum ödeme."),
    Template("support-02", "support", "IBAN {TR_IBAN}, kart {CREDIT_CARD}, e-posta {EMAIL}."),
    Template("support-03", "support", "Kargo adresim {ADDRESS}; telefonum {TR_PHONE}."),
    Template("support-04", "support", "Firma {ORG}, VKN {TR_VKN}, araç {TR_PLATE}."),
    Template("support-05", "support", "API anahtarım {SECRET_API_KEY}; hesap {IBAN_OTHER}."),
    Template("support-06", "support", "Adli sicil notu {CRIMINAL}; sendika {UNION}; SGK {TR_SGK}."),
    Template("support-07", "support", "Siyasi görüş {POLITICAL}; kişi {PERSON}; doğum {DOB}."),
)

CONTEXT_VARIANTS = (
    "{pattern}",
    "Kayıt: {pattern}",
    "İç not: {pattern}",
    "Güncelleme: {pattern}",
    "Talep metni: {pattern}",
    "İç yazışma özeti: {pattern}",
)
TEMPLATES = tuple(
    Template(
        id=f"{template.id}-v{variant_index}",
        domain=template.domain,
        pattern=variant.format(pattern=template.pattern),
    )
    for template in BASE_TEMPLATES
    for variant_index, variant in enumerate(CONTEXT_VARIANTS, start=1)
)

DOMAINS = frozenset(template.domain for template in TEMPLATES)
