import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";

function structuralFromToken(token) {
  if (!token || token[0] === "-") return "-";
  if (token[0] === "P" || token[0] === "p") return "P";
  if (token[0] === "c") return "c";
  return "S";
}

function simplifyExactCode(value) {
  const raw = String(value || "").trim().replace(/[{}\s]/g, "");
  if (!raw) return "";
  const simplified = raw.split(":").map((layer) => {
    if (layer.length <= 4 && [...layer].every((cell) => "-SPc".includes(cell))) return layer.padEnd(4, "-");
    if (layer.length % 2 !== 0) {
      return [...layer].filter((cell) => "-SPc".includes(cell)).join("").padEnd(4, "-").slice(0, 4);
    }
    const tokens = Array.from({ length: Math.min(4, layer.length / 2) }, (_, index) => layer.slice(index * 2, index * 2 + 2));
    while (tokens.length < 4) tokens.push("--");
    return tokens.map(structuralFromToken).join("");
  });
  while (simplified.length && simplified.at(-1) === "----") simplified.pop();
  return simplified.join(":");
}

const classificationByInput = new Map([
  ["SS-P", "SWAPPABLE"],
  ["cS-P", "SWAPPABLE"],
  ["cP-P:P-SS:--cS", "SWAPPABLE"],
  ["c---:SSSS", "STACKABLE"],
  ["P-P-:P---:cS-S", "CLAW"],
  ["CrCr--Cr--", "BASIC"],
]);

const sourcePath = path.resolve("public/legacy-tests.json");
const targetPath = path.resolve("public/zip-tests.json");
const source = JSON.parse(await readFile(sourcePath, "utf8"));

const migrated = Object.fromEntries(Object.entries(source).map(([category, tests]) => [category, tests.map((test) => {
  const operation = test.operation === "rotate"
    ? (test.params?.clockwise === false ? "rotate_ccw" : "rotate_cw")
    : test.operation;
  const expectedA = operation === "classifier"
    ? classificationByInput.get(test.input_a)
    : simplifyExactCode(test.expected_a);
  if (expectedA == null) throw new Error(`분류 기대값 마이그레이션 누락: ${test.name} / ${test.input_a}`);
  return {
    ...test,
    operation,
    expected_a: expectedA,
    expected_b: simplifyExactCode(test.expected_b),
    params: test.params?.color ? { color: test.params.color } : undefined,
  };
})]));

await writeFile(targetPath, `${JSON.stringify(migrated, null, 2)}\n`, "utf8");
console.log(JSON.stringify({ status: "PASS", source: path.relative(process.cwd(), sourcePath), target: path.relative(process.cwd(), targetPath), tests: Object.values(migrated).reduce((sum, tests) => sum + tests.length, 0) }));
