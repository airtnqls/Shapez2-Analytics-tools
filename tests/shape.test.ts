import { describe, expect, it } from "vitest";
import { canonicalCode, mirrorCodePreserve, parseCode, rotateCodePreserve, rotateRows, rowsToCode, simplifyExactCode } from "../lib/shape";

describe("shape parser", () => {
  it("simplifies exact colored shape codes", () => {
    expect(simplifyExactCode("P-P-P-P-:cwSuSuSu:Su--Su--:--SucwSu")).toBe("PPPP:cSSS:S-S-:-ScS");
  });
  it("round trips structural codes", () => {
    const code = "-PPP:SS-P:---P:c--P:cS-S";
    expect(rowsToCode(parseCode(code, 5))).toBe(code);
  });
  it("rotates four times to identity", () => {
    const rows = parseCode("S-P-:cS--", 3);
    expect(rowsToCode(rotateRows(rows, 4))).toBe("S-P-:cS--");
  });
  it("preserves exact tokens across transforms", () => {
    expect(rotateCodePreserve("CrCg----", 1)).toBe("--CrCg--");
    expect(mirrorCodePreserve("CrCg----")).toBe("Cr----Cg");
  });
  it("canonical is symmetry invariant", () => {
    const code = "S-P-:cS--";
    const rotated = rowsToCode(rotateRows(parseCode(code, 3), 1));
    expect(canonicalCode(code, 3)).toBe(canonicalCode(rotated, 3));
  });
});
