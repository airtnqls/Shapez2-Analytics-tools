export function directHalf(features) {
  if (!features.isHalf || features.crystalEvents.length || features.pinEvents.length) return null;
  return { subtype: 'HALF_DIRECT', cost: features.layers, operations: ['DIRECT_HALF'], evidence: {} };
}

export function periodicPinSwap(features) {
  if (!features.isHalf || !features.rightSpine) return null;
  const events = features.crystalEvents.filter(([, q]) => q === 0).map(([i]) => i);
  if (events.length < 2) return null;
  const period = events[1] - events[0];
  if (period <= 0) return null;
  for (let i = 2; i < events.length; i++) {
    features.meter.inspections++;
    if (events[i] - events[i - 1] !== period) return null;
  }
  const start = events[0] - period + 1;
  if (start < 0 || (features.layers - start) % period !== 0) return null;
  const block = features.leftWord.slice(start, start + period);
  if (block.at(-1) !== 'c' || block.slice(0, -1).includes('c')) return null;
  for (let i = start; i < features.layers; i++) {
    features.meter.inspections++;
    if (features.leftWord[i] !== block[(i - start) % period]) return null;
  }
  const repeats = (features.layers - start) / period;
  const operations = ['SEED'];
  for (let i = 0; i < repeats; i++) operations.push('PIN', 'SWAP', 'SWAP', 'PIN');
  return {
    subtype: 'HALF_PERIODIC_PIN_SWAP',
    cost: operations.length,
    operations,
    evidence: { start, period, repeats, block: block.join(''), events },
  };
}

export function noOverflowReceipt(features) {
  if (features.receiptPrefix <= 0) return null;
  return {
    subtype: 'PP_RECEIPT_CHAIN',
    cost: features.receiptPrefix + 1,
    operations: ['SOLVE_CORE', ...Array(features.receiptPrefix).fill('PIN_PUSH')],
    evidence: { receiptPrefix: features.receiptPrefix },
  };
}

export function monotoneStack(features) {
  if (!features.isHalf || features.ownershipTransitions.length !== 1) return null;
  const split = features.ownershipTransitions[0];
  if (split <= 0 || split >= features.layers) return null;
  return {
    subtype: 'HALF_MONOTONE_STACK',
    cost: features.layers + 1,
    operations: ['BUILD_BOTTOM', 'BUILD_TOP', 'STACK'],
    evidence: { split },
  };
}

export const FAST_CONSTRUCTORS = [directHalf, periodicPinSwap, noOverflowReceipt, monotoneStack];

export function runFastConstructors(features) {
  let best = null;
  const attempts = [];
  for (const constructor of FAST_CONSTRUCTORS) {
    const result = constructor(features);
    attempts.push({ name: constructor.name, accepted: result !== null, cost: result?.cost ?? null });
    if (result && (!best || result.cost < best.cost || (result.cost === best.cost && result.subtype < best.subtype))) best = result;
  }
  return { best, attempts };
}
