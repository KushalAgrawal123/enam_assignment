import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { buildDigest } from "./digest";

const fixture = JSON.parse(
  readFileSync(join(__dirname, "../../backend/tests/fixtures/digest_cases.json"), "utf8"),
);

describe("digest.ts matches digest.py", () => {
  for (const c of fixture.cases) {
    it(`window ${c.start} → ${c.end}`, () => {
      expect(buildDigest(fixture.filings, c.start, c.end)).toEqual(c.expected);
    });
  }
});
