import { z } from "zod";

export const LICENSE_FEATURES = ["sso", "kms_vault", "audit_chain", "tedbir_report"] as const;

export const UnsignedLicenseSchema = z
  .object({
    v: z.literal(1),
    licensee: z.string().min(1).max(240),
    tier: z.enum(["team", "enterprise", "regulated"]),
    issued_at: z.iso.datetime({ offset: true }),
    expires_at: z.iso.datetime({ offset: true }),
    grace_days: z.number().int().min(0).max(365),
    entitlements: z.object({ features: z.array(z.enum(LICENSE_FEATURES)).min(1) }).strict(),
  })
  .strict()
  .refine((value) => new Date(value.expires_at) > new Date(value.issued_at), {
    message: "expires_at must be later than issued_at",
  });

export const SignedLicenseSchema = UnsignedLicenseSchema.safeExtend({
  sig: z.base64(),
}).strict();

export type UnsignedLicense = z.infer<typeof UnsignedLicenseSchema>;
export type SignedLicense = z.infer<typeof SignedLicenseSchema>;
export type LicenseFeature = (typeof LICENSE_FEATURES)[number];
