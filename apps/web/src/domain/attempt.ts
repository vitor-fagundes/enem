/**
 * Regras do marco M4 (docs/m4-registro-tentativas.md; ADR-0003): validação do
 * envio de uma resposta do catálogo, comparação de payload para idempotência
 * e montagem do registro imutável da tentativa, corrigida com `evaluateAnswer`
 * e o gabarito verificado pela proveniência. Funções puras, sem I/O.
 */
import { type AreaCode, mapAreaCode } from "./area";
import {
  ALTERNATIVE_LABELS,
  type AlternativeLabel,
  type AnswerEvaluation,
  type AnswerKey,
  type AnswerKeyStatus,
  type CuratedQuestion,
  SHA256_PATTERN,
  evaluateAnswer,
  resourceIdsForRoles,
} from "./question";

/** Versão da regra de correção gravada em cada tentativa. */
export const EVALUATION_RULE_VERSION = "evaluateAnswer/v1";

/** Limite superior de `duration_ms` (24 h). */
export const MAX_DURATION_MS = 86_400_000;

/** UUID v4 em minúsculas, como gerado por `crypto.randomUUID()`. */
export const SUBMISSION_ID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

const MAX_QUESTION_ID_LENGTH = 200;

/** Dados aceitos do navegador; qualquer outro campo é ignorado. */
export interface AttemptSubmission {
  submission_id: string;
  question_id: string;
  question_file_sha256: string;
  selected_label: AlternativeLabel;
  duration_ms: number;
}

export type SubmissionValidation =
  { ok: true; submission: AttemptSubmission } | { ok: false; errors: string[] };

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Valida o envio. Resultado, gabarito, área e horário eventualmente enviados
 * pelo cliente não são lidos (o servidor os determina).
 */
export function validateSubmission(input: unknown): SubmissionValidation {
  if (!isObject(input)) return { ok: false, errors: ["envio não é objeto"] };
  const errors: string[] = [];
  const {
    submission_id,
    question_id,
    question_file_sha256,
    selected_label,
    duration_ms,
  } = input;
  if (
    typeof submission_id !== "string" ||
    !SUBMISSION_ID_PATTERN.test(submission_id)
  ) {
    errors.push("submission_id deve ser UUID v4 em minúsculas");
  }
  if (
    typeof question_id !== "string" ||
    question_id.trim().length === 0 ||
    question_id.length > MAX_QUESTION_ID_LENGTH
  ) {
    errors.push("question_id inválido");
  }
  if (
    typeof question_file_sha256 !== "string" ||
    !SHA256_PATTERN.test(question_file_sha256)
  ) {
    errors.push("question_file_sha256 deve ter 64 hex minúsculos");
  }
  if (
    typeof selected_label !== "string" ||
    !(ALTERNATIVE_LABELS as readonly string[]).includes(selected_label)
  ) {
    errors.push("selected_label deve ser uma alternativa de A a E");
  }
  if (
    typeof duration_ms !== "number" ||
    !Number.isSafeInteger(duration_ms) ||
    duration_ms < 0 ||
    duration_ms > MAX_DURATION_MS
  ) {
    errors.push(`duration_ms deve ser inteiro entre 0 e ${MAX_DURATION_MS}`);
  }
  if (errors.length > 0) return { ok: false, errors };
  return {
    ok: true,
    submission: {
      submission_id: submission_id as string,
      question_id: question_id as string,
      question_file_sha256: question_file_sha256 as string,
      selected_label: selected_label as AlternativeLabel,
      duration_ms: duration_ms as number,
    },
  };
}

type SubmissionPayload = Pick<
  AttemptSubmission,
  "question_id" | "question_file_sha256" | "selected_label" | "duration_ms"
>;

/** Reenvio idempotente: mesmo payload (sem contar o `submission_id`). */
export function samePayload(
  a: SubmissionPayload,
  b: SubmissionPayload,
): boolean {
  return (
    a.question_id === b.question_id &&
    a.question_file_sha256 === b.question_file_sha256 &&
    a.selected_label === b.selected_label &&
    a.duration_ms === b.duration_ms
  );
}

/** Linha da tabela `attempt` (sem o `id` gerado pelo banco). */
export interface AttemptRecord {
  submission_id: string;
  question_id: string;
  question_file_sha256: string;
  question_format: string;
  area: string;
  area_code: AreaCode | null;
  selected_label: AlternativeLabel;
  evaluation: AnswerEvaluation;
  answer_key_status: AnswerKeyStatus | null;
  answer_key_value: AlternativeLabel | null;
  answer_key_resource_id: string | null;
  answer_key_resource_sha256: string | null;
  content_resource_sha256: string;
  evaluation_rule_version: string;
  answered_at: string;
  duration_ms: number;
}

export interface StoredAttempt extends AttemptRecord {
  id: number;
}

export type BuildAttemptResult =
  { ok: true; record: AttemptRecord } | { ok: false; error: string };

/**
 * Monta o registro da tentativa. `verifiedAnswerKey` é o gabarito verificado
 * pela proveniência (`null` quando não verificado); `questionFileSha256` é o
 * SHA-256 dos bytes do arquivo curado lido pelo servidor. Rejeita questões
 * que citam mais de um recurso distinto para conteúdo/posição ou gabarito.
 */
export function buildAttemptRecord({
  submission,
  question,
  questionFileSha256,
  verifiedAnswerKey,
  answeredAt,
}: {
  submission: AttemptSubmission;
  question: CuratedQuestion;
  questionFileSha256: string;
  verifiedAnswerKey: AnswerKey | null;
  answeredAt: Date;
}): BuildAttemptResult {
  const resources = new Map(question.resources.map((r) => [r.resource_id, r]));
  const contentIds = [
    ...resourceIdsForRoles(question, ["CONTENT", "PLACEMENT"]),
  ];
  const keyIds = [...resourceIdsForRoles(question, ["ANSWER_KEY"])];
  if (contentIds.length !== 1) {
    return {
      ok: false,
      error: "a questão deve citar exatamente um recurso de conteúdo/posição",
    };
  }
  if (keyIds.length > 1) {
    return {
      ok: false,
      error: "a questão cita mais de um recurso de gabarito",
    };
  }
  const content = resources.get(contentIds[0]!);
  if (content === undefined) {
    return { ok: false, error: "recurso de conteúdo não listado" };
  }
  let answerKey: Pick<
    AttemptRecord,
    | "answer_key_status"
    | "answer_key_value"
    | "answer_key_resource_id"
    | "answer_key_resource_sha256"
  > = {
    answer_key_status: null,
    answer_key_value: null,
    answer_key_resource_id: null,
    answer_key_resource_sha256: null,
  };
  if (verifiedAnswerKey !== null) {
    const keyResource =
      keyIds.length === 1 ? resources.get(keyIds[0]!) : undefined;
    if (keyResource === undefined) {
      return { ok: false, error: "gabarito verificado sem recurso citado" };
    }
    answerKey = {
      answer_key_status: verifiedAnswerKey.status,
      answer_key_value: verifiedAnswerKey.published_value,
      answer_key_resource_id: keyResource.resource_id,
      answer_key_resource_sha256: keyResource.sha256,
    };
  }
  const area = question.identification.area;
  return {
    ok: true,
    record: {
      submission_id: submission.submission_id,
      question_id: submission.question_id,
      question_file_sha256: questionFileSha256,
      question_format: question.format,
      area,
      area_code: mapAreaCode(area),
      selected_label: submission.selected_label,
      evaluation: evaluateAnswer(submission.selected_label, verifiedAnswerKey),
      ...answerKey,
      content_resource_sha256: content.sha256,
      evaluation_rule_version: EVALUATION_RULE_VERSION,
      answered_at: answeredAt.toISOString(),
      duration_ms: submission.duration_ms,
    },
  };
}

/** O que volta ao navegador: o gabarito só para CORRECT/INCORRECT (FR-013). */
export interface AttemptOutcome {
  evaluation: AnswerEvaluation;
  selected_label: AlternativeLabel;
  answer_key_value: AlternativeLabel | null;
  answered_at: string;
}

export function attemptOutcome(record: AttemptRecord): AttemptOutcome {
  const graded =
    record.evaluation === "CORRECT" || record.evaluation === "INCORRECT";
  return {
    evaluation: record.evaluation,
    selected_label: record.selected_label,
    answer_key_value: graded ? record.answer_key_value : null,
    answered_at: record.answered_at,
  };
}
