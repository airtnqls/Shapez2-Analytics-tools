import { assertHalfOrientation, rowKey } from './shape.mjs';

export function scanFeatures(rows, meter = { inspections: 0 }) {
  const features = {
    layers: rows.length,
    isHalf: true,
    occupiedColumnsMask: 0,
    crystalEvents: [],
    pinEvents: [],
    receiptPrefix: 0,
    rowRuns: [],
    ownershipTransitions: [],
    rightSpine: true,
    leftWord: [],
    rowKeys: [],
    ambiguous: false,
    meter,
  };

  let previousKey = null;
  let runStart = 0;
  let previousOwner = null;
  for (let i = 0; i < rows.length; i++) {
    meter.inspections++;
    const row = rows[i];
    const key = rowKey(row);
    features.rowKeys.push(key);
    if (!assertHalfOrientation([row])) features.isHalf = false;
    for (let q = 0; q < 4; q++) {
      if (row[q] !== '-') features.occupiedColumnsMask |= 1 << q;
      if (row[q] === 'c') features.crystalEvents.push([i, q]);
      if (row[q] === 'P') features.pinEvents.push([i, q]);
    }
    if (!(row[1] === 'S' && row[2] === '-' && row[3] === '-')) features.rightSpine = false;
    features.leftWord.push(row[0]);

    const owner = row.some((x) => x === 'c' || x === 'P') ? 'event' : 'plain';
    if (previousOwner !== null && owner !== previousOwner) {
      features.ownershipTransitions.push(i);
    }
    previousOwner = owner;

    if (previousKey === null) {
      previousKey = key;
      runStart = i;
    } else if (key !== previousKey) {
      features.rowRuns.push({ key: previousKey, start: runStart, end: i });
      previousKey = key;
      runStart = i;
    }
  }
  if (previousKey !== null) features.rowRuns.push({ key: previousKey, start: runStart, end: rows.length });

  while (
    features.receiptPrefix < rows.length &&
    rows[features.receiptPrefix][0] === '-' &&
    rows[features.receiptPrefix][1] === '-' &&
    rows[features.receiptPrefix][2] === 'P' &&
    rows[features.receiptPrefix][3] === 'P'
  ) {
    features.receiptPrefix++;
  }
  return features;
}
