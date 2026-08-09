import type { ErrorBody, ErrorCode } from "@hushmark/shared";

const STATUS_BY_CODE: Record<ErrorCode, number> = {
  "HM-4001": 400,
  "HM-4010": 401,
  "HM-4030": 403,
  "HM-4102": 422,
  "HM-4201": 422,
  "HM-4203": 422,
  "HM-4290": 429,
  "HM-4301": 403,
  "HM-5001": 502,
  "HM-5030": 503,
  "HM-5040": 503,
};

export class GatewayError extends Error {
  readonly statusCode: number;

  constructor(
    readonly code: ErrorCode,
    message: string,
    readonly types?: string[],
  ) {
    super(message);
    this.name = "GatewayError";
    this.statusCode = STATUS_BY_CODE[code];
  }

  body(): ErrorBody {
    return {
      error: {
        code: this.code,
        message: this.message,
        ...(this.types === undefined ? {} : { types: this.types }),
      },
    };
  }
}
