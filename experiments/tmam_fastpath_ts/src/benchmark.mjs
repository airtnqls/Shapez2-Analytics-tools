import { solveFast } from './pipeline.mjs';

const mapping = { SS: 'SuSu----', '-S': '--Su----', cS: 'cwSu----' };
function makePeriodic(repeats) {
  const rows = ['SS'];
  for (let i = 0; i < repeats; i++) rows.push('SS', '-S', 'SS', '-S', 'cS');
  return rows.map((x) => mapping[x]).join(':');
}

const rows = [];
for (const repeats of [2, 4, 8, 16, 32, 64, 128, 256]) {
  const code = makePeriodic(repeats);
  const verdict = solveFast(code, 'verdict');
  const proof = solveFast(code, 'proof');
  rows.push({ repeats, layers: 1 + repeats * 5, verdictInspections: verdict.meter.inspections, proofNodes: proof.meter.proofNodes, fallbackCalls: proof.meter.fallbackCalls });
}
console.log(JSON.stringify({ schemaVersion: 1, rows }, null, 2));
