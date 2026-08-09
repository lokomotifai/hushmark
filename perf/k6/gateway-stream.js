import http from "k6/http";
import { check } from "k6";
import { Trend } from "k6/metrics";

const gatewayUrl = __ENV.GATEWAY_URL || "http://127.0.0.1:8080";
const directUrl = __ENV.DIRECT_URL || "http://127.0.0.1:9000";
const apiKey = __ENV.HUSHMARK_PERF_API_KEY || "hm_k1_evaluation_local_key";
const threshold = Number(__ENV.STREAM_OVERHEAD_P95_MS || "300");
const firstTokenOverhead = new Trend("gateway_first_token_overhead", true);

export const options = {
  vus: Number(__ENV.VUS || "2"),
  iterations: Number(__ENV.ITERATIONS || "40"),
  thresholds: {
    gateway_first_token_overhead: [`p(95)<${threshold}`],
    http_req_failed: ["rate<0.01"],
  },
};

const gatewayPayload = JSON.stringify({
  model: "hushmark-eval",
  stream: true,
  messages: [{ role: "user", content: "10000000146" }],
});
const directPayload = JSON.stringify({
  model: "hushmark-eval",
  stream: true,
  messages: [{ role: "user", content: "[TCKN_1]" }],
});

export default function () {
  const direct = http.post(`${directUrl}/v1/chat/completions`, directPayload, {
    headers: { "content-type": "application/json" },
    tags: { scenario: "direct_stream" },
  });
  const gateway = http.post(`${gatewayUrl}/v1/chat/completions`, gatewayPayload, {
    headers: { authorization: `Bearer ${apiKey}`, "content-type": "application/json" },
    tags: { scenario: "gateway_stream" },
  });
  firstTokenOverhead.add(Math.max(0, gateway.timings.waiting - direct.timings.waiting));
  check(gateway, {
    "stream returned 200": (result) => result.status === 200,
    "stream restored TCKN": (result) => result.body.includes("10000000146"),
    "stream preserved done": (result) => result.body.includes("[DONE]"),
  });
}
