import test from 'node:test';
import assert from 'node:assert/strict';
import { parseShape, structuralCode } from '../src/shape.mjs';
import { scanFeatures } from '../src/features.mjs';
import { compileFastCandidate, solveFast } from '../src/pipeline.mjs';
import { DeltaProofGraph, diffRows } from '../src/proof.mjs';

const target = 'SuSu----:SuSu----:--Su----:SuSu----:--Su----:cwSu----:SuSu----:--Su----:SuSu----:--Su----:cwSu----';

const acceptingTestReplay = ({ candidate }) => ({
  ok: candidate.subtype === 'HALF_PERIODIC_PIN_SWAP',
  certificate: 'test-only-structural-replay',
  receipt: candidate.operations,
});

test('periodic target compiles as a candidate', () => {
  const compiled = compileFastCandidate(target);
  assert.equal(compiled.source, 'fast-candidate');
  assert.equal(compiled.candidate.subtype, 'HALF_PERIODIC_PIN_SWAP');
  assert.equal(compiled.orientationTurns, 0);
  assert.deepEqual(compiled.candidate.operations, ['SEED', 'PIN', 'SWAP', 'SWAP', 'PIN', 'PIN', 'SWAP', 'SWAP', 'PIN']);
  assert.ok(compiled.meter.inspections <= parseShape(target).length * 2 + 4);
});

test('candidate cannot promote without a replay adapter', () => {
  const out = solveFast(target, 'verdict');
  assert.equal(out.verdict, 'UNKNOWN');
  assert.equal(out.source, 'fallback-required');
  assert.equal(out.reason, 'replay-adapter-required');
  assert.equal(out.candidateSubtype, 'HALF_PERIODIC_PIN_SWAP');
  assert.equal(out.meter.fallbackCalls, 1);
  assert.equal(out.meter.replayCalls, 0);
});

test('failed replay always falls back', () => {
  const out = solveFast(target, 'verdict', { replay: () => ({ ok: false, reason: 'mismatch' }) });
  assert.equal(out.verdict, 'UNKNOWN');
  assert.equal(out.reason, 'replay-failed');
  assert.equal(out.meter.replayCalls, 1);
  assert.equal(out.meter.replayFailures, 1);
  assert.equal(out.meter.fallbackCalls, 1);
});

test('certified replay promotes the target', () => {
  const out = solveFast(target, 'proof', { replay: acceptingTestReplay });
  assert.equal(out.verdict, 'POSSIBLE');
  assert.equal(out.source, 'fast-certified');
  assert.equal(out.subtype, 'HALF_PERIODIC_PIN_SWAP');
  assert.equal(out.replayCertificate, 'test-only-structural-replay');
  assert.equal(out.meter.fallbackCalls, 0);
  assert.equal(out.meter.replayCalls, 1);
  assert.deepEqual(out.operations, out.receipt);
});

test('rotated periodic target is still recognized', () => {
  const original = parseShape(target);
  const rotated = original.map((r) => [r[3], r[0], r[1], r[2]]).map((r) => r.join('')).join(':');
  const compiled = compileFastCandidate(rotated);
  assert.equal(compiled.candidate.subtype, 'HALF_PERIODIC_PIN_SWAP');
  assert.ok(compiled.orientationTurns > 0);
  assert.ok(compiled.meter.inspections <= original.length * 6 + 8);
});

test('mode separation prevents proof graph construction', () => {
  const verdict = solveFast(target, 'verdict', { replay: acceptingTestReplay });
  const analysis = solveFast(target, 'analysis', { replay: acceptingTestReplay });
  const proof = solveFast(target, 'proof', { replay: acceptingTestReplay });
  assert.equal(verdict.meter.proofNodes, 0);
  assert.equal(analysis.meter.proofNodes, 0);
  assert.ok(proof.meter.proofNodes > 0);
  assert.equal(verdict.operations, undefined);
  assert.equal(analysis.operations, undefined);
});

test('mutations do not receive a certified fast verdict', () => {
  const rows = target.split(':');
  for (let i = 1; i < rows.length; i++) {
    const mutated = [...rows];
    mutated[i] = 'Su------';
    const out = solveFast(mutated.join(':'), 'verdict', { replay: acceptingTestReplay });
    assert.notEqual(out.source, 'fast-certified');
  }
});

test('shared feature scan is linear', () => {
  for (const repeats of [2, 4, 8, 16, 32, 64, 128, 256]) {
    const rows = ['SuSu----'];
    for (let i = 0; i < repeats; i++) rows.push('SuSu----', '--Su----', 'SuSu----', '--Su----', 'cwSu----');
    const code = rows.join(':');
    const compiled = compileFastCandidate(code);
    assert.equal(compiled.candidate.subtype, 'HALF_PERIODIC_PIN_SWAP');
    assert.equal(compiled.orientationTurns, 0);
    assert.ok(compiled.meter.inspections <= parseShape(code).length * 2 + repeats + 4);
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
  const code = '--PP:--PP:SS--';
  const rows = parseShape(code);
  const meter = { inspections: 0 };
  const features = scanFeatures(rows, meter);
  assert.equal(features.receiptPrefix, 2);
  assert.equal(meter.inspections, rows.length);
});
