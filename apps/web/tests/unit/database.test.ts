import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { sql } from "drizzle-orm";
import { expect, test } from "vitest";
import { openDatabase } from "../../src/lib/db/client";

test("Drizzle persists data in a local SQLite file with foreign keys enabled", () => {
  const directory = mkdtempSync(join(tmpdir(), "enem-rei-"));
  const filename = join(directory, "smoke.sqlite");
  try {
    const connection = openDatabase(filename);
    try {
      expect(connection.db.get(sql`PRAGMA foreign_keys`)).toEqual({
        foreign_keys: 1,
      });
      connection.db.run(sql`CREATE TABLE smoke (value INTEGER NOT NULL)`);
      connection.db.run(sql`INSERT INTO smoke VALUES (42)`);
    } finally {
      connection.close();
    }
    const reopened = openDatabase(filename);
    try {
      expect(reopened.db.get(sql`SELECT value FROM smoke`)).toEqual({
        value: 42,
      });
    } finally {
      reopened.close();
    }
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});
