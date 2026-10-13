/**
 * Regras do marco M2 (docs/m2-primeira-questao.md): uma questão curada,
 * transcrita manualmente, que referencia recursos ingeridos (SPEC-004) por
 * SHA-256 e localizador PDF_PAGE, com evidências separadas por papel
 * (SPEC-003 FR-025). Funções puras, sem I/O.
 */

export const ALTERNATIVE_LABELS = ["A", "B", "C", "D", "E"] as const;
export type AlternativeLabel = (typeof ALTERNATIVE_LABELS)[number];

/** SPEC-003 FR-011. */
export const ANSWER_KEY_STATUSES = ["VALID", "ANNULLED", "UNKNOWN"] as const;
export type AnswerKeyStatus = (typeof ANSWER_KEY_STATUSES)[number];

/** contracts/evidence.md (SPEC-004). */
export const EVIDENCE_ROLES = [
  "CONTENT",
  "PLACEMENT",
  "ANSWER_KEY",
  "EXTERNAL_IDENTIFIER",
  "OFFICIAL_ASSOCIATION",
  "PUBLICATION_METADATA",
] as const;
export type EvidenceRole = (typeof EVIDENCE_ROLES)[number];

/** SPEC-003 FR-008 (conceitos mínimos de contexto de numeração). */
export const NUMBERING_CONTEXTS = [
  "COMMON",
  "ENGLISH",
  "SPANISH",
  "UNKNOWN",
] as const;
export type NumberingContext = (typeof NUMBERING_CONTEXTS)[number];

export const QUESTION_FILE_FORMAT = "enem-rei/m2-question/v1";

export interface AnswerKey {
  published_value: AlternativeLabel | null;
  status: AnswerKeyStatus;
}

/** contracts/locator.md; o M2 só usa localizador PDF_PAGE. */
export interface PdfPageLocator {
  resource_id: string;
  locator_type: "PDF_PAGE";
  locator_value: { page_index: number };
}

export interface EvidenceReference {
  locator: PdfPageLocator;
  evidence_role: EvidenceRole;
  notes: string | null;
}

export interface ResourceReference {
  resource_id: string;
  sha256: string;
  source_url: string;
}

export interface Alternative {
  label: AlternativeLabel;
  text: string;
}

export interface CuratedQuestion {
  format: typeof QUESTION_FILE_FORMAT;
  identification: {
    edition_year: number;
    application: string;
    day: number;
    booklet: { number: number; color: string };
    numbering_context: NumberingContext;
    question_number: number;
    area: string;
  };
  resources: ResourceReference[];
  content: {
    base_text: string[];
    source_lines: string[];
    statement: string;
    alternatives: Alternative[];
  };
  answer_key: AnswerKey | null;
  evidence: EvidenceReference[];
  /**
   * Proveniência da transcrição e de sua conferência. `verified_at = null`
   * quando o horário da conferência não foi registrado.
   * `confirmation_recorded_at` (opcional) é o horário em que a confirmação
   * pessoal declarada pelo usuário foi REGISTRADA, nunca o da conferência.
   */
  extraction: {
    method: string;
    verified_by: string;
    verified_at: string | null;
    confirmation_recorded_at?: string | null;
  };
}

export type AnswerEvaluation =
  "CORRECT" | "INCORRECT" | "NOT_VERIFIED" | "ANNULLED";

/**
 * Corrige a resposta. `answerKey = null` significa gabarito não verificado.
 * Só há correção com status VALID e valor publicado resolvido em A–E; anulada,
 * desconhecida ou sem valor nunca é corrigida como erro (SPEC-003 FR-011).
 */
export function evaluateAnswer(
  selected: AlternativeLabel,
  answerKey: AnswerKey | null,
): AnswerEvaluation {
  if (answerKey === null) return "NOT_VERIFIED";
  if (answerKey.status === "ANNULLED") return "ANNULLED";
  if (answerKey.status !== "VALID" || answerKey.published_value === null) {
    return "NOT_VERIFIED";
  }
  return selected === answerKey.published_value ? "CORRECT" : "INCORRECT";
}

export const SHA256_PATTERN = /^[0-9a-f]{64}$/;

export type ValidationResult =
  { ok: true; question: CuratedQuestion } | { ok: false; errors: string[] };

type Json = Record<string, unknown>;

function isObject(value: unknown): value is Json {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isNonEmptyStringArray(value: unknown): value is string[] {
  return (
    Array.isArray(value) && value.length > 0 && value.every(isNonEmptyString)
  );
}

function isPositiveInteger(value: unknown): value is number {
  return Number.isInteger(value) && (value as number) > 0;
}

function includes<T extends string>(list: readonly T[], value: unknown) {
  return (
    typeof value === "string" && (list as readonly string[]).includes(value)
  );
}

/** Validação estrutural do arquivo curado; não consulta recursos. */
export function validateQuestion(input: unknown): ValidationResult {
  const errors: string[] = [];
  if (!isObject(input)) return { ok: false, errors: ["raiz não é objeto"] };
  if (input.format !== QUESTION_FILE_FORMAT) {
    errors.push(`format deve ser "${QUESTION_FILE_FORMAT}"`);
  }

  const id = input.identification;
  if (!isObject(id)) {
    errors.push("identification ausente");
  } else {
    if (!isPositiveInteger(id.edition_year))
      errors.push("edition_year inválido");
    if (!isNonEmptyString(id.application)) errors.push("application inválida");
    if (!isPositiveInteger(id.day)) errors.push("day inválido");
    if (
      !isObject(id.booklet) ||
      !isPositiveInteger(id.booklet.number) ||
      !isNonEmptyString(id.booklet.color)
    ) {
      errors.push("booklet inválido");
    }
    if (!includes(NUMBERING_CONTEXTS, id.numbering_context)) {
      errors.push("numbering_context desconhecido");
    }
    if (!isPositiveInteger(id.question_number)) {
      errors.push("question_number inválido");
    }
    if (!isNonEmptyString(id.area)) errors.push("area inválida");
  }

  const resourceIds = new Set<string>();
  if (!Array.isArray(input.resources) || input.resources.length === 0) {
    errors.push("resources deve ser lista não vazia");
  } else {
    const hashes = new Set<string>();
    for (const [i, resource] of input.resources.entries()) {
      if (
        !isObject(resource) ||
        !isNonEmptyString(resource.resource_id) ||
        typeof resource.sha256 !== "string" ||
        !SHA256_PATTERN.test(resource.sha256) ||
        !isNonEmptyString(resource.source_url)
      ) {
        errors.push(
          `resources[${i}] exige resource_id, sha256 (64 hex minúsculos) e source_url`,
        );
        continue;
      }
      if (
        resourceIds.has(resource.resource_id) ||
        hashes.has(resource.sha256)
      ) {
        errors.push(`resources[${i}] duplicado`);
      }
      resourceIds.add(resource.resource_id);
      hashes.add(resource.sha256);
    }
  }

  const content = input.content;
  if (!isObject(content)) {
    errors.push("content ausente");
  } else {
    if (!isNonEmptyStringArray(content.base_text)) {
      errors.push("base_text deve ter parágrafos não vazios");
    }
    if (!isNonEmptyStringArray(content.source_lines)) {
      errors.push("source_lines deve ter linhas não vazias");
    }
    if (!isNonEmptyString(content.statement)) errors.push("statement vazio");
    const alternatives = content.alternatives;
    if (
      !Array.isArray(alternatives) ||
      alternatives.length !== ALTERNATIVE_LABELS.length ||
      !alternatives.every(
        (alternative, i) =>
          isObject(alternative) &&
          alternative.label === ALTERNATIVE_LABELS[i] &&
          isNonEmptyString(alternative.text),
      )
    ) {
      errors.push("alternatives deve ter exatamente A–E, em ordem, com texto");
    }
  }

  const key = input.answer_key;
  if (key !== null) {
    if (
      !isObject(key) ||
      !includes(ANSWER_KEY_STATUSES, key.status) ||
      !(
        key.published_value === null ||
        includes(ALTERNATIVE_LABELS, key.published_value)
      )
    ) {
      errors.push(
        "answer_key inválido (status ou published_value desconhecido)",
      );
    }
  }

  const roles = new Set<string>();
  if (!Array.isArray(input.evidence) || input.evidence.length === 0) {
    errors.push("evidence deve ser lista não vazia");
  } else {
    for (const [i, evidence] of input.evidence.entries()) {
      const locator = isObject(evidence) ? evidence.locator : undefined;
      const value = isObject(locator) ? locator.locator_value : undefined;
      if (
        !isObject(evidence) ||
        !includes(EVIDENCE_ROLES, evidence.evidence_role) ||
        !(evidence.notes === null || typeof evidence.notes === "string") ||
        !isObject(locator) ||
        locator.locator_type !== "PDF_PAGE" ||
        !isObject(value) ||
        !Number.isInteger(value.page_index) ||
        (value.page_index as number) < 0
      ) {
        errors.push(
          `evidence[${i}] exige papel conhecido, notes e locator PDF_PAGE com page_index inteiro ≥ 0`,
        );
        continue;
      }
      if (
        typeof locator.resource_id !== "string" ||
        !resourceIds.has(locator.resource_id)
      ) {
        errors.push(
          `evidence[${i}] referencia recurso não listado em resources`,
        );
      }
      roles.add(evidence.evidence_role as string);
    }
    for (const role of ["CONTENT", "PLACEMENT"]) {
      if (!roles.has(role)) errors.push(`evidência ${role} ausente`);
    }
    if (key !== null && !roles.has("ANSWER_KEY")) {
      errors.push("answer_key sem evidência ANSWER_KEY");
    }
  }

  const extraction = input.extraction;
  const isIsoOrNull = (value: unknown) =>
    value === null ||
    (typeof value === "string" && !Number.isNaN(Date.parse(value)));
  if (
    !isObject(extraction) ||
    !isNonEmptyString(extraction.method) ||
    !isNonEmptyString(extraction.verified_by) ||
    !isIsoOrNull(extraction.verified_at) ||
    !(
      extraction.confirmation_recorded_at === undefined ||
      isIsoOrNull(extraction.confirmation_recorded_at)
    )
  ) {
    errors.push(
      "extraction exige method, verified_by, verified_at (data ISO ou null) e confirmation_recorded_at opcional (data ISO ou null)",
    );
  }

  return errors.length === 0
    ? { ok: true, question: input as unknown as CuratedQuestion }
    : { ok: false, errors };
}

/** Recursos citados por evidências com algum dos papéis informados. */
export function resourceIdsForRoles(
  question: CuratedQuestion,
  roles: readonly EvidenceRole[],
): Set<string> {
  return new Set(
    question.evidence
      .filter((evidence) => roles.includes(evidence.evidence_role))
      .map((evidence) => evidence.locator.resource_id),
  );
}

export type ProvenanceAssessment =
  { blocked: true } | { blocked: false; verifiedAnswerKey: AnswerKey | null };

/**
 * Regra do M2 (reutilizada no M3) para classificar a questão a partir dos
 * recursos cuja verificação falhou: falha em recurso de conteúdo/posição
 * bloqueia a exibição; falha apenas em recurso do gabarito exibe a questão
 * sem correção (gabarito não verificado).
 */
export function assessProvenance(
  question: CuratedQuestion,
  failedResourceIds: ReadonlySet<string>,
): ProvenanceAssessment {
  const contentResources = resourceIdsForRoles(question, [
    "CONTENT",
    "PLACEMENT",
  ]);
  if ([...contentResources].some((id) => failedResourceIds.has(id))) {
    return { blocked: true };
  }
  const keyResources = resourceIdsForRoles(question, ["ANSWER_KEY"]);
  const keyVerified =
    question.answer_key !== null &&
    keyResources.size > 0 &&
    [...keyResources].every((id) => !failedResourceIds.has(id));
  return {
    blocked: false,
    verifiedAnswerKey: keyVerified ? question.answer_key : null,
  };
}
