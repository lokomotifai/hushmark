import en from "../messages/en.json";
import tr from "../messages/tr.json";
import { expect, it } from "vitest";

it("keeps the complete English fallback in lockstep with the Turkish default", () => {
  expect(flattenKeys(en)).toEqual(flattenKeys(tr));
  expect(flattenValues(en).every((value) => value.trim().length > 0)).toBe(true);
  expect(flattenValues(tr).every((value) => value.trim().length > 0)).toBe(true);
});

function flattenKeys(value: Record<string, unknown>, prefix = ""): string[] {
  return Object.entries(value)
    .flatMap(([key, child]) => {
      const path = prefix.length === 0 ? key : `${prefix}.${key}`;
      return typeof child === "object" && child !== null
        ? flattenKeys(child as Record<string, unknown>, path)
        : [path];
    })
    .sort();
}

function flattenValues(value: Record<string, unknown>): string[] {
  return Object.values(value).flatMap((child) =>
    typeof child === "object" && child !== null
      ? flattenValues(child as Record<string, unknown>)
      : typeof child === "string"
        ? [child]
        : [],
  );
}
