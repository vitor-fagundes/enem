/**
 * Server-side only. Verifica a proveniência da questão do M2 contra o SQLite de
 * ingestão (SPEC-004), que permanece a autoridade dos metadados de recurso.
 * Abre o banco somente leitura e só lê os payloads; nunca escreve.
 */
import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { lstat, readFile } from "node:fs/promises";
import { join } from "node:path";
import Database from "better-sqlite3";
import {
  type AnswerKey,
  type CuratedQuestion,
  type ResourceReference,
  resourceIdsForRoles,
  validateQuestion,
} from "../../domain/question";

export interface ResourceCheck {
  resource_id: string;
  sha256: string;
  ok: boolean;
  /** Motivo da falha; vazio quando `ok`. */
  problems: string[];
}

export type QuestionLoadResult =
  | { status: "NOT_CONFIGURED" }
  | { status: "INVALID_QUESTION_FILE"; errors: string[] }
  | { status: "PROVENANCE_ERROR"; checks: ResourceCheck[] }
  | {
      status: "READY";
      question: CuratedQuestion;
      /** `null` quando o gabarito não pôde ser verificado. */
      verifiedAnswerKey: AnswerKey | null;
      checks: ResourceCheck[];
    };

export function expectedStorageLocator(sha256: string): string {
  return `raw/resources/${sha256}/payload`;
}

async function hashFile(
  path: string,
): Promise<{ sha256: string; size: number }> {
  const hash = createHash("sha256");
  let size = 0;
  for await (const chunk of createReadStream(path)) {
    hash.update(chunk as Buffer);
    size += (chunk as Buffer).length;
  }
  return { sha256: hash.digest("hex"), size };
}

interface SourceResourceRow {
  id: string;
  sha256: string;
  byte_size: number;
  storage_locator: string;
}

/** Confere um recurso referenciado contra SQLite e payload preservado. */
export async function checkResource(
  db: Database.Database,
  dataRoot: string,
  reference: ResourceReference,
): Promise<ResourceCheck> {
  const problems: string[] = [];
  const row = db
    .prepare(
      "SELECT id, sha256, byte_size, storage_locator FROM source_resource WHERE sha256 = ?",
    )
    .get(reference.sha256) as SourceResourceRow | undefined;
  if (row === undefined) {
    problems.push("SHA-256 não registrado em source_resource");
  } else {
    if (row.id !== reference.resource_id) {
      problems.push("resource_id diverge do registrado para o SHA-256");
    }
    const locator = expectedStorageLocator(reference.sha256);
    if (row.storage_locator !== locator) {
      problems.push(`storage_locator diverge de ${locator}`);
    }
    const acquisition = db
      .prepare(
        "SELECT 1 FROM resource_acquisition WHERE resource_id = ? AND source_url = ? LIMIT 1",
      )
      .get(row.id, reference.source_url);
    if (acquisition === undefined) {
      problems.push("nenhuma aquisição registrada com a URL referenciada");
    }
    if (row.storage_locator === locator) {
      const path = join(dataRoot, locator);
      try {
        const info = await lstat(path);
        if (!info.isFile()) {
          problems.push("payload não é arquivo regular");
        } else {
          const actual = await hashFile(path);
          if (actual.sha256 !== row.sha256) {
            problems.push("SHA-256 recalculado do payload diverge");
          }
          if (actual.size !== row.byte_size) {
            problems.push("tamanho do payload diverge de byte_size");
          }
        }
      } catch {
        problems.push("payload ausente ou ilegível");
      }
    }
  }
  return {
    resource_id: reference.resource_id,
    sha256: reference.sha256,
    ok: problems.length === 0,
    problems,
  };
}

/**
 * Carrega e verifica a questão. Falha em recurso de conteúdo/posição impede a
 * exibição; falha apenas em recurso do gabarito exibe a questão sem correção.
 */
export async function loadVerifiedQuestion(
  questionPath: string | undefined,
  dataRoot: string | undefined,
): Promise<QuestionLoadResult> {
  if (!questionPath || !dataRoot) return { status: "NOT_CONFIGURED" };

  let parsed: unknown;
  try {
    parsed = JSON.parse(await readFile(questionPath, "utf8"));
  } catch (error) {
    return {
      status: "INVALID_QUESTION_FILE",
      errors: [`arquivo da questão ilegível: ${(error as Error).message}`],
    };
  }
  const validation = validateQuestion(parsed);
  if (!validation.ok) {
    return { status: "INVALID_QUESTION_FILE", errors: validation.errors };
  }
  const question = validation.question;

  let db: Database.Database;
  try {
    db = new Database(join(dataRoot, "ingestion.db"), {
      readonly: true,
      fileMustExist: true,
    });
  } catch (error) {
    return {
      status: "PROVENANCE_ERROR",
      checks: question.resources.map((resource) => ({
        resource_id: resource.resource_id,
        sha256: resource.sha256,
        ok: false,
        problems: [
          `SQLite de ingestão indisponível: ${(error as Error).message}`,
        ],
      })),
    };
  }
  let checks: ResourceCheck[];
  try {
    checks = [];
    for (const resource of question.resources) {
      checks.push(await checkResource(db, dataRoot, resource));
    }
  } catch (error) {
    checks = question.resources.map((resource) => ({
      resource_id: resource.resource_id,
      sha256: resource.sha256,
      ok: false,
      problems: [`falha ao consultar SQLite: ${(error as Error).message}`],
    }));
  } finally {
    db.close();
  }

  const failed = new Set(checks.filter((c) => !c.ok).map((c) => c.resource_id));
  const contentResources = resourceIdsForRoles(question, [
    "CONTENT",
    "PLACEMENT",
  ]);
  if ([...contentResources].some((id) => failed.has(id))) {
    return { status: "PROVENANCE_ERROR", checks };
  }
  const keyResources = resourceIdsForRoles(question, ["ANSWER_KEY"]);
  const keyVerified =
    question.answer_key !== null &&
    keyResources.size > 0 &&
    [...keyResources].every((id) => !failed.has(id));
  return {
    status: "READY",
    question,
    verifiedAnswerKey: keyVerified ? question.answer_key : null,
    checks,
  };
}
