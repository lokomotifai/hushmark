import { z } from "zod";

export const ERROR_CODES = [
  "HM-4001",
  "HM-4010",
  "HM-4030",
  "HM-4102",
  "HM-4201",
  "HM-4203",
  "HM-4290",
  "HM-4301",
  "HM-5001",
  "HM-5030",
  "HM-5040",
] as const;

export type ErrorCode = (typeof ERROR_CODES)[number];
export const ErrorCodeSchema = z.enum(ERROR_CODES);

export const ErrorBodySchema = z
  .object({
    error: z
      .object({
        code: ErrorCodeSchema,
        message: z.string().min(1),
        types: z.array(z.string()).optional(),
      })
      .strict(),
  })
  .strict();

export type ErrorBody = z.infer<typeof ErrorBodySchema>;
