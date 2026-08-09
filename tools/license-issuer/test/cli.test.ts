import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { SignedLicenseSchema, verifyLicense } from "@hushmark/gateway-enterprise";
import { execa } from "execa";
import { expect, it } from "vitest";

it("generates ephemeral keys, signs a license, and inspects it without printing the signature", async () => {
  const directory = await mkdtemp(join(tmpdir(), "hushmark-license-test-"));
  const privatePath = join(directory, "issuer-private.pem");
  const publicPath = join(directory, "issuer-public.pem");
  const inputPath = join(directory, "input.json");
  const outputPath = join(directory, "license.json");
  const cli = join(process.cwd(), "dist/cli.js");
  await execa("node", [cli, "keygen", "--private", privatePath, "--public", publicPath]);
  await writeFile(
    inputPath,
    JSON.stringify({
      v: 1,
      licensee: "Example",
      tier: "enterprise",
      issued_at: "2026-01-01T00:00:00.000Z",
      expires_at: "2027-01-01T00:00:00.000Z",
      grace_days: 30,
      entitlements: { features: ["kms_vault", "audit_chain"] },
    }) + "\n",
  );
  await execa("node", [
    cli,
    "sign",
    "--input",
    inputPath,
    "--private",
    privatePath,
    "--output",
    outputPath,
  ]);
  const signed = SignedLicenseSchema.parse(JSON.parse(await readFile(outputPath, "utf8")));
  expect(verifyLicense(signed, await readFile(publicPath, "utf8"))).toEqual(signed);
  const inspected = await execa("node", [cli, "inspect", "--input", outputPath]);
  expect(inspected.stdout).toContain('"licensee": "Example"');
  expect(inspected.stdout).not.toContain('"sig"');
});
