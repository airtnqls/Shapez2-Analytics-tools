import { simplifyExactCode } from "./shape";

export interface ZipTestParams {
  color?: string;
  clockwise?: boolean;
}

export interface ZipTestCase {
  id: string;
  category: string;
  name: string;
  operation: string;
  input_a: string;
  input_b?: string;
  expected_a?: string;
  expected_b?: string;
  params?: string | ZipTestParams;
}

const CLASSIFICATION_BY_INPUT = new Map([
  ["SS-P", "SWAPPABLE"],
  ["cS-P", "SWAPPABLE"],
  ["cP-P:P-SS:--cS", "SWAPPABLE"],
  ["c---:SSSS", "STACKABLE"],
  ["P-P-:P---:cS-S", "CLAW"],
  ["CrCr--Cr--", "BASIC"],
]);

const LEGACY_CLASSIFICATION = new Map([
  ["단순_기하형", "BASIC"],
  ["스왑", "SWAPPABLE"],
  ["하이브리드", "STACKABLE"],
  ["클로", "CLAW"],
]);

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function testId(category: string, index: number, test: Record<string, unknown>): string {
  const seed = `${category}|${index}|${stringValue(test.name)}|${stringValue(test.operation)}|${stringValue(test.input_a)}`;
  let hash = 2166136261;
  for (const character of seed) {
    hash ^= character.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return `zip-test-${(hash >>> 0).toString(36)}-${index}`;
}

function normalizeParams(value: unknown): string | ZipTestParams | undefined {
  if (typeof value === "string") return value || undefined;
  if (!value || typeof value !== "object") return undefined;
  const source = value as Record<string, unknown>;
  const color = typeof source.color === "string" ? source.color : undefined;
  const clockwise = typeof source.clockwise === "boolean" ? source.clockwise : undefined;
  return color || clockwise !== undefined ? { color, clockwise } : undefined;
}

export function migrateZipTest(test: Record<string, unknown>, category: string, index: number): ZipTestCase {
  const inputA = stringValue(test.input_a);
  const rawOperation = stringValue(test.operation) || "apply_physics";
  const params = normalizeParams(test.params);
  const clockwise = typeof params === "object" ? params.clockwise : undefined;
  const operation = rawOperation === "rotate" ? (clockwise === false ? "rotate_ccw" : "rotate_cw") : rawOperation;
  const oldExpectedA = stringValue(test.expected_a);
  const expectedA = operation === "classifier"
    ? CLASSIFICATION_BY_INPUT.get(inputA) ?? LEGACY_CLASSIFICATION.get(oldExpectedA) ?? oldExpectedA
    : simplifyExactCode(oldExpectedA);
  const preservedParams = typeof params === "object" && params.color ? { color: params.color } : typeof params === "string" ? params : undefined;
  return {
    id: stringValue(test.id) || testId(category, index, test),
    category,
    name: stringValue(test.name) || "이름 없는 테스트",
    operation,
    input_a: inputA,
    input_b: stringValue(test.input_b) || undefined,
    expected_a: expectedA,
    expected_b: simplifyExactCode(stringValue(test.expected_b)),
    params: preservedParams,
  };
}

export function migrateZipTests(value: unknown): ZipTestCase[] {
  if (Array.isArray(value)) {
    return value.map((item, index) => {
      const test = item && typeof item === "object" ? item as Record<string, unknown> : {};
      return migrateZipTest(test, stringValue(test.category) || "사용자", index);
    });
  }
  if (!value || typeof value !== "object") throw new Error("테스트 JSON은 배열 또는 카테고리 객체여야 합니다.");
  let index = 0;
  const migrated: ZipTestCase[] = [];
  for (const [category, items] of Object.entries(value as Record<string, unknown>)) {
    if (!Array.isArray(items)) continue;
    for (const item of items) {
      const test = item && typeof item === "object" ? item as Record<string, unknown> : {};
      migrated.push(migrateZipTest(test, category, index));
      index += 1;
    }
  }
  return migrated;
}
