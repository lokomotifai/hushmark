#!/usr/bin/env node
import { generateKeyPairSync } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";

import {
  SignedLicenseSchema,
  UnsignedLicenseSchema,
  signLicensePayload,
} from "@hushmark/gateway-enterprise";

const [command, ...args] = process.argv.slice(2);

if (command === "keygen") {
  const privatePath = requiredOption(args, "--private");
  const publicPath = requiredOption(args, "--public");
  const { privateKey, publicKey } = generateKeyPairSync("ed25519");
  await writeFile(privatePath, privateKey.export({ type: "pkcs8", format: "pem" }), {
    mode: 0o600,
  });
  await writeFile(publicPath, publicKey.export({ type: "spki", format: "pem" }), { mode: 0o644 });
  process.stdout.write(`generated ${publicPath}\n`);
} else if (command === "sign") {
  const inputPath = requiredOption(args, "--input");
  const privatePath = requiredOption(args, "--private");
  const outputPath = requiredOption(args, "--output");
  const payload = UnsignedLicenseSchema.parse(JSON.parse(await readFile(inputPath, "utf8")));
  const signed = signLicensePayload(payload, await readFile(privatePath, "utf8"));
  await writeFile(outputPath, JSON.stringify(signed, null, 2) + "\n", { mode: 0o600 });
  process.stdout.write(`signed ${outputPath}\n`);
} else if (command === "inspect") {
  const inputPath = requiredOption(args, "--input");
  const signed = SignedLicenseSchema.parse(JSON.parse(await readFile(inputPath, "utf8")));
  const payload = Object.fromEntries(Object.entries(signed).filter(([key]) => key !== "sig"));
  process.stdout.write(JSON.stringify(payload, null, 2) + "\n");
} else {
  throw new Error("usage: hushmark-license keygen|sign|inspect [options]");
}

function requiredOption(args: string[], name: string): string {
  const index = args.indexOf(name);
  const value = args[index + 1];
  if (index < 0 || value === undefined) throw new Error(`${name} is required`);
  return value;
}
