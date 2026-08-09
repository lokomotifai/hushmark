import { createCipheriv, createDecipheriv, randomBytes } from "node:crypto";

import type { Kms } from "./types.js";

export class LocalTestKms implements Kms {
  readonly #masterKey: Buffer;

  constructor(masterKey: Uint8Array = randomBytes(32)) {
    if (masterKey.byteLength !== 32) throw new RangeError("local test master key must be 32 bytes");
    this.#masterKey = Buffer.from(masterKey);
  }

  wrap(keyId: string, dataKey: Uint8Array): Promise<string> {
    const iv = randomBytes(12);
    const cipher = createCipheriv("aes-256-gcm", this.#masterKey, iv);
    cipher.setAAD(Buffer.from(keyId));
    const ciphertext = Buffer.concat([cipher.update(dataKey), cipher.final()]);
    const tag = cipher.getAuthTag();
    return Promise.resolve(Buffer.concat([iv, tag, ciphertext]).toString("base64"));
  }

  unwrap(keyId: string, wrappedKey: string): Promise<Uint8Array> {
    const envelope = Buffer.from(wrappedKey, "base64");
    const iv = envelope.subarray(0, 12);
    const tag = envelope.subarray(12, 28);
    const ciphertext = envelope.subarray(28);
    const decipher = createDecipheriv("aes-256-gcm", this.#masterKey, iv);
    decipher.setAAD(Buffer.from(keyId));
    decipher.setAuthTag(tag);
    return Promise.resolve(
      new Uint8Array(Buffer.concat([decipher.update(ciphertext), decipher.final()])),
    );
  }
}
