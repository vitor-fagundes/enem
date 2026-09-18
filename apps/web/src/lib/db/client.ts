import Database from "better-sqlite3";
import { drizzle } from "drizzle-orm/better-sqlite3";

/** Server-side only. Caller owns the connection and its lifecycle. */
export function openDatabase(filename: string) {
  const sqlite = new Database(filename);
  sqlite.pragma("foreign_keys = ON");
  return { db: drizzle(sqlite), close: () => sqlite.close() };
}
