/**
 * Server-side only. Verifica a proveniência das questões do M2/M3 contra o
 * SQLite de ingestão (SPEC-004; ADR-0002), que permanece a autoridade dos metadados de recurso.
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
  assessProvenance,
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

/** Chave do recurso referenciado: verificação única por (id, SHA-256, URL). */
export function resourceKey(reference: ResourceReference): string {
  return JSON.stringify([
    reference.resource_id,
    reference.sha256,
    reference.source_url,
  ]);
}

function failedCheck(
  reference: ResourceReference,
  problem: string,
): ResourceCheck {
  return {
    resource_id: reference.resource_id,
    sha256: reference.sha256,
    ok: false,
    problems: [problem],
  };
}

/**
 * Verifica cada recurso distinto UMA vez (mesma chamada = mesma requisição),
 * abrindo o SQLite de ingestão uma única vez, somente leitura. Sem cache entre
 * chamadas. Resultado indexado por `resourceKey`.
 */
export async function verifyResources(
  dataRoot: string,
  references: readonly ResourceReference[],
): Promise<Map<string, ResourceCheck>> {
  const distinct = new Map<string, ResourceReference>();
  for (const reference of references) {
    const key = resourceKey(reference);
    if (!distinct.has(key)) distinct.set(key, reference);
  }
  const checks = new Map<string, ResourceCheck>();
  if (distinct.size === 0) return checks;

  let db: Database.Database;
  try {
    db = new Database(join(dataRoot, "ingestion.db"), {
      readonly: true,
      fileMustExist: true,
    });
  } catch (error) {
    for (const [key, reference] of distinct) {
      checks.set(
        key,
        failedCheck(
          reference,
          `SQLite de ingestão indisponível: ${(error as Error).message}`,
        ),
      );
    }
    return checks;
  }
  try {
    for (const [key, reference] of distinct) {
      checks.set(key, await checkResource(db, dataRoot, reference));
    }
  } catch (error) {
    for (const [key, reference] of distinct) {
      checks.set(
        key,
        failedCheck(
          reference,
          `falha ao consultar SQLite: ${(error as Error).message}`,
        ),
      );
    }
  } finally {
    db.close();
  }
  return checks;
}

/** Verificações dos recursos de uma questão, na ordem de `resources`. */
export function checksFor(
  question: CuratedQuestion,
  verified: ReadonlyMap<string, ResourceCheck>,
): ResourceCheck[] {
  return question.resources.map(
    (resource) =>
      verified.get(resourceKey(resource)) ??
      failedCheck(resource, "recurso não verificado"),
  );
}

/** Recursos (por resource_id) cuja verificação falhou. */
export function failedResourceIds(checks: readonly ResourceCheck[]) {
  return new Set(checks.filter((c) => !c.ok).map((c) => c.resource_id));
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

  const checks = checksFor(
    question,
    await verifyResources(dataRoot, question.resources),
  );
  const assessment = assessProvenance(question, failedResourceIds(checks));
  if (assessment.blocked) return { status: "PROVENANCE_ERROR", checks };
  return {
    status: "READY",
    question,
    verifiedAnswerKey: assessment.verifiedAnswerKey,
    checks,
  };
}
