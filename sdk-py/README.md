# hushmark-sdk

Typed `httpx` client for a self-hosted Hushmark core and gateway.

```python
from hushmark_sdk import Hushmark

with Hushmark(
    core_url="http://localhost:8000",
    gateway_url="http://localhost:8080",
    api_key="hm_k1_replace_me",
) as client:
    result = client.analyze([{"id": "m0", "text": "TCKN 10000000146"}])
```

`mask` and `analyze` call the internal core URL configured by the operator. `chat` sends an
OpenAI- or Anthropic-compatible payload through the gateway and adds only the Hushmark gateway
credential. Keep the core on a trusted internal network.

Hushmark is a technical control for supported AI traffic. Detection quality and policy outcomes
depend on the configured engine, policy, and deployment.
