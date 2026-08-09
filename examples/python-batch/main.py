from __future__ import annotations

import argparse
import json
import os

from hushmark_sdk import Hushmark


def main() -> None:
    parser = argparse.ArgumentParser(description="Mask a small local batch with Hushmark")
    parser.add_argument("--core-url", default="http://127.0.0.1:8000")
    parser.add_argument("--gateway-url", default="http://127.0.0.1:8080")
    parser.add_argument(
        "--text",
        default="Müşterimiz Ayşe Yılmaz, TCKN 10000000146 ile başvurdu.",
    )
    args = parser.parse_args()
    api_key = os.environ.get("HUSHMARK_API_KEY", "hm_k1_local_example")

    with Hushmark(
        core_url=args.core_url,
        gateway_url=args.gateway_url,
        api_key=api_key,
    ) as client:
        result = client.mask(
            [{"id": "batch-0", "text": args.text}],
            include_values=False,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
