/**
 * Server-side only. Banco SQLite operacional de tentativas (ADR-0003;
 * docs/m4-registro-tentativas.md, Modelo de dados): DDL idempotente aplicada
 * com better-sqlite3 e versionada por `PRAGMA user_version`; consultas
 * tipadas com drizzle-orm. Tabela append-only: gatilhos abortam UPDATE e
 * DELETE. O chamador abre e fecha a conexão explicitamente.
 */
import { existsSync } from "node:fs";
import Database from "better-sqlite3";
import { desc, eq } from "drizzle-orm";
import { drizzle } from "drizzle-orm/better-sqlite3";
import { integer, sqliteTable, text } from "drizzle-orm/sqlite-core";
import { AREA_CODES } from "../../domain/area";
import {
  type AttemptRecord,
  type StoredAttempt,
  samePayload,
} from "../../domain/attempt";
import { ALTERNATIVE_LABELS, ANSWER_KEY_STATUSES } from "../../domain/question";

export const ATTEMPT_SCHEMA_VERSION = 1;

/** DDL do documento do M4, sem o PRAGMA (aplicado à parte, na mesma transação). */
export const ATTEMPT_DDL = `
CREATE TABLE IF NOT EXISTS attempt (
  id                          INTEGER PRIMARY KEY AUTOINCREMENT,
  submission_id               TEXT    NOT NULL UNIQUE
    CHECK (length(submission_id) = 36 AND submission_id NOT GLOB '*[^0-9a-f-]*'),
  question_id                 TEXT    NOT NULL CHECK (length(question_id) > 0),
  question_file_sha256        TEXT    NOT NULL
    CHECK (length(question_file_sha256) = 64 AND question_file_sha256 NOT GLOB '*[^0-9a-f]*'),
  question_format             TEXT    NOT NULL,
  area                        TEXT    NOT NULL,
  area_code                   TEXT    CHECK (area_code IN ('LC', 'CH', 'CN', 'MT')),
  selected_label              TEXT    NOT NULL CHECK (selected_label IN ('A', 'B', 'C', 'D', 'E')),
  evaluation                  TEXT    NOT NULL
    CHECK (evaluation IN ('CORRECT', 'INCORRECT', 'NOT_VERIFIED', 'ANNULLED')),
  answer_key_status           TEXT    CHECK (answer_key_status IN ('VALID', 'ANNULLED', 'UNKNOWN')),
  answer_key_value            TEXT    CHECK (answer_key_value IN ('A', 'B', 'C', 'D', 'E')),
  answer_key_resource_id      TEXT,
  answer_key_resource_sha256  TEXT
    CHECK (answer_key_resource_sha256 IS NULL OR
           (length(answer_key_resource_sha256) = 64 AND answer_key_resource_sha256 NOT GLOB '*[^0-9a-f]*')),
  content_resource_sha256     TEXT    NOT NULL
    CHECK (length(content_resource_sha256) = 64 AND content_resource_sha256 NOT GLOB '*[^0-9a-f]*'),
  evaluation_rule_version     TEXT    NOT NULL,
  answered_at                 TEXT    NOT NULL CHECK (answered_at GLOB
    '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-9][0-9][0-9]Z'),
  duration_ms                 INTEGER NOT NULL CHECK (duration_ms BETWEEN 0 AND 86400000),

  CHECK ((answer_key_status IS NULL) = (answer_key_resource_id IS NULL)),
  CHECK ((answer_key_resource_id IS NULL) = (answer_key_resource_sha256 IS NULL)),
  CHECK (answer_key_status IS NOT NULL OR answer_key_value IS NULL),
  CHECK (evaluation NOT IN ('CORRECT', 'INCORRECT')
         OR (answer_key_status = 'VALID' AND answer_key_value IS NOT NULL)),
  CHECK (evaluation <> 'CORRECT' OR selected_label = answer_key_value),
  CHECK (evaluation <> 'INCORRECT' OR selected_label <> answer_key_value),
  CHECK (evaluation <> 'ANNULLED' OR answer_key_status = 'ANNULLED'),
  CHECK (evaluation <> 'NOT_VERIFIED'
         OR answer_key_status IS NULL
         OR answer_key_status = 'UNKNOWN'
         OR (answer_key_status = 'VALID' AND answer_key_value IS NULL))
) STRICT;

CREATE INDEX IF NOT EXISTS attempt_question_answered_at
  ON attempt (question_id, answered_at);

CREATE TRIGGER IF NOT EXISTS attempt_no_update BEFORE UPDATE ON attempt
BEGIN SELECT RAISE(ABORT, 'attempt é append-only'); END;

CREATE TRIGGER IF NOT EXISTS attempt_no_delete BEFORE DELETE ON attempt
BEGIN SELECT RAISE(ABORT, 'attempt é append-only'); END;
`;

const EVALUATIONS = [
  "CORRECT",
  "INCORRECT",
  "NOT_VERIFIED",
  "ANNULLED",
] as const;

/** Espelho tipado da DDL para consultas com drizzle-orm. */
export const attempt = sqliteTable("attempt", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  submission_id: text("submission_id").notNull().unique(),
  question_id: text("question_id").notNull(),
  question_file_sha256: text("question_file_sha256").notNull(),
  question_format: text("question_format").notNull(),
  area: text("area").notNull(),
  area_code: text("area_code", { enum: AREA_CODES }),
  selected_label: text("selected_label", {
    enum: ALTERNATIVE_LABELS,
  }).notNull(),
  evaluation: text("evaluation", { enum: EVALUATIONS }).notNull(),
  answer_key_status: text("answer_key_status", { enum: ANSWER_KEY_STATUSES }),
  answer_key_value: text("answer_key_value", { enum: ALTERNATIVE_LABELS }),
  answer_key_resource_id: text("answer_key_resource_id"),
  answer_key_resource_sha256: text("answer_key_resource_sha256"),
  content_resource_sha256: text("content_resource_sha256").notNull(),
  evaluation_rule_version: text("evaluation_rule_version").notNull(),
  answered_at: text("answered_at").notNull(),
  duration_ms: integer("duration_ms").notNull(),
});

/** Banco recusado (esquema desconhecido): nada é escrito. */
export class AttemptStoreError extends Error {}

function schemaObjectCount(sqlite: Database.Database): number {
  const row = sqlite
    .prepare(
      "SELECT count(*) AS n FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%'",
    )
    .get() as { n: number };
  return row.n;
}

/**
 * Confere a versão do esquema. `user_version = 0` em banco vazio cria o
 * esquema (somente se `writable`); `0` com objetos, ou versão diferente de 1,
 * é recusado sem escrita.
 */
function ensureSchema(sqlite: Database.Database, writable: boolean): boolean {
  const version = sqlite.pragma("user_version", { simple: true }) as number;
  if (version === ATTEMPT_SCHEMA_VERSION) return true;
  if (version !== 0) {
    throw new AttemptStoreError(
      `banco de tentativas com versão de esquema desconhecida (${version})`,
    );
  }
  if (schemaObjectCount(sqlite) > 0) {
    throw new AttemptStoreError(
      "banco de tentativas não vazio sem versão de esquema",
    );
  }
  if (!writable) return false;
  sqlite.transaction(() => {
    sqlite.exec(ATTEMPT_DDL);
    sqlite.pragma(`user_version = ${ATTEMPT_SCHEMA_VERSION}`);
  })();
  return true;
}

export type InsertResult =
  | { status: "INSERTED"; attempt: StoredAttempt }
  | { status: "EXISTING"; attempt: StoredAttempt }
  | { status: "CONFLICT"; attempt: StoredAttempt };

export interface AttemptStore {
  findBySubmissionId(submissionId: string): StoredAttempt | undefined;
  /**
   * Insere em transação. Se o `submission_id` já existe (inclusive por envio
   * concorrente), não grava: EXISTING com payload igual, CONFLICT senão.
   */
  insertIdempotent(record: AttemptRecord): InsertResult;
  list(): StoredAttempt[];
  close(): void;
}

function storeFor(sqlite: Database.Database): AttemptStore {
  const db = drizzle(sqlite);
  const find = (submissionId: string) =>
    db
      .select()
      .from(attempt)
      .where(eq(attempt.submission_id, submissionId))
      .get();
  return {
    findBySubmissionId: find,
    insertIdempotent: (record) =>
      sqlite
        .transaction((): InsertResult => {
          const existing = find(record.submission_id);
          if (existing !== undefined) {
            return {
              status: samePayload(existing, record) ? "EXISTING" : "CONFLICT",
              attempt: existing,
            };
          }
          const inserted = db.insert(attempt).values(record).returning().get();
          return { status: "INSERTED", attempt: inserted };
        })
        .immediate(),
    list: () =>
      db
        .select()
        .from(attempt)
        .orderBy(desc(attempt.answered_at), desc(attempt.id))
        .all(),
    close: () => sqlite.close(),
  };
}

/**
 * Abre o banco para leitura e escrita, criando o arquivo e o esquema quando
 * necessário. Lança `AttemptStoreError` para esquema desconhecido.
 */
export function openAttemptStore(path: string): AttemptStore {
  const sqlite = new Database(path);
  try {
    sqlite.pragma("busy_timeout = 5000");
    ensureSchema(sqlite, true);
  } catch (error) {
    sqlite.close();
    throw error;
  }
  return storeFor(sqlite);
}

export type ReadAttemptsResult =
  | { status: "READY"; attempts: StoredAttempt[] }
  | { status: "REFUSED"; reason: string };

/**
 * Leitura somente leitura para /desempenho. Arquivo inexistente (ou banco
 * vazio ainda sem esquema) significa nenhuma tentativa; nada é criado.
 */
export function readAttempts(path: string): ReadAttemptsResult {
  if (!existsSync(path)) return { status: "READY", attempts: [] };
  let sqlite: Database.Database;
  try {
    sqlite = new Database(path, { readonly: true, fileMustExist: true });
  } catch (error) {
    return { status: "REFUSED", reason: (error as Error).message };
  }
  try {
    if (!ensureSchema(sqlite, false)) return { status: "READY", attempts: [] };
    return { status: "READY", attempts: storeFor(sqlite).list() };
  } catch (error) {
    return { status: "REFUSED", reason: (error as Error).message };
  } finally {
    sqlite.close();
  }
}
