import { describe, expect, it } from "vitest";
import { isStable, pushPin, stackShapes } from "../lib/physics";
import {
  bottomPinReceiptProfile,
  bottomPinReceiptRank,
  forwardBatchUpperBound,
  isPureFullPinColumnShape,
  makeReceiptEdgeCertificate,
  verifyReceiptEdgeCertificate,
} from "../lib/pp-rank";
import { canonicalCode, mirrorRows, parseCode, rotateRows, rowsToCode } from "../lib/shape";
import type { Cell, ShapeRows } from "../lib/types";

const cells: Cell[] = ["-", "S", "P", "c"];

function rowsFromNumber(value: number, cap: number): ShapeRows {
  let n = value;
  return Array.from({ length: cap }, () => Array.from({ length: 4 }, () => {
    const cell = cells[n & 3];
    n >>>= 2;
    return cell;
  }));
}

describe("Bottom Pin Receipt Rank", () => {
  it("computes the four bottom P runs", () => {
    const rows = parseCode("PP-P:P--P:P---", 4);
    expect(bottomPinReceiptProfile(rows, 4)).toEqual([3, 1, 0, 2]);
    expect(bottomPinReceiptRank(rows, 4)).toBe(6);
    expect(forwardBatchUpperBound(4)).toBe(15);
  });

  it("is D4 invariant for every cap-1 structure", () => {
    for (let value = 0; value < 256; value += 1) {
      const rows = rowsFromNumber(value, 1);
      const sigma = bottomPinReceiptRank(rows, 1);
      expect(bottomPinReceiptRank(rotateRows(rows, 1), 1)).toBe(sigma);
      expect(bottomPinReceiptRank(mirrorRows(rows), 1)).toBe(sigma);
    }
  });

  it("strictly increases under every stable nondegenerate cap-1 Pin Push", () => {
    for (let value = 1; value < 256; value += 1) {
      const rows = rowsFromNumber(value, 1);
      if (!isStable(rows) || isPureFullPinColumnShape(rows, 1)) continue;
      const pushed = pushPin(rows, 1);
      expect(bottomPinReceiptRank(pushed, 1)).toBeGreaterThan(bottomPinReceiptRank(rows, 1));
    }
  });

  it("Stack does not decrease the stable bottom receipt rank at cap 1", () => {
    for (let bottomValue = 0; bottomValue < 256; bottomValue += 1) {
      const bottom = rowsFromNumber(bottomValue, 1);
      if (!isStable(bottom)) continue;
      const before = bottomPinReceiptRank(bottom, 1);
      for (let topValue = 0; topValue < 256; topValue += 1) {
        const top = rowsFromNumber(topValue, 1);
        expect(bottomPinReceiptRank(stackShapes(bottom, top, 1), 1)).toBeGreaterThanOrEqual(before);
      }
    }
  });

  it("verifies a replayable Claw receipt edge certificate", () => {
    const predecessor = "cPSS:cP-c:cScS:c---:c---";
    const target = "PPPP:-PSS:-P--:-ScS";
    const certificate = makeReceiptEdgeCertificate(predecessor, target, 5);
    expect(certificate.pinPushReplay).toBe(true);
    expect(certificate.strictIncrease).toBe(true);
    expect(verifyReceiptEdgeCertificate(certificate, 5)).toBe(true);
    expect(canonicalCode(rowsToCode(pushPin(parseCode(predecessor, 5), 5)), 5)).toBe(canonicalCode(target, 5));
  });
});
