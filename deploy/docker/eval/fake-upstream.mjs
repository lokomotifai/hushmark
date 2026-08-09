import { createServer } from "node:http";

const port = Number(process.env.PORT ?? 9000);
const server = createServer(async (request, response) => {
  if (request.url === "/healthz") {
    response.writeHead(200, { "content-type": "application/json" });
    response.end('{"status":"ok"}');
    return;
  }
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  const raw = Buffer.concat(chunks).toString("utf8");
  if (/\b[1-9][0-9]{10}\b/u.test(raw)) {
    response.writeHead(500, { "content-type": "application/json" });
    response.end('{"error":"raw value reached fake upstream"}');
    return;
  }
  if (request.url?.endsWith("/chat/completions")) {
    const streaming = JSON.parse(raw).stream === true;
    if (streaming) {
      response.writeHead(200, { "content-type": "text/event-stream" });
      response.write('data: {"choices":[{"delta":{"content":"Kayıt [TCKN_1]"}}]}\n\n');
      response.end("data: [DONE]\n\n");
      return;
    }
    response.writeHead(200, { "content-type": "application/json" });
    response.end(
      JSON.stringify({
        id: "eval-response",
        object: "chat.completion",
        choices: [{ index: 0, message: { role: "assistant", content: "Kayıt [TCKN_1]" } }],
      }),
    );
    return;
  }
  response.writeHead(404, { "content-type": "application/json" });
  response.end('{"error":"not found"}');
});

server.listen(port, "0.0.0.0");
