/**
 * Server-side only. Registro de uma tentativa do catálogo
 * (docs/m4-registro-tentativas.md, Fluxo de envio): valida o envio, resolve o
 * banco de tentativas, trata a idempotência, recarrega o catálogo e a
 * proveniência (sem cache), confere a versão da questão, corrige no servidor
 * e grava a linha em uma transação. Qualquer rejeição não grava nada.
 */
import {
  type AttemptOutcome,
  attemptOutcome,
  buildAttemptRecord,
  samePayload,
  validateSubmission,
} from "../../domain/attempt";
import { loadCatalog } from "../m3/catalog";
import { type AttemptsEnv, resolveAttemptsDb } from "./config";
import { type AttemptStore, openAttemptStore } from "./store";

export interface RecordEnv extends AttemptsEnv {
  ENEM_CATALOG_DIR?: string | undefined;
}

export type RejectionCode =
  | "NOT_CONFIGURED"
  | "CONFIG_REFUSED"
  | "STORE_UNAVAILABLE"
  | "INVALID_SUBMISSION"
  | "IDEMPOTENCY_CONFLICT"
  | "CATALOG_UNAVAILABLE"
  | "QUESTION_NOT_FOUND"
  | "QUESTION_BLOCKED"
  | "VERSION_MISMATCH"
  | "AMBIGUOUS_PROVENANCE";

export type RecordAttemptResult =
  | { status: "RECORDED" | "ALREADY_RECORDED"; attempt: AttemptOutcome }
  | { status: "REJECTED"; code: RejectionCode; message: string };

function reject(code: RejectionCode, message: string): RecordAttemptResult {
  return { status: "REJECTED", code, message };
}

export async function recordAttempt(
  input: unknown,
  env: RecordEnv,
  now: () => Date = () => new Date(),
): Promise<RecordAttemptResult> {
  const validation = validateSubmission(input);
  if (!validation.ok) {
    return reject(
      "INVALID_SUBMISSION",
      `Envio inválido: ${validation.errors.join("; ")}.`,
    );
  }
  const submission = validation.submission;

  const config = await resolveAttemptsDb(env);
  if (config.status === "NOT_CONFIGURED") {
    return reject(
      "NOT_CONFIGURED",
      "Registro de tentativas não configurado. Defina ENEM_ATTEMPTS_DB.",
    );
  }
  if (config.status === "REFUSED") {
    return reject(
      "CONFIG_REFUSED",
      `Registro de tentativas recusado: ${config.reason}.`,
    );
  }

  let store: AttemptStore;
  try {
    store = openAttemptStore(config.path);
  } catch (error) {
    return reject(
      "STORE_UNAVAILABLE",
      `Banco de tentativas indisponível: ${(error as Error).message}.`,
    );
  }
  try {
    const existing = store.findBySubmissionId(submission.submission_id);
    if (existing !== undefined) {
      return samePayload(existing, submission)
        ? { status: "ALREADY_RECORDED", attempt: attemptOutcome(existing) }
        : reject(
            "IDEMPOTENCY_CONFLICT",
            "Envio repetido com conteúdo diferente: nada foi registrado.",
          );
    }

    const catalog = await loadCatalog(env.ENEM_CATALOG_DIR, env.ENEM_DATA_ROOT);
    if (catalog.status !== "READY") {
      return reject(
        "CATALOG_UNAVAILABLE",
        "Catálogo não configurado ou ilegível: nada foi registrado.",
      );
    }
    const entry = catalog.entries.find((e) => e.id === submission.question_id);
    if (entry === undefined) {
      return reject(
        "QUESTION_NOT_FOUND",
        "Questão inexistente ou fora do catálogo: nada foi registrado.",
      );
    }
    if (entry.source === "BLOCKED") {
      return reject(
        "QUESTION_BLOCKED",
        "Erro de proveniência: a questão está bloqueada e nada foi registrado.",
      );
    }
    if (entry.fileSha256 !== submission.question_file_sha256) {
      return reject(
        "VERSION_MISMATCH",
        "A questão foi alterada depois de exibida (versão divergente): nada foi registrado. Recarregue a página.",
      );
    }

    const built = buildAttemptRecord({
      submission,
      question: entry.question,
      questionFileSha256: entry.fileSha256,
      verifiedAnswerKey: entry.verifiedAnswerKey,
      answeredAt: now(),
    });
    if (!built.ok) {
      return reject(
        "AMBIGUOUS_PROVENANCE",
        `Proveniência não suportada: ${built.error}.`,
      );
    }

    const inserted = store.insertIdempotent(built.record);
    if (inserted.status === "CONFLICT") {
      return reject(
        "IDEMPOTENCY_CONFLICT",
        "Envio repetido com conteúdo diferente: nada foi registrado.",
      );
    }
    return {
      status: inserted.status === "INSERTED" ? "RECORDED" : "ALREADY_RECORDED",
      attempt: attemptOutcome(inserted.attempt),
    };
  } catch (error) {
    return reject(
      "STORE_UNAVAILABLE",
      `Falha ao registrar a tentativa: ${(error as Error).message}.`,
    );
  } finally {
    store.close();
  }
}
