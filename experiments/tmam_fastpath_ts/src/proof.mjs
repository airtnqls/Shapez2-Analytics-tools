import { structuralCode } from './shape.mjs';

function fnv1a(text) {
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h.toString(16).padStart(8, '0');
}

export class DeltaProofGraph {
  constructor(rootRows) {
    this.checkpoints = new Map([[0, rootRows.map((r) => [...r])]]);
    this.nodes = [{ id: 0, parent: null, operation: 'ROOT', changes: [], resultHash: fnv1a(structuralCode(rootRows)) }];
    this.materializeCache = new Map([[0, rootRows.map((r) => [...r])]]);
  }

  append(parent, operation, changes, resultRows = null) {
    const id = this.nodes.length;
    const rows = resultRows ?? applyChanges(this.materialize(parent), changes);
    this.nodes.push({ id, parent, operation, changes: changes.map(([i, r]) => [i, [...r]]), resultHash: fnv1a(structuralCode(rows)) });
    if (id % 32 === 0) this.checkpoints.set(id, rows.map((r) => [...r]));
    return id;
  }

  materialize(id) {
    if (this.materializeCache.has(id)) return this.materializeCache.get(id).map((r) => [...r]);
    if (this.checkpoints.has(id)) {
      const rows = this.checkpoints.get(id).map((r) => [...r]);
      this.materializeCache.set(id, rows);
      return rows.map((r) => [...r]);
    }
    const chain = [];
    let cursor = id;
    while (!this.materializeCache.has(cursor) && !this.checkpoints.has(cursor)) {
      const node = this.nodes[cursor];
      chain.push(node);
      cursor = node.parent;
    }
    let rows = this.materializeCache.has(cursor)
      ? this.materializeCache.get(cursor).map((r) => [...r])
      : this.checkpoints.get(cursor).map((r) => [...r]);
    for (let i = chain.length - 1; i >= 0; i--) rows = applyChanges(rows, chain[i].changes);
    this.materializeCache.set(id, rows.map((r) => [...r]));
    return rows;
  }

  verifyHashes() {
    for (const node of this.nodes) {
      if (fnv1a(structuralCode(this.materialize(node.id))) !== node.resultHash) return false;
    }
    return true;
  }

  storageCells() {
    let cells = 0;
    for (const rows of this.checkpoints.values()) cells += rows.length * 4;
    for (const node of this.nodes) cells += node.changes.length * 4;
    return cells;
  }
}

export function applyChanges(rows, changes) {
  const out = rows.map((r) => [...r]);
  for (const [index, row] of changes) {
    while (out.length <= index) out.push(['-', '-', '-', '-']);
    out[index] = [...row];
  }
  while (out.length && out[out.length - 1].every((x) => x === '-')) out.pop();
  return out;
}

export function diffRows(before, after) {
  const max = Math.max(before.length, after.length);
  const changes = [];
  for (let i = 0; i < max; i++) {
    const a = before[i] ?? ['-', '-', '-', '-'];
    const b = after[i] ?? ['-', '-', '-', '-'];
    if (a.join('') !== b.join('')) changes.push([i, b]);
  }
  return changes;
}
