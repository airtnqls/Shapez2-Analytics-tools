import { parseShape, rotateRows } from './shape.mjs';
import { scanFeatures } from './features.mjs';
import { runFastConstructors } from './constructors.mjs';

function newMeter() {
  return {
    inspections: 0,
    proofNodes: 0,
    materializations: 0,
    fallbackCalls: 0,
    orientationsTried: 0,
    replayCalls: 0,
    replayFailures: 0,
  };
}

export function compileFastCandidate(code) {
  const parsed = parseShape(code);
  const meter = newMeter();

  // Try the supplied orientation first, then the remaining rotations. This is
  // deterministic and keeps the common zero-rotation path cheapest.
  for (let turns = 0; turns < 4; turns++) {
    meter.orientationsTried++;
    const rows = turns === 0 ? parsed : rotateRows(parsed, turns);
    const result = runFastConstructors(scanFeatures(rows, meter));
    if (result.best) {
      return {
        source: 'fast-candidate',
        orientationTurns: turns,
        rows,
        candidate: result.best,
        attempts: result.attempts,
        meter,
      };
    }
  }
  return { source: 'no-fast-candidate', candidate: null, attempts: [], meter };
}

function callFallback(code, mode, compiled, fallback, reason, replayResult = null) {
  compiled.meter.fallbackCalls++;
  if (fallback) return fallback(code, mode, compiled.meter, { compiled, reason, replayResult });
  return {
    verdict: 'UNKNOWN',
    source: 'fallback-required',
    reason,
    candidateSubtype: compiled.candidate?.subtype,
    meter: compiled.meter,
  };
}

export function solveFast(code, mode = 'verdict', options = {}) {
  const { fallback = null, replay = null } = options ?? {};
  const compiled = compileFastCandidate(code);
  if (!compiled.candidate) return callFallback(code, mode, compiled, fallback, 'no-fast-candidate');

  // Structural recognition is only an accelerator. It cannot promote a
  // POSSIBLE verdict until an independent project-physics adapter replays the
  // concrete primitive receipt and confirms the exact target.
  if (typeof replay !== 'function') {
    return callFallback(code, mode, compiled, fallback, 'replay-adapter-required');
  }
  compiled.meter.replayCalls++;
  const replayResult = replay({
    targetCode: code,
    orientationTurns: compiled.orientationTurns,
    orientedRows: compiled.rows,
    candidate: compiled.candidate,
  });
  if (!replayResult || replayResult.ok !== true) {
    compiled.meter.replayFailures++;
    return callFallback(code, mode, compiled, fallback, 'replay-failed', replayResult ?? null);
  }

  const common = {
    verdict: 'POSSIBLE',
    source: 'fast-certified',
    subtype: compiled.candidate.subtype,
    orientationTurns: compiled.orientationTurns,
    replayCertificate: replayResult.certificate ?? null,
    meter: compiled.meter,
  };
  if (mode === 'verdict') return common;
  if (mode === 'analysis') {
    return { ...common, evidence: compiled.candidate.evidence, attempts: compiled.attempts };
  }
  compiled.meter.proofNodes = compiled.candidate.operations.length + 1;
  return {
    ...common,
    evidence: compiled.candidate.evidence,
    attempts: compiled.attempts,
    operations: compiled.candidate.operations,
    receipt: replayResult.receipt ?? null,
  };
}
