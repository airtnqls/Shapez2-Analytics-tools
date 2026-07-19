import test from 'node:test';
import assert from 'node:assert/strict';
import { parseShape, structuralCode } from '../src/shape.mjs';
import { scanFeatures } from '../src/features.mjs';
import { solveFast } from '../src/pipeline.mjs';
import { DeltaProofGraph, diffRows } from '../src/proof.mjs';

const target = 'SuSu----:SuSu----:--Su----:SuSu----:--Su----:cwSu----:SuSu----:--Su----:SuSu----:--Su----:cwSu----';

test('periodic target compiles without fallback', () => {
  const out = solveFast(target, 'proof');
  assert.equal(out.verdict, 'POSSIBLE');
  assert.equal(out.subtype, 'HALF_PERIODIC_PIN_SWAP');
  assert.equal(out.meter.fallbackCalls, 0);
  assert.deepEqual(out.operations, ['SEED', 'PIN', 'SWAP', 'SWAP', 'PIN', 'PIN', 'SWAP', 'SWAP', 'PIN']);
  assert.ok(out.meter.inspections <= parseShape(target).length * 2 + 4);
});

test('mode separation prevents proof work', () => {
  const verdict = solveFast(target, 'verdict');
  const analysis = solveFast(target, 'analysis');
  const proof = solveFast(target, 'proof');
  assert.equal(verdict.meter.proofNodes, 0);
  assert.equal(analysis.meter.proofNodes, 0);
  assert.ok(proof.meter.proofNodes > 0);
  assert.equal(verdict.operations, undefined);
  assert.equal(analysis.operations, undefined);
});

test('mutations safely fall back', () => {
  const rows = target.split(':');
  for (let i = 1; i < rows.length; i++) {
    const mutated = [...rows];
    mutated[i] = 'Su------';
    const out = solveFast(mutated.join(':'), 'verdict');
    assert.notEqual(out.source, 'fast-structural');
  }
});

test('shared feature scan is linear', () => {
  for (const repeats of [2, 4, 8, 16, 32, 64, 128, 256]) {
    const rows = ['SuSu----'];
    for (let i = 0; i < repeats; i++) rows.push('SuSu----', '--Su----', 'SuSu----', '--Su----', 'cwSu----');
    const code = rows.join(':');
    const out = solveFast(code, 'proof');
    assert.equal(out.meter.fallbackCalls, 0);
    assert.ok(out.meter.inspections <= parseShape(code).length * 2 + repeats + 4);
  }
});

test('delta proof materializes exact states and saves cells', () => {
  const root = parseShape('SuSu----');
  const state1 = parseShape('SuSu----:--Su----');
  const state2 = parseShape('SuSu----:--Su----:cwSu----');
  const graph = new DeltaProofGraph(root);
  const n1 = graph.append(0, 'STEP1', diffRows(root, state1), state1);
  const n2 = graph.append(n1, 'STEP2', diffRows(state1, state2), state2);
  assert.equal(structuralCode(graph.materialize(n2)), structuralCode(state2));
  assert.equal(graph.verifyHashes(), true);
  const eagerCells = (root.length + state1.length + state2.length) * 4;
  assert.ok(graph.storageCells() < eagerCells);
});

test('receipt prefix scans once', () => {
  const code = '--P-P-P-:--P-P-P-:SuSu----';
  const rows = parseShape(code);
  const meter = { inspections: 0 };
  const features = scanFeatures(rows, meter);
  assert.equal(features.receiptPrefix, 2);
  assert.equal(meter.inspections, rows.length);
});
