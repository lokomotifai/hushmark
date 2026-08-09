import { randomUUID } from "node:crypto";
import { Readable } from "node:stream";

import fastify, {
  type FastifyInstance,
  type FastifyReply,
  type FastifyRequest,
  LogController,
} from "fastify";
import { ZodError } from "zod";

import type { GatewayConfig, StaticPolicy } from "./config.js";
import type { CorePort } from "./coreClient.js";
import { CoreClient } from "./coreClient.js";
import { GatewayError } from "./errors.js";
import { MaskPipeline, type MaskEvent } from "./mask/pipeline.js";
import { AnthropicAdapter } from "./providers/anthropic.js";
import { OpenAiAdapter } from "./providers/openai.js";
import type { ProviderAdapter } from "./providers/types.js";
import { transformSse } from "./streaming/sse.js";
import { unmaskText } from "./streaming/unmasker.js";
import { HttpUpstream, type UpstreamPort } from "./upstream.js";
import { MemoryVault, type PlaceholderVault, type VaultStore } from "./vault/memory.js";

export interface ServerDependencies {
  config: GatewayConfig;
  policy: StaticPolicy;
  core?: CorePort;
  upstream?: UpstreamPort;
  vault?: PlaceholderVault;
  onMaskEvent?: (event: MaskEvent) => Promise<void> | void;
  logger?: boolean;
}

export function buildServer(dependencies: ServerDependencies): FastifyInstance {
  const app = fastify({
    logger: dependencies.logger ?? false,
    logController: new LogController({ disableRequestLogging: true }),
  });
  const config = dependencies.config;
  const apiKeys = new Set(config.HUSHMARK_API_KEYS);
  const core = dependencies.core ?? new CoreClient(config.HUSHMARK_CORE_URL);
  const upstream = dependencies.upstream ?? new HttpUpstream(config);
  const vault =
    dependencies.vault ??
    new MemoryVault(config.HUSHMARK_VAULT_MAX_ENTRIES, Date.now, (event) => {
      app.log.warn(event);
    });
  const pipeline = new MaskPipeline(
    core,
    dependencies.policy,
    vault,
    config.HUSHMARK_VAULT_TTL_SEC,
    dependencies.onMaskEvent ?? ((event) => app.log.info(event)),
  );

  app.setErrorHandler((error, _request, reply) => {
    if (error instanceof GatewayError) {
      void reply.status(error.statusCode).send(error.body());
      return;
    }
    if (error instanceof ZodError) {
      const gatewayError = new GatewayError("HM-4001", "malformed request");
      void reply.status(gatewayError.statusCode).send(gatewayError.body());
      return;
    }
    app.log.error({
      event: "request_failed",
      error_type: error instanceof Error ? error.constructor.name : "UnknownError",
    });
    const gatewayError = new GatewayError("HM-4001", "malformed request");
    void reply.status(gatewayError.statusCode).send(gatewayError.body());
  });

  app.addHook("onRequest", (request, _reply, done) => {
    if (
      request.url === "/healthz" ||
      request.url === "/readyz" ||
      request.url.startsWith("/admin/")
    ) {
      done();
      return;
    }
    const authorization = request.headers.authorization;
    const key = authorization?.startsWith("Bearer ") === true ? authorization.slice(7) : "";
    if (!apiKeys.has(key)) {
      done(new GatewayError("HM-4010", "missing or invalid gateway API key"));
      return;
    }
    done();
  });

  app.get("/healthz", () => ({ status: "ok" }));
  app.get("/readyz", async (_request, reply) => {
    const ready = (await core.ready?.()) ?? true;
    void reply.status(ready ? 200 : 503);
    return { status: ready ? "ready" : "loading" };
  });
  app.post("/v1/chat/completions", async (request, reply) =>
    handleProvider(
      request,
      reply,
      new OpenAiAdapter(),
      pipeline,
      upstream,
      vault,
      dependencies.policy,
    ),
  );
  app.post("/v1/messages", async (request, reply) =>
    handleProvider(
      request,
      reply,
      new AnthropicAdapter(),
      pipeline,
      upstream,
      vault,
      dependencies.policy,
    ),
  );
  app.setNotFoundHandler(() => {
    throw new GatewayError("HM-4001", "unsupported provider route");
  });

  app.addHook("onClose", async () => {
    await core.close?.();
  });
  return app;
}

async function handleProvider(
  request: FastifyRequest,
  reply: FastifyReply,
  adapter: ProviderAdapter,
  pipeline: MaskPipeline,
  upstream: UpstreamPort,
  vault: VaultStore,
  policy: StaticPolicy,
): Promise<unknown> {
  const parsed = adapter.parseRequest(request.body);
  if (parsed.stream && policy.defaults.response_scan === "buffered") {
    throw new GatewayError("HM-4203", "buffered response scan is incompatible with streaming");
  }
  const session = parseSession(request.headers["x-hushmark-session"]);
  await pipeline.apply(parsed.segments, session);
  const abortController = new AbortController();
  request.raw.once("close", () => abortController.abort());
  const response = await upstream.forward(
    adapter.kind,
    parsed.body,
    request.headers,
    abortController.signal,
  );
  if (parsed.stream) {
    reply.header("content-type", "text/event-stream; charset=utf-8");
    reply.header("cache-control", "no-cache");
    return reply.send(Readable.from(transformSse(response.body, adapter, session, vault)));
  }
  const upstreamBody = await response.body.json();
  const restored = await adapter.unmaskResponse(upstreamBody, (text) =>
    unmaskText(text, session, vault),
  );
  if (policy.defaults.response_scan === "buffered") {
    await pipeline.apply(adapter.responseSegments(restored), session);
  }
  return restored;
}

function parseSession(value: string | string[] | undefined): string {
  if (value === undefined) return randomUUID();
  if (
    Array.isArray(value) ||
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu.test(value)
  ) {
    throw new GatewayError("HM-4001", "invalid session id");
  }
  return value;
}
