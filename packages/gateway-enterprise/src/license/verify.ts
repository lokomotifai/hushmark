import { createPrivateKey, createPublicKey, sign, verify } from "node:crypto";

import { jcs } from "../audit/canonical.js";
import {
  SignedLicenseSchema,
  UnsignedLicenseSchema,
  type SignedLicense,
  type UnsignedLicense,
} from "./schema.js";

export const EMBEDDED_LICENSE_PUBLIC_KEY = `-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAchalqI1Lb3ksb8US23S/QpZgH3AB3fUH+ZCstvvRqro=
-----END PUBLIC KEY-----
`;

export function canonicalLicensePayload(payload: UnsignedLicense): string {
  return jcs(UnsignedLicenseSchema.parse(payload));
}

export function signLicensePayload(payload: UnsignedLicense, privateKeyPem: string): SignedLicense {
  const parsed = UnsignedLicenseSchema.parse(payload);
  const signature = sign(
    null,
    Buffer.from(canonicalLicensePayload(parsed)),
    createPrivateKey(privateKeyPem),
  );
  return SignedLicenseSchema.parse({ ...parsed, sig: signature.toString("base64") });
}

export function verifyLicense(input: unknown, publicKeyPem: string): SignedLicense | null {
  const parsed = SignedLicenseSchema.safeParse(input);
  if (!parsed.success) return null;
  const { sig, ...payload } = parsed.data;
  try {
    const valid = verify(
      null,
      Buffer.from(canonicalLicensePayload(payload)),
      createPublicKey(publicKeyPem),
      Buffer.from(sig, "base64"),
    );
    return valid ? parsed.data : null;
  } catch {
    return null;
  }
}
