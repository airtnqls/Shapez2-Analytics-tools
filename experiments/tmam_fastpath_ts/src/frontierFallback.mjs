export function pairKey(a, b) {
  return a < b ? `${a}|${b}` : `${b}|${a}`;
}

export function naiveBinaryEnumeration(allShapeIds, operations) {
  let calls = 0;
  const candidates = [];
  for (const op of operations) {
    for (const a of allShapeIds) {
      for (const b of allShapeIds) {
        if (a === b && op.symmetric && !op.allowSelf) continue;
        calls++;
        candidates.push({ op: op.name, a, b });
      }
    }
  }
  return { calls, candidates };
}

export function frontierBinaryEnumeration(allShapeIds, frontierIds, operations, evaluator) {
  let calls = 0;
  let symmetryPrunes = 0;
  let noOpPrunes = 0;
  let duplicateOutputPrunes = 0;
  const seenInvocation = new Set();
  const internedOutputs = new Map();
  const accepted = [];

  for (const op of operations) {
    for (const a of allShapeIds) {
      for (const b of frontierIds) {
        if (a === b && op.symmetric && !op.allowSelf) continue;
        const invocationKey = op.symmetric
          ? `${op.name}:${pairKey(a, b)}`
          : `${op.name}:${a}>${b}`;
        if (seenInvocation.has(invocationKey)) {
          symmetryPrunes++;
          continue;
        }
        seenInvocation.add(invocationKey);
        calls++;
        const outputs = evaluator(op, a, b);
        const inputSet = new Set([a, b]);
        for (const output of outputs) {
          if (inputSet.has(output)) {
            noOpPrunes++;
            continue;
          }
          if (internedOutputs.has(output)) {
            duplicateOutputPrunes++;
            continue;
          }
          internedOutputs.set(output, internedOutputs.size);
          accepted.push({ op: op.name, a, b, output });
        }
      }
    }
  }
  return {
    calls,
    symmetryPrunes,
    noOpPrunes,
    duplicateOutputPrunes,
    internedOutputCount: internedOutputs.size,
    accepted,
  };
}

export function syntheticEvaluator(op, a, b) {
  const ai = Number(a.slice(1));
  const bi = Number(b.slice(1));
  if (op.name === 'SWAP') {
    if ((ai + bi) % 7 === 0) return [a, `Q${(ai * 31 + bi * 17) % 97}`];
    return [`Q${(Math.min(ai, bi) * 19 + Math.max(ai, bi) * 23) % 97}`];
  }
  if ((ai * 3 + bi) % 11 === 0) return [b];
  return [`Q${(ai * 13 + bi * 29) % 127}`];
}

export function benchmarkFrontierFallback(total = 256, frontier = 24) {
  const all = Array.from({ length: total }, (_, i) => `S${i}`);
  const fresh = all.slice(total - frontier);
  const operations = [
    { name: 'SWAP', symmetric: true, allowSelf: false },
    { name: 'STACK', symmetric: false, allowSelf: true },
  ];
  const naive = naiveBinaryEnumeration(all, operations);
  const optimized = frontierBinaryEnumeration(all, fresh, operations, syntheticEvaluator);
  return {
    total,
    frontier,
    naiveCalls: naive.calls,
    optimizedCalls: optimized.calls,
    callReduction: 1 - optimized.calls / naive.calls,
    symmetryPrunes: optimized.symmetryPrunes,
    noOpPrunes: optimized.noOpPrunes,
    duplicateOutputPrunes: optimized.duplicateOutputPrunes,
    internedOutputCount: optimized.internedOutputCount,
  };
}
