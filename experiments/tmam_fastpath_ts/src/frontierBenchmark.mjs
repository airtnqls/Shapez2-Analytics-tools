import { benchmarkFrontierFallback } from './frontierFallback.mjs';

const rows = [];
for (const total of [64, 128, 256, 512, 1024]) {
  for (const frontier of [8, 16, 32]) {
    if (frontier >= total) continue;
    rows.push(benchmarkFrontierFallback(total, frontier));
  }
}

console.log(JSON.stringify({
  schemaVersion: 1,
  contract: 'all-x-frontier with symmetry/no-op/output-intern pruning',
  rows,
}, null, 2));
