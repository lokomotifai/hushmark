"""Machine-readable result storage and recall-first Markdown rendering."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def result_path(report_path: Path, engine: str) -> Path:
    return report_path.with_name(f"{report_path.stem}-{engine}.json")


def write_result(report_path: Path, result: dict[str, Any]) -> None:
    output = result_path(report_path, str(result["engine"]))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def render_report(report_path: Path) -> None:
    results = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(report_path.parent.glob(f"{report_path.stem}-*.json"))
    ]
    if not results:
        raise ValueError("no benchmark engine results are available")
    dataset = results[0]["dataset"]
    lines = [
        "# hushmark-bench v0 baseline",
        "",
        "> Bu rapor yalnızca sentetik benchmark ölçümüdür; bir uyumluluk veya anonimleştirme",
        "> iddiası değildir. Geri döndürülebilir maskeleme teknik bir güvenlik tedbiridir.",
        "",
        f"Dataset: `{dataset['name']}` · examples: {dataset['examples']} · "
        f"SHA-256: `{dataset['sha256']}`",
        "",
        "## Recall-first summary",
        "",
        "<!-- prettier-ignore -->",
        "| Engine | Strict recall | Strict precision | Strict F1 | Partial recall | Partial F1 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for result in results:
        strict = result["strict"]["micro"]
        partial = result["partial"]["micro"]
        lines.append(
            f"| {result['engine']} | {strict['recall']:.3f} | {strict['precision']:.3f} | "
            f"{strict['f1']:.3f} | {partial['recall']:.3f} | {partial['f1']:.3f} |"
        )
    for result in results:
        lines.extend(
            [
                "",
                f"## {result['engine']}",
                "",
                f"Model: `{result['model_id']}` · backend: `{result['backend']}` · "
                f"duration: {result['duration_seconds']:.3f}s",
                "",
                "<!-- prettier-ignore -->",
                "| Type | Gold | Strict R | Strict P | Strict F1 | Partial R | Partial F1 |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        strict_types = result["strict"]["per_type"]
        partial_types = result["partial"]["per_type"]
        for entity_type, strict in sorted(
            strict_types.items(), key=lambda item: (float(item[1]["recall"]), item[0])
        ):
            partial = partial_types[entity_type]
            lines.append(
                f"| {entity_type} | {strict['support']} | {strict['recall']:.3f} | "
                f"{strict['precision']:.3f} | {strict['f1']:.3f} | "
                f"{partial['recall']:.3f} | {partial['f1']:.3f} |"
            )
    lines.extend(
        [
            "",
            "## Method",
            "",
            "Strict matching requires identical type and code-point offsets. Partial matching",
            "requires the same type and any positive span overlap. Each prediction can match at",
            "most one gold span. Macro values average only types with gold support.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
