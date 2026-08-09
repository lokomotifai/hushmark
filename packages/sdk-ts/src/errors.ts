import { ErrorBodySchema, type ErrorCode } from "@hushmark/shared";

export class HushmarkError extends Error {
  readonly code: ErrorCode;
  readonly status: number;
  readonly types: readonly string[];

  constructor(code: ErrorCode, message: string, status: number, types: readonly string[] = []) {
    super(message);
    this.name = "HushmarkError";
    this.code = code;
    this.status = status;
    this.types = types;
  }
}

export async function errorFromResponse(response: Response): Promise<HushmarkError> {
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return new HushmarkError(
      "HM-5001",
      "gateway returned an invalid error response",
      response.status,
    );
  }
  const parsed = ErrorBodySchema.safeParse(payload);
  if (!parsed.success) {
    return new HushmarkError(
      "HM-5001",
      "gateway returned an invalid error response",
      response.status,
    );
  }
  return new HushmarkError(
    parsed.data.error.code,
    parsed.data.error.message,
    response.status,
    parsed.data.error.types ?? [],
  );
}
