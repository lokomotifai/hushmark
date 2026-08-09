import { buildServer } from "./server.js";
import { loadConfig, loadPolicy } from "./config.js";

const config = loadConfig();
const policy = await loadPolicy(config.HUSHMARK_POLICY_PATH);
const app = buildServer({ config, policy, logger: true });
await app.listen({ host: config.HUSHMARK_GATEWAY_HOST, port: config.HUSHMARK_GATEWAY_PORT });
