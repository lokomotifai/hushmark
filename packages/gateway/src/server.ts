import { createHash, randomUUID, timingSafeEqual } from "node:crypto";
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
import { MemoryRateLimiter, type RateLimiter } from "./rateLimit.js";
import { transformSse } from "./streaming/sse.js";
import { unmaskText } from "./streaming/unmasker.js";
import { HttpUpstream, type UpstreamPort } from "./upstream.js";
import { MemoryVault, type PlaceholderVault, type VaultScope } from "./vault/memory.js";

export interface ServerDependencies {
  config: GatewayConfig;
  policy: StaticPolicy;
  core?: CorePort;
  upstream?: UpstreamPort;
  vault?: PlaceholderVault;
  onMaskEvent?: (event: MaskEvent) => Promise<void> | void;
  authenticateApiKey?: (key: string) => Promise<string | null>;
  rateLimiter?: RateLimiter;
  onSecurityEvent?: (event: GatewaySecurityEvent) => Promise<void> | void;
  policyForTenant?: (tenantId: string) => Promise<StaticPolicy>;
  logger?: boolean;
}

export interface GatewaySecurityEvent {
  kind: "REQUEST_BLOCKED";
  reason: "auth-rate-limit" | "tenant-rate-limit" | "unmask-limit";
  tenantId?: string;
  sessionId?: string;
}

export function buildServer(dependencies: ServerDependencies): FastifyInstance {
  const app = fastify({
    logger: dependencies.logger ?? false,
    logController: new LogController({ disableRequestLogging: true }),
    bodyLimit: dependencies.config.HUSHMARK_BODY_LIMIT_BYTES,
    trustProxy:
      dependencies.config.HUSHMARK_TRUST_PROXY_HOPS === 0
        ? false
        : dependencies.config.HUSHMARK_TRUST_PROXY_HOPS,
  });
  const config = dependencies.config;
  const apiKeys = config.HUSHMARK_API_KEYS;
  const tenantByRequest = new WeakMap<FastifyRequest, string>();
  const rateLimiter = dependencies.rateLimiter ?? new MemoryRateLimiter();
  const core =
    dependencies.core ??
    new CoreClient(config.HUSHMARK_CORE_URL, 2_000, config.HUSHMARK_CORE_SERVICE_TOKEN);
  const upstream = dependencies.upstream ?? new HttpUpstream(config);
  const vault =
    dependencies.vault ??
    new MemoryVault(config.HUSHMARK_VAULT_MAX_ENTRIES, Date.now, (event) => {
      app.log.warn(event);
    });
  const onMaskEvent = dependencies.onMaskEvent ?? ((event: MaskEvent) => app.log.info(event));

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

  app.addHook("onRequest", async (request) => {
    const authMode = (
      request.routeOptions.config as { hushmarkAuth?: "public" | "gateway" | "admin" }
    ).hushmarkAuth;
    if (authMode === "public" || authMode === "admin") return;
    if (
      !(await rateLimiter.consume(
        `gateway-auth:${request.ip}`,
        config.HUSHMARK_RATE_LIMIT_MAX,
        config.HUSHMARK_RATE_LIMIT_WINDOW_SEC * 1_000,
      ))
    ) {
      await dependencies.onSecurityEvent?.({
        kind: "REQUEST_BLOCKED",
        reason: "auth-rate-limit",
      });
      throw new GatewayError("HM-4290", "gateway rate limit exceeded");
    }
    const authorization = request.headers.authorization;
    const key = authorization?.startsWith("Bearer ") === true ? authorization.slice(7) : "";
    const tenantId =
      dependencies.authenticateApiKey === undefined
        ? apiKeys.some((candidate) => safeEqual(candidate, key))
          ? apiKeyId(key)
          : null
        : await dependencies.authenticateApiKey(key);
    if (tenantId === null) {
      throw new GatewayError("HM-4010", "missing or invalid gateway API key");
    }
    if (
      !(await rateLimiter.consume(
        `gateway-tenant:${tenantId}`,
        config.HUSHMARK_RATE_LIMIT_MAX,
        config.HUSHMARK_RATE_LIMIT_WINDOW_SEC * 1_000,
      ))
    ) {
      await dependencies.onSecurityEvent?.({
        kind: "REQUEST_BLOCKED",
        reason: "tenant-rate-limit",
        tenantId,
      });
      throw new GatewayError("HM-4290", "gateway rate limit exceeded");
    }
    tenantByRequest.set(request, tenantId);
  });

  app.get("/healthz", { config: { hushmarkAuth: "public" } }, () => ({ status: "ok" }));
  app.get("/readyz", { config: { hushmarkAuth: "public" } }, async (_request, reply) => {
    const ready = (await core.ready?.()) ?? true;
    void reply.status(ready ? 200 : 503);
    return { status: ready ? "ready" : "loading" };
  });
  const tenantFor = (request: FastifyRequest): string => {
    const tenantId = tenantByRequest.get(request);
    if (tenantId === undefined) throw new GatewayError("HM-4010", "missing gateway identity");
    return tenantId;
  };
  app.post(
    "/v1/chat/completions",
    { config: { hushmarkAuth: "gateway" } },
    async (request, reply) =>
      handleProvider(
        request,
        reply,
        new OpenAiAdapter(),
        core,
        upstream,
        vault,
        dependencies.policy,
        dependencies.policyForTenant,
        onMaskEvent,
        config.HUSHMARK_VAULT_TTL_SEC,
        tenantFor(request),
        config.HUSHMARK_UNMASK_LIMIT,
        config.HUSHMARK_UPSTREAM_MAX_RESPONSE_BYTES,
        config.HUSHMARK_STREAM_MAX_BUFFER_BYTES,
        config.HUSHMARK_STREAM_MAX_STATES,
        dependencies.onSecurityEvent,
      ),
  );
  app.post("/v1/messages", { config: { hushmarkAuth: "gateway" } }, async (request, reply) =>
    handleProvider(
      request,
      reply,
      new AnthropicAdapter(),
      core,
      upstream,
      vault,
      dependencies.policy,
      dependencies.policyForTenant,
      onMaskEvent,
      config.HUSHMARK_VAULT_TTL_SEC,
      tenantFor(request),
      config.HUSHMARK_UNMASK_LIMIT,
      config.HUSHMARK_UPSTREAM_MAX_RESPONSE_BYTES,
      config.HUSHMARK_STREAM_MAX_BUFFER_BYTES,
      config.HUSHMARK_STREAM_MAX_STATES,
      dependencies.onSecurityEvent,
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
  core: CorePort,
  upstream: UpstreamPort,
  vault: PlaceholderVault,
  fallbackPolicy: StaticPolicy,
  policyForTenant: ((tenantId: string) => Promise<StaticPolicy>) | undefined,
  onMaskEvent: (event: MaskEvent) => Promise<void> | void,
  vaultTtlSec: number,
  tenantId: string,
  unmaskLimit: number,
  upstreamMaxResponseBytes: number,
  streamMaxBufferBytes: number,
  streamMaxStates: number,
  onSecurityEvent?: (event: GatewaySecurityEvent) => Promise<void> | void,
): Promise<unknown> {
  const policy = policyForTenant === undefined ? fallbackPolicy : await policyForTenant(tenantId);
  const pipeline = new MaskPipeline(core, policy, vault, vaultTtlSec, onMaskEvent);
  const parsed = adapter.parseRequest(request.body);
  if (parsed.stream && policy.defaults.response_scan === "buffered") {
    throw new GatewayError("HM-4203", "buffered response scan is incompatible with streaming");
  }
  const session = parseSession(request.headers["x-hushmark-session"]);
  const scope: VaultScope = { tenantId, sessionId: session };
  const application = await pipeline.apply(parsed.segments, scope);
  const authorization = {
    allowedPlaceholders: application.issuedPlaceholders,
    remaining: unmaskLimit,
    limitReported: false,
    onLimitExceeded: () =>
      onSecurityEvent?.({
        kind: "REQUEST_BLOCKED",
        reason: "unmask-limit",
        tenantId,
        sessionId: session,
      }),
  };
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
    return reply.send(
      Readable.from(
        transformSse(response.body, adapter, scope, vault, authorization, {
          maxBufferBytes: streamMaxBufferBytes,
          maxStates: streamMaxStates,
        }),
      ),
    );
  }
  const upstreamBody = await readJsonBody(response.body, upstreamMaxResponseBytes);
  const restored = await adapter.unmaskResponse(upstreamBody, (text) =>
    unmaskText(text, scope, vault, authorization),
  );
  if (policy.defaults.response_scan === "buffered") {
    await pipeline.apply(adapter.responseSegments(restored), scope);
  }
  return restored;
}

async function readJsonBody(body: AsyncIterable<Uint8Array>, maxBytes: number): Promise<unknown> {
  const chunks: Uint8Array[] = [];
  let total = 0;
  for await (const chunk of body) {
    total += chunk.byteLength;
    if (total > maxBytes) throw new GatewayError("HM-5001", "upstream provider error");
    chunks.push(chunk);
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    throw new GatewayError("HM-5001", "upstream provider error");
  }
}

function apiKeyId(key: string): string {
  return createHash("sha256").update(key).digest("hex");
}

function safeEqual(expected: string, supplied: string): boolean {
  const left = Buffer.from(expected);
  const suppliedBytes = Buffer.from(supplied);
  const right = Buffer.alloc(left.length);
  suppliedBytes.copy(right, 0, 0, left.length);
  const equal = timingSafeEqual(left, right);
  return suppliedBytes.length === left.length && equal;
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
