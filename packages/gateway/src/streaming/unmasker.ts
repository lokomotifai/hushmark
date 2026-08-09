import type { VaultStore } from "../vault/memory.js";

const LABEL_MAX = 12;
const INDEX_MAX = 5;
const BRACKETS_AND_SEPARATOR = 3;
const COLLISION_SUFFIX_MAX = 5;

export const MAX_PLACEHOLDER_CODE_POINTS =
  LABEL_MAX + INDEX_MAX + BRACKETS_AND_SEPARATOR + COLLISION_SUFFIX_MAX;

export const PLACEHOLDER_PATTERN = /\[[A-Z]{2,12}_[1-9][0-9]{0,4}\](?:#[0-9a-f]{4})?/gu;
const BASE_AT_START = /^\[[A-Z]{2,12}_[1-9][0-9]{0,4}\]/u;
const SUFFIXED_AT_START = /^\[[A-Z]{2,12}_[1-9][0-9]{0,4}\]#[0-9a-f]{4}/u;

export class StreamingUnmasker {
  #buffer = "";

  constructor(
    private readonly session: string,
    private readonly vault: VaultStore,
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
        output += (await this.vault.resolve(this.session, suffixed)) ?? suffixed;
        this.#buffer = this.#buffer.slice(suffixed.length);
        continue;
      }

      const base = BASE_AT_START.exec(this.#buffer)?.[0];
      if (base !== undefined) {
        const remainder = this.#buffer.slice(base.length);
        if (remainder.startsWith("#") && /^#[0-9a-f]{0,3}$/u.test(remainder)) break;
        const resolved = await this.vault.resolve(this.session, base);
        if (resolved !== null) {
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
      output += (await this.vault.resolve(this.session, match[0])) ?? match[0];
      cursor = index + match[0].length;
    }
    output += this.#buffer.slice(cursor);
    this.#buffer = "";
    return output;
  }
}

export async function unmaskText(
  text: string,
  session: string,
  vault: VaultStore,
): Promise<string> {
  const unmasker = new StreamingUnmasker(session, vault);
  return (await unmasker.push(text)) + (await unmasker.finish());
}
