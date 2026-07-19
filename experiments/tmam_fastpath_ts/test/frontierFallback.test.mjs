import test from 'node:test';
import assert from 'node:assert/strict';
import {
  benchmarkFrontierFallback,
  frontierBinaryEnumeration,
  naiveBinaryEnumeration,
  syntheticEvaluator,
} from '../src/frontierFallback.mjs';

const operations = [
  { name: 'SWAP', symmetric: true, allowSelf: false },
  { name: 'STACK', symmetric: false, allowSelf: true },
];

test('frontier-only enumeration sharply reduces binary calls', () => {
  const report = benchmarkFrontierFallback(256, 24);
  assert.ok(report.callReduction >= 0.85, report);
  assert.ok(report.symmetryPrunes > 0, report);
  assert.ok(report.noOpPrunes > 0, report);
  assert.ok(report.duplicateOutputPrunes > 0, report);
});

test('symmetric Swap pair is executed once', () => {
  const all = ['S0', 'S1', 'S2'];
  const frontier = ['S1', 'S2'];
  const out = frontierBinaryEnumeration(all, frontier, [operations[0]], syntheticEvaluator);
  const keys = out.accepted.map((x) => [x.a, x.b].sort().join('|'));
  assert.equal(new Set(keys).size, keys.length);
});

test('frontier expansion is bounded by all times frontier', () => {
  for (const total of [64, 128, 256, 512]) {
    const frontierSize = 16;
    const all = Array.from({ length: total }, (_, i) => `S${i}`);
    const frontier = all.slice(-frontierSize);
    const naive = naiveBinaryEnumeration(all, operations);
    const optimized = frontierBinaryEnumeration(all, frontier, operations, syntheticEvaluator);
    assert.ok(optimized.calls <= operations.length * total * frontierSize);
    assert.ok(optimized.calls < naive.calls);
  }
});

test('shape output interning removes repeated graph nodes', () => {
  const all = Array.from({ length: 80 }, (_, i) => `S${i}`);
  const frontier = all.slice(-12);
  const out = frontierBinaryEnumeration(all, frontier, operations, syntheticEvaluator);
  assert.equal(new Set(out.accepted.map((x) => x.output)).size, out.accepted.length);
  assert.equal(out.internedOutputCount, out.accepted.length);
});
