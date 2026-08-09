# Next.js chat example

This local-only example uses AI SDK 7, its OpenAI provider, and `@hushmark/ai-sdk` against the
Hushmark gateway.

```sh
HUSHMARK_API_KEY=hm_k1_replace_me \
HUSHMARK_GATEWAY_URL=http://127.0.0.1:8080 \
pnpm --filter examples-nextjs-chat dev
```

The default model ID is `test` for the bundled fake-upstream integration. Set
`HUSHMARK_EXAMPLE_MODEL` for another gateway-configured upstream.
