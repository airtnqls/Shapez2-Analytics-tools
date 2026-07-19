import type { ShapeRows } from "./types";
import { EMPTY, PIN, canonicalCode, parseCode, rowsToCode } from "./shape";
import { isStable, pushPin } from "./physics";

export type ReceiptProfile = [number, number, number, number];

/**
 * Bottom Pin Receipt Rank.
 *
 * r_q(X) is the number of consecutive P cells starting at layer 0 in column q.
 * sigma(X) = sum_q r_q(X), hence 0 <= sigma(X) <= 4 * cap.
 */
export function bottomPinReceiptProfile(rows: ShapeRows, cap = Math.max(1, rows.length)): ReceiptProfile {
  const profile: ReceiptProfile = [0, 0, 0, 0];
  for (let q = 0; q < 4; q += 1) {
    let length = 0;
    while (length < cap && rows[length]?.[q] === PIN) length += 1;
    profile[q] = length;
  }
  return profile;
}

export function bottomPinReceiptRank(rows: ShapeRows, cap = Math.max(1, rows.length)): number {
  return bottomPinReceiptProfile(rows, cap).reduce((sum, value) => sum + value, 0);
}

export function receiptRankFromCode(code: string, cap: number): number {
  return bottomPinReceiptRank(parseCode(code, cap), cap);
}

/** Empty columns or cap-full P columns only. These are the sole stable non-strict cases. */
export function isPureFullPinColumnShape(rows: ShapeRows, cap: number): boolean {
  let occupiedColumn = false;
  for (let q = 0; q < 4; q += 1) {
    let emptyColumn = true;
    let fullPinColumn = true;
    for (let l = 0; l < cap; l += 1) {
      const cell = rows[l]?.[q] ?? EMPTY;
      if (cell !== EMPTY) emptyColumn = false;
      if (cell !== PIN) fullPinColumn = false;
    }
    if (!emptyColumn && !fullPinColumn) return false;
    occupiedColumn ||= fullPinColumn;
  }
  return occupiedColumn;
}

export interface ReceiptEdgeCertificate {
  target: string;
  prePush: string;
  sigmaTarget: number;
  sigmaPrePush: number;
  strictIncrease: boolean;
  pinPushReplay: boolean;
  stablePrePush: boolean;
  degeneratePrePush: boolean;
}

export function makeReceiptEdgeCertificate(prePushCode: string, targetCode: string, cap: number): ReceiptEdgeCertificate {
  const prePush = parseCode(prePushCode, cap);
  const target = parseCode(targetCode, cap);
  const pushed = rowsToCode(pushPin(prePush, cap));
  const sigmaPrePush = bottomPinReceiptRank(prePush, cap);
  const sigmaTarget = bottomPinReceiptRank(target, cap);
  return {
    target: rowsToCode(target),
    prePush: rowsToCode(prePush),
    sigmaTarget,
    sigmaPrePush,
    strictIncrease: sigmaTarget > sigmaPrePush,
    pinPushReplay: canonicalCode(pushed, cap) === canonicalCode(targetCode, cap),
    stablePrePush: isStable(prePush),
    degeneratePrePush: isPureFullPinColumnShape(prePush, cap),
  };
}

export function verifyReceiptEdgeCertificate(certificate: ReceiptEdgeCertificate, cap: number): boolean {
  const rebuilt = makeReceiptEdgeCertificate(certificate.prePush, certificate.target, cap);
  return (
    rebuilt.pinPushReplay &&
    rebuilt.stablePrePush &&
    !rebuilt.degeneratePrePush &&
    rebuilt.strictIncrease &&
    rebuilt.sigmaTarget === certificate.sigmaTarget &&
    rebuilt.sigmaPrePush === certificate.sigmaPrePush
  );
}

export function ppChainUpperBound(rows: ShapeRows, cap = Math.max(1, rows.length)): number {
  return bottomPinReceiptRank(rows, cap);
}

export function forwardBatchUpperBound(cap: number): number {
  return Math.max(0, 4 * cap - 1);
}
