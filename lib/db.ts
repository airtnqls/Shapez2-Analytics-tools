"use client";

import Dexie, { type EntityTable } from "dexie";
import type { HistoryRecord } from "./types";

class TMAMDatabase extends Dexie {
  history!: EntityTable<HistoryRecord, "id">;

  constructor() {
    super("shapez2-tmam-web");
    this.version(1).stores({
      history: "++id, createdAt, normalizedCode, verdict, shapeType, favorite",
    });
  }
}

export const db = new TMAMDatabase();

export async function saveHistory(record: HistoryRecord): Promise<number> {
  const existing = await db.history.where("normalizedCode").equals(record.normalizedCode).last();
  if (existing?.id) {
    await db.history.update(existing.id, { ...record, id: existing.id, favorite: existing.favorite, note: existing.note });
    return existing.id;
  }
  return (await db.history.add(record)) as number;
}
