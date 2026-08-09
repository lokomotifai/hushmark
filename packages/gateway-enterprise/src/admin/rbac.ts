import { GatewayError } from "@hushmark/gateway";
import { z } from "zod";

export const AdminRoleSchema = z.enum(["admin", "operator", "auditor"]);
export type AdminRole = z.infer<typeof AdminRoleSchema>;

export function requireRole(actual: AdminRole, allowed: readonly AdminRole[]): void {
  if (!allowed.includes(actual)) throw new GatewayError("HM-4030", "role lacks permission");
}
