import { parseShape, rotateRows } from './shape.mjs';
import { scanFeatures } from './features.mjs';
import { runFastConstructors } from './constructors.mjs';

export function solveFast(code, mode = 'verdict', fallback = null) {
  const parsed = parseShape(code);
  const meter = { inspections: 0, proofNodes: 0, materializations: 0, fallbackCalls: 0, orientationsTried: 0 };

  // Try the supplied orientation first, then the remaining rotations. This is
  // deterministic, preserves the common zero-rotation fast case, and avoids a
  // lexicographic canonical rotation hiding a simple Half orientation.
  let accepted = null;
  let acceptedTurns = 0;
  for (let turns = 0; turns < 4; turns++) {
    meter.orientationsTried++;
    const rows = turns === 0 ? parsed : rotateRows(parsed, turns);
    const features = scanFeatures(rows, meter);
    const result = runFastConstructors(features);
    if (result.best) {
      accepted = result;
      acceptedTurns = turns;
      break;
    }
  }

  if (!accepted) {
    meter.fallbackCalls++;
    return fallback ? fallback(code, mode, meter) : { verdict: 'UNKNOWN', source: 'fallback-required', meter };
  }

  const common = {
    verdict: 'POSSIBLE',
    source: 'fast-structural',
    subtype: accepted.best.subtype,
    orientationTurns: acceptedTurns,
    meter,
  };
  if (mode === 'verdict') return common;
  if (mode === 'analysis') return { ...common, evidence: accepted.best.evidence, attempts: accepted.attempts };
  meter.proofNodes = accepted.best.operations.length + 1;
  return { ...common, evidence: accepted.best.evidence, attempts: accepted.attempts, operations: accepted.best.operations };
}
