import { compileFastCandidate, solveFast } from './pipeline.mjs';

const mapping = { SS: 'SuSu----', '-S': '--Su----', cS: 'cwSu----' };
function makePeriodic(repeats) {
  const rows = ['SS'];
  for (let i = 0; i < repeats; i++) rows.push('SS', '-S', 'SS', '-S', 'cS');
  return rows.map((x) => mapping[x]).join(':');
}

const testReplay = ({ candidate }) => ({ ok: true, certificate: 'benchmark-test-adapter', receipt: candidate.operations });
const rows = [];
for (const repeats of [2, 4, 8, 16, 32, 64, 128, 256]) {
  const code = makePeriodic(repeats);
  const compiled = compileFastCandidate(code);
  const uncertified = solveFast(code, 'verdict');
  const certified = solveFast(code, 'proof', { replay: testReplay });
  rows.push({
    repeats,
    layers: 1 + repeats * 5,
    candidateSubtype: compiled.candidate?.subtype ?? null,
    candidateInspections: compiled.meter.inspections,
    uncertifiedVerdict: uncertified.verdict,
    uncertifiedFallbackCalls: uncertified.meter.fallbackCalls,
    certifiedVerdict: certified.verdict,
    certifiedProofNodes: certified.meter.proofNodes,
    certifiedReplayCalls: certified.meter.replayCalls,
  });
}
console.log(JSON.stringify({ schemaVersion: 2, safetyContract: 'candidate-never-promotes-without-replay', rows }, null, 2));
