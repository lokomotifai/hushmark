import http from "k6/http";
import { check } from "k6";

const coreUrl = __ENV.CORE_URL || "http://127.0.0.1:8000";
const threshold = Number(__ENV.CORE_P95_MS || "150");
const text = `${Array(511).fill("ve").join(" ")} 10000000146`;

export const options = {
  vus: Number(__ENV.VUS || "4"),
  iterations: Number(__ENV.ITERATIONS || "80"),
  thresholds: {
    "http_req_duration{scenario:core_mask}": [`p(95)<${threshold}`],
    http_req_failed: ["rate<0.01"],
  },
};

export default function () {
  const response = http.post(
    `${coreUrl}/v1/mask`,
    JSON.stringify({ language: "tr", session: `perf-${__VU}`, items: [{ id: "1", text }] }),
    { headers: { "content-type": "application/json" }, tags: { scenario: "core_mask" } },
  );
  check(response, {
    "core returned 200": (result) => result.status === 200,
    "core masked TCKN": (result) => result.body.includes("[TCKN_1]"),
  });
}
