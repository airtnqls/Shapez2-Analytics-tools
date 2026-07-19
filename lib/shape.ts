import type { Cell, ShapeRows } from "./types";

export const EMPTY: Cell = "-";
export const ORDINARY: Cell = "S";
export const PIN: Cell = "P";
export const CRYSTAL: Cell = "c";
export const VALID_CELLS = new Set<Cell>([EMPTY, ORDINARY, PIN, CRYSTAL]);
export const ADJ: readonly [readonly [number, number], readonly [number, number], readonly [number, number], readonly [number, number]] = [
  [1, 3],
  [0, 2],
  [1, 3],
  [0, 2],
];

export interface DisplayCell {
  structural: Cell;
  type: string;
  color: string;
  raw: string;
}

export interface DisplayLayer {
  cells: [DisplayCell, DisplayCell, DisplayCell, DisplayCell];
}

export function emptyRow(): Cell[] {
  return [EMPTY, EMPTY, EMPTY, EMPTY];
}

export function cloneRows(rows: ShapeRows): ShapeRows {
  return rows.map((row) => [...row]);
}

export function trimRows(rows: ShapeRows): ShapeRows {
  const out = cloneRows(rows);
  while (out.length && out[out.length - 1].every((cell) => cell === EMPTY)) out.pop();
  return out;
}

export function padRows(rows: ShapeRows, cap: number): ShapeRows {
  const out = cloneRows(rows).slice(0, cap);
  while (out.length < cap) out.push(emptyRow());
  return out;
}

export function rowsToCode(rows: ShapeRows): string {
  return trimRows(rows).map((row) => row.join("")).join(":");
}

function structuralFromToken(token: string): Cell {
  if (!token || token[0] === "-") return EMPTY;
  const type = token[0];
  if (type === "P" || type === "p") return PIN;
  if (type === "c") return CRYSTAL;
  return ORDINARY;
}

export function simplifyExactCode(value: string): string {
  const raw = value.trim().replace(/[{}\s]/g, "");
  if (!raw) return "";
  const layers = raw.split(":");
  const simplified = layers.map((layer) => {
    if (layer.length <= 4 && [...layer].every((ch) => "-SPc".includes(ch))) {
      return layer.padEnd(4, "-");
    }
    if (layer.length % 2 !== 0) {
      const clean = [...layer].filter((ch) => "-SPc".includes(ch)).join("");
      return clean.padEnd(4, "-").slice(0, 4);
    }
    const tokens = Array.from({ length: Math.min(4, layer.length / 2) }, (_, i) => layer.slice(i * 2, i * 2 + 2));
    while (tokens.length < 4) tokens.push("--");
    return tokens.map(structuralFromToken).join("");
  });
  while (simplified.length && simplified[simplified.length - 1] === "----") simplified.pop();
  return simplified.join(":");
}

export function parseCode(value: string, cap?: number): ShapeRows {
  const simplified = simplifyExactCode(value);
  const layers = simplified ? simplified.split(":") : [];
  const rows: ShapeRows = layers.map((layer) => {
    const padded = layer.padEnd(4, "-").slice(0, 4);
    const cells = [...padded] as Cell[];
    if (cells.some((cell) => !VALID_CELLS.has(cell))) throw new Error(`잘못된 구조 셀: ${layer}`);
    return cells;
  });
  return cap == null ? trimRows(rows) : padRows(rows, cap);
}

export function normalizeCode(value: string, cap: number): string {
  if (!Number.isInteger(cap) || cap < 1) throw new Error("Cap은 1 이상의 정수여야 합니다.");
  return rowsToCode(parseCode(value, cap));
}

export function displayLayers(value: string): DisplayLayer[] {
  const raw = value.trim().replace(/[{}\s]/g, "");
  if (!raw) return [];
  return raw.split(":").map((layer) => {
    let tokens: string[];
    if (layer.length <= 4 && [...layer].every((ch) => "-SPc".includes(ch))) {
      tokens = [...layer.padEnd(4, "-")].map((ch) => (ch === "-" ? "--" : `${ch}u`));
    } else {
      tokens = Array.from({ length: Math.min(4, Math.ceil(layer.length / 2)) }, (_, i) => layer.slice(i * 2, i * 2 + 2).padEnd(2, "-"));
      while (tokens.length < 4) tokens.push("--");
    }
    const cells = tokens.slice(0, 4).map((token) => ({
      structural: structuralFromToken(token),
      type: token[0] ?? "-",
      color: token[1] ?? "-",
      raw: token,
    })) as [DisplayCell, DisplayCell, DisplayCell, DisplayCell];
    return { cells };
  });
}

export function getCell(rows: ShapeRows, layer: number, column: number): Cell {
  if (layer < 0 || column < 0 || column >= 4 || layer >= rows.length) return EMPTY;
  return rows[layer][column] ?? EMPTY;
}

export function occupied(cell: Cell): boolean {
  return cell !== EMPTY;
}

export function nonPin(cell: Cell): boolean {
  return cell === ORDINARY || cell === CRYSTAL;
}

export function rotateRows(rows: ShapeRows, turns = 1): ShapeRows {
  let out = cloneRows(rows);
  for (let i = 0; i < ((turns % 4) + 4) % 4; i += 1) {
    out = out.map((row) => [row[3], row[0], row[1], row[2]]);
  }
  return trimRows(out);
}

export function mirrorRows(rows: ShapeRows): ShapeRows {
  return trimRows(rows.map((row) => [row[0], row[3], row[2], row[1]]));
}

export function canonicalCode(value: string, cap: number): string {
  const rows = parseCode(value, cap);
  const variants: string[] = [];
  let current = rows;
  for (let turn = 0; turn < 4; turn += 1) {
    variants.push(rowsToCode(current));
    variants.push(rowsToCode(mirrorRows(current)));
    current = rotateRows(current, 1);
  }
  return variants.sort()[0] ?? "";
}

export function pillars(rows: ShapeRows): string[] {
  const work = trimRows(rows);
  return Array.from({ length: 4 }, (_, q) => {
    const chars = work.map((row) => row[q]);
    while (chars.length && chars[chars.length - 1] === EMPTY) chars.pop();
    return chars.join("");
  });
}

export function shapeHeight(rows: ShapeRows): number {
  return trimRows(rows).length;
}

export function occupiedCount(rows: ShapeRows): number {
  return trimRows(rows).reduce((sum, row) => sum + row.filter(occupied).length, 0);
}

export function activeColumnCount(rows: ShapeRows): number {
  const ps = pillars(rows);
  return ps.filter(Boolean).length;
}

export function maskColumns(rows: ShapeRows, columns: number[]): ShapeRows {
  const allowed = new Set(columns);
  return trimRows(rows.map((row) => row.map((cell, q) => (allowed.has(q) ? cell : EMPTY)) as Cell[]));
}

export function structuralLayerTokens(value: string): string[] {
  const normalized = simplifyExactCode(value);
  return normalized ? normalized.split(":") : [];
}


export function rotateCodePreserve(value: string, turns = 1): string {
  const raw = value.trim().replace(/[{}\s]/g, "");
  const exact = raw.split(":").some((layer) => layer.length > 4);
  let layers = displayLayers(value).map((layer) => layer.cells.map((cell) => cell.structural === EMPTY ? "--" : cell.raw.padEnd(2, "-").slice(0, 2)));
  for (let i = 0; i < ((turns % 4) + 4) % 4; i += 1) layers = layers.map((row) => [row[3], row[0], row[1], row[2]]);
  while (layers.length && layers[layers.length - 1].every((token) => token[0] === "-")) layers.pop();
  return layers.map((row) => exact ? row.join("") : row.map((token) => structuralFromToken(token)).join("")).join(":");
}

export function mirrorCodePreserve(value: string): string {
  const raw = value.trim().replace(/[{}\s]/g, "");
  const exact = raw.split(":").some((layer) => layer.length > 4);
  const layers = displayLayers(value).map((layer) => {
    const row = layer.cells.map((cell) => cell.structural === EMPTY ? "--" : cell.raw.padEnd(2, "-").slice(0, 2));
    return [row[0], row[3], row[2], row[1]];
  });
  while (layers.length && layers[layers.length - 1].every((token) => token[0] === "-")) layers.pop();
  return layers.map((row) => exact ? row.join("") : row.map((token) => structuralFromToken(token)).join("")).join(":");
}

export function extractShapeCodes(text: string): string[] {
  const results: string[] = [];
  const braceMatches = [...text.matchAll(/\{([^{}]+)\}/g)].map((match) => match[1].trim());
  if (braceMatches.length) results.push(...braceMatches);
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    if (line.includes("{") && line.includes("}")) continue;
    const candidate = line.split(/\s+/).find((part) => part.includes(":") || /^[\-SPcCRWXYFHGMDu rgbwkycmpo]+$/i.test(part));
    if (candidate) results.push(candidate.replace(/[{},]/g, ""));
  }
  return [...new Set(results.filter(Boolean))];
}
