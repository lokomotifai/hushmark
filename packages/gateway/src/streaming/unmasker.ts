import type { VaultScope, VaultStore } from "../vault/memory.js";
import { GatewayError } from "../errors.js";

const LABEL_MAX = 12;
const INDEX_MAX = 5;
const BRACKETS_AND_SEPARATOR = 3;
const COLLISION_SUFFIX_MAX = 17;

export const MAX_PLACEHOLDER_CODE_POINTS =
  LABEL_MAX + INDEX_MAX + BRACKETS_AND_SEPARATOR + COLLISION_SUFFIX_MAX;

export const PLACEHOLDER_PATTERN = /\[[A-Z]{2,12}_[1-9][0-9]{0,4}\](?:#[0-9a-f]{16})?/gu;
const BASE_AT_START = /^\[[A-Z]{2,12}_[1-9][0-9]{0,4}\]/u;
const SUFFIXED_AT_START = /^\[[A-Z]{2,12}_[1-9][0-9]{0,4}\]#[0-9a-f]{16}/u;

export interface UnmaskAuthorization {
  readonly allowedPlaceholders: ReadonlySet<string>;
  remaining: number;
  limitReported: boolean;
  onLimitExceeded?: () => Promise<void> | void;
}

export class StreamingUnmasker {
  #buffer = "";

  constructor(
    private readonly scope: VaultScope,
    private readonly vault: VaultStore,
    private readonly authorization: UnmaskAuthorization,
  ) {}

  async push(chunk: string): Promise<string> {
    this.#buffer += chunk;
    let output = "";
    while (this.#buffer.length > 0) {
      const opening = this.#buffer.indexOf("[");
      if (opening < 0) {
        output += this.#buffer;
        this.#buffer = "";
        break;
      }
      output += this.#buffer.slice(0, opening);
      this.#buffer = this.#buffer.slice(opening);

      const suffixed = SUFFIXED_AT_START.exec(this.#buffer)?.[0];
      if (suffixed !== undefined) {
        output += await this.resolve(suffixed);
        this.#buffer = this.#buffer.slice(suffixed.length);
        continue;
      }

      const base = BASE_AT_START.exec(this.#buffer)?.[0];
      if (base !== undefined) {
        const remainder = this.#buffer.slice(base.length);
        if (remainder.startsWith("#") && /^#[0-9a-f]{0,15}$/u.test(remainder)) break;
        const resolved = await this.resolve(base);
        if (resolved !== base) {
          output += resolved;
          this.#buffer = remainder;
          continue;
        }
        if (remainder.length === 0) break;
        output += base;
        this.#buffer = remainder;
        continue;
      }

      if (this.#buffer.length < MAX_PLACEHOLDER_CODE_POINTS) break;
      output += "[";
      this.#buffer = this.#buffer.slice(1);
    }
    return output;
  }

  async finish(): Promise<string> {
    let output = "";
    let cursor = 0;
    for (const match of this.#buffer.matchAll(PLACEHOLDER_PATTERN)) {
      const index = match.index;
      output += this.#buffer.slice(cursor, index);
      output += await this.resolve(match[0]);
      cursor = index + match[0].length;
    }
    output += this.#buffer.slice(cursor);
    this.#buffer = "";
    return output;
  }

  private async resolve(placeholder: string): Promise<string> {
    if (!this.authorization.allowedPlaceholders.has(placeholder)) return placeholder;
    if (this.authorization.remaining <= 0) {
      if (!this.authorization.limitReported) {
        this.authorization.limitReported = true;
        await this.authorization.onLimitExceeded?.();
      }
      throw new GatewayError("HM-4290", "response unmask limit exceeded");
    }
    this.authorization.remaining -= 1;
    return (await this.vault.resolve(this.scope, placeholder)) ?? placeholder;
  }
}

export async function unmaskText(
  text: string,
  scope: VaultScope,
  vault: VaultStore,
  authorization: UnmaskAuthorization,
): Promise<string> {
  const unmasker = new StreamingUnmasker(scope, vault, authorization);
  return (await unmasker.push(text)) + (await unmasker.finish());
}
