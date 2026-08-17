"""Cross-engine comparison rendering for the criteria table."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MORPHOLOGIES = ("plain", "name_suffix", "missing_diacritics", "lowercase_context")

DISCLAIMER = (
    "> Bu rapor sentetik bir veri kümesi üzerinde yapılmış bir ölçümdür; bir uyumluluk,\n"
    "> anonimleştirme veya üstünlük iddiası değildir. Geri döndürülebilir maskeleme\n"
    "> teknik bir güvenlik tedbiridir, KVKK anlamında anonimleştirme değildir."
)


def load_results(report_path: Path) -> list[dict[str, Any]]:
    results = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(report_path.parent.glob(f"{report_path.stem}-*.json"))
    ]
    if not results:
        raise ValueError("no benchmark engine results are available")
    return sorted(results, key=lambda item: -float(item["strict"]["micro"]["recall"]))


def deployment(result: dict[str, Any]) -> str:
    return "üçüncü taraf API" if result["backend"] == "api" else "yerel"


def summary_table(results: list[dict[str, Any]]) -> list[str]:
    lines = [
        "<!-- prettier-ignore -->",
        "| Motor | Model | Çalışma | Strict R | Strict P | Strict F1 | Partial R |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for result in results:
        strict = result["strict"]["micro"]
        partial = result["partial"]["micro"]
        lines.append(
            f"| {result['engine']} | `{result['model_id']}` | {deployment(result)} | "
            f"{strict['recall']:.3f} | {strict['precision']:.3f} | {strict['f1']:.3f} | "
            f"{partial['recall']:.3f} |"
        )
    return lines


def criteria_table(results: list[dict[str, Any]]) -> list[str]:
    lines = [
        "<!-- prettier-ignore -->",
        "| Motor | TR kimlik recall | Özel nitelikli recall | Tip kapsamı | p50 gecikme | "
        "p95 gecikme |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for result in results:
        slices = result.get("slices")
        if not slices:
            continue
        identifier = slices["identifier"]
        special = slices["special_category"]
        cover = slices["coverage"]
        latency = slices["latency"]
        lines.append(
            f"| {result['engine']} | {identifier['recall']:.3f} | {special['recall']:.3f} | "
            f"{cover['types_detected']}/{cover['types_with_gold']} | "
            f"{latency['p50_ms']:.1f} ms | {latency['p95_ms']:.1f} ms |"
        )
    return lines


def morphology_table(results: list[dict[str, Any]]) -> list[str]:
    header = " | ".join(MORPHOLOGIES)
    lines = [
        "<!-- prettier-ignore -->",
        f"| Motor | {header} |",
        "| --- |" + " ---: |" * len(MORPHOLOGIES),
    ]
    for result in results:
        slices = result.get("slices")
        if not slices:
            continue
        cells = []
        for morphology in MORPHOLOGIES:
            bucket = slices["morphology"].get(morphology)
            cells.append(f"{bucket['recall']:.3f}" if bucket else "—")
        lines.append(f"| {result['engine']} | " + " | ".join(cells) + " |")
    return lines


def per_type_table(results: list[dict[str, Any]]) -> list[str]:
    engines = [str(result["engine"]) for result in results]
    lines = [
        "<!-- prettier-ignore -->",
        "| Tip | Gold | " + " | ".join(engines) + " |",
        "| --- | ---: |" + " ---: |" * len(engines),
    ]
    entity_types = sorted(
        {
            entity_type
            for result in results
            for entity_type, metrics in result["strict"]["per_type"].items()
            if metrics["support"]
        }
    )
    for entity_type in entity_types:
        support = 0
        cells = []
        for result in results:
            metrics = result["strict"]["per_type"].get(entity_type)
            if metrics and metrics["support"]:
                support = int(metrics["support"])
                cells.append(f"{metrics['recall']:.3f}")
            else:
                cells.append("—")
        lines.append(f"| {entity_type} | {support} | " + " | ".join(cells) + " |")
    return lines


def render_comparison(report_path: Path, output_path: Path) -> None:
    results = load_results(report_path)
    dataset = results[0]["dataset"]
    lines = [
        "# hushmark-bench · çok motorlu karşılaştırma",
        "",
        DISCLAIMER,
        "",
        f"Veri kümesi: `{dataset['name']}` · örnek: {dataset['examples']} · "
        f"SHA-256: `{dataset['sha256']}`",
        "",
        "## Genel özet (recall öncelikli)",
        "",
        *summary_table(results),
        "",
        "## Karar kriterleri",
        "",
        *criteria_table(results),
        "",
        "## Türkçe morfoloji dayanıklılığı (strict recall)",
        "",
        *morphology_table(results),
        "",
        "## Tip bazlı strict recall",
        "",
        *per_type_table(results),
        "",
        "## Yöntem",
        "",
        "Strict eşleşme aynı tip ve birebir aynı kod noktası ofsetlerini gerektirir; partial",
        "eşleşme aynı tip ve herhangi bir örtüşme ile sağlanır. Her tahmin en fazla bir gold",
        "span ile eşleşir. `TR kimlik recall` deterministik kimlik tiplerinin (TCKN, VKN, IBAN,",
        "SGK, plaka, telefon, e-posta, kart, sır) toplam micro recall değeridir. `Özel nitelikli",
        "recall` KVKK m.6 kapsamındaki sağlık, din, etnik köken, siyasi görüş, cinsel hayat,",
        "ceza mahkûmiyeti, biyometri ve sendika tiplerinin micro recall değeridir. Gecikme",
        "değerleri tek iş parçacıklı CPU üzerinde örnek başına ölçülmüştür.",
        "",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")
