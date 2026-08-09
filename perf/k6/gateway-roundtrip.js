import http from "k6/http";
import { check } from "k6";

const gatewayUrl = __ENV.GATEWAY_URL || "http://127.0.0.1:8080";
const apiKey = __ENV.HUSHMARK_PERF_API_KEY || "hm_k1_evaluation_local_key";
const threshold = Number(__ENV.GATEWAY_P95_MS || "250");

export const options = {
  vus: Number(__ENV.VUS || "4"),
  iterations: Number(__ENV.ITERATIONS || "80"),
  thresholds: {
    "http_req_duration{scenario:gateway_roundtrip}": [`p(95)<${threshold}`],
    http_req_failed: ["rate<0.01"],
  },
};

export default function () {
  const response = http.post(
    `${gatewayUrl}/v1/chat/completions`,
    JSON.stringify({
      model: "hushmark-eval",
      messages: [{ role: "user", content: "10000000146" }],
    }),
    {
      headers: { authorization: `Bearer ${apiKey}`, "content-type": "application/json" },
      tags: { scenario: "gateway_roundtrip" },
    },
  );
  check(response, {
    "gateway returned 200": (result) => result.status === 200,
    "round-trip restored TCKN": (result) => result.body.includes("10000000146"),
  });
}
