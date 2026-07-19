export function parseShape(code) {
  if (typeof code !== 'string' || code.length === 0) return [];
  return code.split(':').map((layer) => {
    if (layer.length === 4) return [...layer];
    if (layer.length !== 8) throw new Error(`invalid layer: ${layer}`);
    const cells = [];
    for (let i = 0; i < 8; i += 2) {
      const token = layer.slice(i, i + 2);
      if (token === '--') cells.push('-');
      else if (token[0] === 'P') cells.push('P');
      else if (token[0] === 'c') cells.push('c');
      else cells.push('S');
    }
    return cells;
  });
}

export function structuralCode(rows) {
  return rows.map((r) => r.join('')).join(':');
}

export function rotateRows(rows, turns = 1) {
  let out = rows.map((r) => [...r]);
  for (let t = 0; t < ((turns % 4) + 4) % 4; t++) {
    out = out.map((r) => [r[3], r[0], r[1], r[2]]);
  }
  return out;
}

export function trimRows(rows) {
  let end = rows.length;
  while (end > 0 && rows[end - 1].every((x) => x === '-')) end--;
  return rows.slice(0, end).map((r) => [...r]);
}

export function canonicalOrientation(rows) {
  let best = null;
  let bestTurns = 0;
  for (let t = 0; t < 4; t++) {
    const candidate = structuralCode(rotateRows(rows, t));
    if (best === null || candidate < best) {
      best = candidate;
      bestTurns = t;
    }
  }
  return { rows: rotateRows(rows, bestTurns), turns: bestTurns, code: best ?? '' };
}

export function rowKey(row) {
  return row.join('');
}

export function assertHalfOrientation(rows) {
  return rows.every((r) => r[2] === '-' && r[3] === '-');
}
