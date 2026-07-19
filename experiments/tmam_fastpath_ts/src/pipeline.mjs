import { parseShape, canonicalOrientation } from './shape.mjs';
import { scanFeatures } from './features.mjs';
import { runFastConstructors } from './constructors.mjs';

export function solveFast(code, mode = 'verdict', fallback = null) {
  const parsed = parseShape(code);
  const canonical = canonicalOrientation(parsed);
  const meter = { inspections: 0, proofNodes: 0, materializations: 0, fallbackCalls: 0 };
  const features = scanFeatures(canonical.rows, meter);
  const result = runFastConstructors(features);

  if (!result.best) {
    meter.fallbackCalls++;
    return fallback ? fallback(code, mode, meter) : { verdict: 'UNKNOWN', source: 'fallback-required', meter };
  }

  const common = {
    verdict: 'POSSIBLE',
    source: 'fast-structural',
    subtype: result.best.subtype,
    orientationTurns: canonical.turns,
    meter,
  };
  if (mode === 'verdict') return common;
  if (mode === 'analysis') return { ...common, evidence: result.best.evidence, attempts: result.attempts };
  meter.proofNodes = result.best.operations.length + 1;
  return { ...common, evidence: result.best.evidence, attempts: result.attempts, operations: result.best.operations };
}
