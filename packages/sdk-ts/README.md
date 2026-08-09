# @hushmark/ai-sdk

Typed client helpers for sending OpenAI- and Anthropic-compatible requests through a self-hosted
Hushmark gateway. The package pins its development contract to AI SDK 7 and accepts AI SDK 7 as a
peer dependency.

```ts
import { createHushmark } from "@hushmark/ai-sdk";

const hushmark = createHushmark({
  baseUrl: "http://localhost:8080",
  apiKey: process.env.HUSHMARK_API_KEY!,
});
```

Use `hushmark.fetch` and `hushmark.openaiBaseUrl` with an OpenAI-compatible client, or configure an
AI SDK provider with `hushmark.openaiBaseUrl` and wrap its model with `hushmark.middleware()`.
The middleware adds a stable request-session header and preserves AI SDK streams while the gateway
performs masking and restoration.

Hushmark is a technical control for supported AI traffic. Detection quality and policy outcomes
depend on the configured engine, policy, and deployment.
