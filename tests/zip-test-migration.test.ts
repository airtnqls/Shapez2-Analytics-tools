import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { migrateZipTests } from "../lib/zip-test-migration";

describe("ZIP v2 test migration", () => {
  const legacy = JSON.parse(readFileSync("public/legacy-tests.json", "utf8")) as unknown;
  const migrated = migrateZipTests(legacy);

  it("preserves every legacy case with stable unique ids", () => {
    expect(migrated).toHaveLength(58);
    expect(new Set(migrated.map((test) => test.id)).size).toBe(58);
  });

  it("converts legacy rotation parameters and structural expectations", () => {
    const rotations = migrated.filter((test) => test.name.startsWith("Rotate"));
    expect(rotations.map((test) => test.operation)).toEqual(["rotate_cw", "rotate_ccw"]);
    expect(rotations.map((test) => test.expected_a)).toEqual(["SS--", "--SS"]);
  });

  it("maps legacy classifier labels to current ZIP families", () => {
    const byInput = new Map(migrated.filter((test) => test.operation === "classifier").map((test) => [test.input_a, test.expected_a]));
    expect(byInput.get("SS-P")).toBe("SWAPPABLE");
    expect(byInput.get("c---:SSSS")).toBe("STACKABLE");
    expect(byInput.get("P-P-:P---:cS-S")).toBe("CLAW");
  });

  it("is idempotent for already migrated exports", () => {
    expect(migrateZipTests(migrated)).toEqual(migrated);
  });
});
