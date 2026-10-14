import { existsSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import Database from "better-sqlite3";
import { afterAll, beforeAll, describe, expect, test } from "vitest";
import type { AttemptRecord } from "../../src/domain/attempt";
import {
  AttemptStoreError,
  openAttemptStore,
  readAttempts,
} from "../../src/lib/attempts/store";

let dir: string;
let counter = 0;
const newPath = () => join(dir, `attempts-${counter++}.sqlite`);

beforeAll(() => {
  dir = mkdtempSync(join(tmpdir(), "enem-rei-m4-store-"));
});
afterAll(() => rmSync(dir, { recursive: true, force: true }));

const SHA = (c: string) => c.repeat(64);
let uuidCounter = 0;
function uuid() {
  const n = (uuidCounter++).toString(16).padStart(12, "0");
  return `00000000-0000-4000-8000-${n}`;
}

function record(overrides: Partial<AttemptRecord> = {}): AttemptRecord {
  return {
    submission_id: uuid(),
    question_id: "enem-1999-d9-cd9-q7",
    question_file_sha256: SHA("a"),
    question_format: "enem-rei/m2-question/v1",
    area: "Matemática e suas Tecnologias",
    area_code: "MT",
    selected_label: "B",
    evaluation: "CORRECT",
    answer_key_status: "VALID",
    answer_key_value: "B",
    answer_key_resource_id: "key",
    answer_key_resource_sha256: SHA("c"),
    content_resource_sha256: SHA("b"),
    evaluation_rule_version: "evaluateAnswer/v1",
    answered_at: "2026-10-14T12:00:00.000Z",
    duration_ms: 1000,
    ...overrides,
  };
}

function raw(path: string) {
  return new Database(path);
}

describe("attempt store", () => {
  test("creates the schema with user_version 1 and persists after reopening", () => {
    const path = newPath();
    const store = openAttemptStore(path);
    const first = record();
    expect(store.insertIdempotent(first).status).toBe("INSERTED");
    store.close();

    const db = raw(path);
    expect(db.pragma("user_version", { simple: true })).toBe(1);
    const schema = db
      .prepare("SELECT type, name, sql FROM sqlite_schema ORDER BY name")
      .all();
    db.close();

    const reopened = openAttemptStore(path);
    const rows = reopened.list();
    reopened.close();
    expect(rows).toHaveLength(1);
    expect(rows[0]).toEqual({ id: 1, ...first });

    // Abrir de novo não altera o esquema.
    const again = raw(path);
    expect(
      again
        .prepare("SELECT type, name, sql FROM sqlite_schema ORDER BY name")
        .all(),
    ).toEqual(schema);
    again.close();
  });

  test("multiple attempts of the same question, newest first", () => {
    const path = newPath();
    const store = openAttemptStore(path);
    store.insertIdempotent(record({ answered_at: "2026-10-14T12:00:00.000Z" }));
    store.insertIdempotent(
      record({
        answered_at: "2026-10-14T13:00:00.000Z",
        selected_label: "D",
        evaluation: "INCORRECT",
      }),
    );
    store.insertIdempotent(record({ answered_at: "2026-10-14T13:00:00.000Z" }));
    const rows = store.list();
    store.close();
    expect(rows.map((r) => r.id)).toEqual([3, 2, 1]);
  });

  test("idempotent insert: same payload returns the stored row; different payload conflicts", () => {
    const path = newPath();
    const store = openAttemptStore(path);
    const first = record();
    const inserted = store.insertIdempotent(first);
    const again = store.insertIdempotent({
      ...first,
      answered_at: "2027-01-01T00:00:00.000Z",
    });
    expect(again).toEqual({ status: "EXISTING", attempt: inserted.attempt });
    const conflict = store.insertIdempotent({
      ...first,
      selected_label: "D",
      evaluation: "INCORRECT",
    });
    expect(conflict.status).toBe("CONFLICT");
    expect(store.list()).toHaveLength(1);
    expect(store.findBySubmissionId(first.submission_id)).toEqual(
      inserted.attempt,
    );
    store.close();
  });

  test("UPDATE and DELETE are rejected by triggers", () => {
    const path = newPath();
    const store = openAttemptStore(path);
    store.insertIdempotent(record());
    store.close();
    const db = raw(path);
    expect(() =>
      db.prepare("UPDATE attempt SET duration_ms = 1").run(),
    ).toThrow(/append-only/);
    expect(() => db.prepare("DELETE FROM attempt").run()).toThrow(
      /append-only/,
    );
    expect(db.prepare("SELECT count(*) AS n FROM attempt").get()).toEqual({
      n: 1,
    });
    db.close();
  });

  test.each<[string, Partial<AttemptRecord>]>([
    [
      "CORRECT without a key",
      {
        answer_key_status: null,
        answer_key_value: null,
        answer_key_resource_id: null,
        answer_key_resource_sha256: null,
      },
    ],
    ["CORRECT with an annulled key", { answer_key_status: "ANNULLED" }],
    ["CORRECT with an unresolved key", { answer_key_value: null }],
    ["CORRECT with a different alternative", { selected_label: "C" }],
    ["INCORRECT with the key's alternative", { evaluation: "INCORRECT" }],
    ["ANNULLED with a valid key", { evaluation: "ANNULLED" }],
    ["NOT_VERIFIED with a resolved valid key", { evaluation: "NOT_VERIFIED" }],
    ["key status without resource", { answer_key_resource_id: null }],
    ["resource without hash", { answer_key_resource_sha256: null }],
    ["duration above 24 h", { duration_ms: 86_400_001 }],
    ["negative duration", { duration_ms: -1 }],
    ["malformed answered_at", { answered_at: "2026-10-14 12:00:00" }],
    ["malformed submission_id", { submission_id: "X".repeat(36) }],
    ["uppercase file hash", { question_file_sha256: SHA("A") }],
    ["unknown area code", { area_code: "RED" as never }],
  ])("CHECK constraints reject %s", (_name, overrides) => {
    const path = newPath();
    const store = openAttemptStore(path);
    expect(() => store.insertIdempotent(record(overrides))).toThrow();
    expect(store.list()).toHaveLength(0);
    store.close();
  });

  test("uncorrected attempts are accepted with coherent key data", () => {
    const path = newPath();
    const store = openAttemptStore(path);
    for (const r of [
      record({
        evaluation: "NOT_VERIFIED",
        answer_key_status: null,
        answer_key_value: null,
        answer_key_resource_id: null,
        answer_key_resource_sha256: null,
        area_code: null,
        area: "Área Fictícia",
      }),
      record({
        evaluation: "ANNULLED",
        answer_key_status: "ANNULLED",
        answer_key_value: null,
      }),
      record({ evaluation: "NOT_VERIFIED", answer_key_status: "UNKNOWN" }),
    ]) {
      expect(store.insertIdempotent(r).status).toBe("INSERTED");
    }
    store.close();
  });

  test("refuses an unknown user_version without writing", () => {
    const path = newPath();
    const db = raw(path);
    db.pragma("user_version = 7");
    db.close();
    expect(() => openAttemptStore(path)).toThrow(AttemptStoreError);
    expect(readAttempts(path).status).toBe("REFUSED");
    const check = raw(path);
    expect(check.pragma("user_version", { simple: true })).toBe(7);
    expect(
      check.prepare("SELECT count(*) AS n FROM sqlite_schema").get(),
    ).toEqual({ n: 0 });
    check.close();
  });

  test("refuses a non-empty database without user_version", () => {
    const path = newPath();
    const db = raw(path);
    db.exec("CREATE TABLE outra (x INTEGER)");
    db.close();
    expect(() => openAttemptStore(path)).toThrow(AttemptStoreError);
    expect(readAttempts(path).status).toBe("REFUSED");
    const check = raw(path);
    expect(check.pragma("user_version", { simple: true })).toBe(0);
    expect(check.prepare("SELECT name FROM sqlite_schema").all()).toEqual([
      { name: "outra" },
    ]);
    check.close();
  });

  test("readAttempts does not create a missing file", () => {
    const path = newPath();
    expect(readAttempts(path)).toEqual({ status: "READY", attempts: [] });
    expect(existsSync(path)).toBe(false);
  });

  test("readAttempts lists stored rows read-only", () => {
    const path = newPath();
    const store = openAttemptStore(path);
    store.insertIdempotent(record());
    store.close();
    const result = readAttempts(path);
    expect(result.status).toBe("READY");
    if (result.status === "READY") expect(result.attempts).toHaveLength(1);
  });
});
