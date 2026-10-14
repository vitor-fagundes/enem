import { describe, expect, test } from "vitest";
import {
  EVALUATION_RULE_VERSION,
  MAX_DURATION_MS,
  attemptOutcome,
  buildAttemptRecord,
  samePayload,
  validateSubmission,
} from "../../src/domain/attempt";
import type { AnswerKey, CuratedQuestion } from "../../src/domain/question";

const SHA = (c: string) => c.repeat(64);
const SUBMISSION = {
  submission_id: "0f8b6a3e-2c1d-4e5f-9a7b-1c2d3e4f5a6b",
  question_id: "enem-1999-d9-cd9-q7",
  question_file_sha256: SHA("a"),
  selected_label: "B",
  duration_ms: 12_345,
} as const;

function question(
  overrides: {
    area?: string;
    answerKey?: AnswerKey | null;
    extraEvidence?: Array<[string, string]>;
    resources?: CuratedQuestion["resources"];
  } = {},
): CuratedQuestion {
  const evidence: Array<[string, string]> = [
    ["CONTENT", "booklet"],
    ["PLACEMENT", "booklet"],
    ["ANSWER_KEY", "key"],
    ...(overrides.extraEvidence ?? []),
  ];
  return {
    format: "enem-rei/m2-question/v1",
    identification: {
      edition_year: 1999,
      application: "Aplicação Fictícia",
      day: 9,
      booklet: { number: 9, color: "Cor Fictícia" },
      numbering_context: "COMMON",
      question_number: 7,
      area: overrides.area ?? "Matemática e suas Tecnologias",
    },
    resources: overrides.resources ?? [
      { resource_id: "booklet", sha256: SHA("b"), source_url: "u1" },
      { resource_id: "key", sha256: SHA("c"), source_url: "u2" },
      { resource_id: "other", sha256: SHA("d"), source_url: "u3" },
    ],
    content: {
      base_text: ["texto"],
      source_lines: ["fonte"],
      statement: "enunciado",
      alternatives: (["A", "B", "C", "D", "E"] as const).map((label) => ({
        label,
        text: label,
      })),
    },
    answer_key:
      overrides.answerKey === undefined
        ? { published_value: "B", status: "VALID" }
        : overrides.answerKey,
    evidence: evidence.map(([role, resource_id]) => ({
      locator: {
        resource_id,
        locator_type: "PDF_PAGE" as const,
        locator_value: { page_index: 0 },
      },
      evidence_role:
        role as CuratedQuestion["evidence"][number]["evidence_role"],
      notes: null,
    })),
    extraction: { method: "m", verified_by: "v", verified_at: null },
  };
}

const ANSWERED_AT = new Date("2026-10-14T12:34:56.789Z");

function build(
  q: CuratedQuestion,
  verifiedAnswerKey: AnswerKey | null,
  selected: string = "B",
) {
  const result = validateSubmission({
    ...SUBMISSION,
    selected_label: selected,
  });
  if (!result.ok) throw new Error(result.errors.join());
  return buildAttemptRecord({
    submission: result.submission,
    question: q,
    questionFileSha256: SHA("e"),
    verifiedAnswerKey,
    answeredAt: ANSWERED_AT,
  });
}

describe("validateSubmission", () => {
  test("accepts a well-formed submission and keeps only known fields", () => {
    const result = validateSubmission({
      ...SUBMISSION,
      evaluation: "CORRECT",
      answer_key: { published_value: "B", status: "VALID" },
      area: "MT",
      answered_at: "2000-01-01T00:00:00.000Z",
    });
    expect(result).toEqual({ ok: true, submission: SUBMISSION });
  });

  test("rejects non-objects", () => {
    for (const input of [null, undefined, "x", 1, []]) {
      expect(validateSubmission(input).ok).toBe(false);
    }
  });

  test.each([
    ["submission_id", "nao-e-uuid"],
    ["submission_id", SUBMISSION.submission_id.toUpperCase()],
    ["submission_id", "0f8b6a3e-2c1d-1e5f-9a7b-1c2d3e4f5a6b"],
    ["submission_id", undefined],
    ["question_id", ""],
    ["question_id", "   "],
    ["question_id", "x".repeat(201)],
    ["question_id", 7],
    ["question_file_sha256", SHA("A")],
    ["question_file_sha256", "abc"],
    ["selected_label", "F"],
    ["selected_label", "a"],
    ["selected_label", null],
  ])("rejects invalid %s (%j)", (field, value) => {
    const result = validateSubmission({ ...SUBMISSION, [field]: value });
    expect(result.ok).toBe(false);
  });

  test("duration_ms limits: 0 and 24 h accepted; outside, fractional or missing rejected", () => {
    for (const ok of [0, 1, MAX_DURATION_MS]) {
      expect(validateSubmission({ ...SUBMISSION, duration_ms: ok }).ok).toBe(
        true,
      );
    }
    for (const bad of [
      -1,
      MAX_DURATION_MS + 1,
      1.5,
      Number.NaN,
      Number.POSITIVE_INFINITY,
      "100",
      null,
      undefined,
    ]) {
      expect(
        validateSubmission({ ...SUBMISSION, duration_ms: bad }).ok,
        String(bad),
      ).toBe(false);
    }
    const { duration_ms: _omitted, ...missing } = SUBMISSION;
    void _omitted;
    expect(validateSubmission(missing).ok).toBe(false);
  });
});

describe("samePayload", () => {
  test("compares question, version, alternative and duration", () => {
    expect(samePayload(SUBMISSION, { ...SUBMISSION })).toBe(true);
    for (const change of [
      { question_id: "outra" },
      { question_file_sha256: SHA("f") },
      { selected_label: "C" as const },
      { duration_ms: 1 },
    ]) {
      expect(samePayload(SUBMISSION, { ...SUBMISSION, ...change })).toBe(false);
    }
  });
});

describe("buildAttemptRecord", () => {
  test("CORRECT with a verified VALID key records provenance and the rule version", () => {
    const q = question();
    const result = build(q, q.answer_key);
    expect(result).toEqual({
      ok: true,
      record: {
        submission_id: SUBMISSION.submission_id,
        question_id: SUBMISSION.question_id,
        question_file_sha256: SHA("e"),
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
        evaluation_rule_version: EVALUATION_RULE_VERSION,
        answered_at: "2026-10-14T12:34:56.789Z",
        duration_ms: 12_345,
      },
    });
    expect(EVALUATION_RULE_VERSION).toBe("evaluateAnswer/v1");
  });

  test("INCORRECT exposes the key in the outcome", () => {
    const q = question();
    const result = build(q, q.answer_key, "D");
    if (!result.ok) throw new Error(result.error);
    expect(result.record.evaluation).toBe("INCORRECT");
    expect(attemptOutcome(result.record)).toEqual({
      evaluation: "INCORRECT",
      selected_label: "D",
      answer_key_value: "B",
      answered_at: "2026-10-14T12:34:56.789Z",
    });
  });

  test("unverified key: NOT_VERIFIED and no answer key data", () => {
    const result = build(question(), null);
    if (!result.ok) throw new Error(result.error);
    expect(result.record).toMatchObject({
      evaluation: "NOT_VERIFIED",
      answer_key_status: null,
      answer_key_value: null,
      answer_key_resource_id: null,
      answer_key_resource_sha256: null,
    });
    expect(attemptOutcome(result.record).answer_key_value).toBeNull();
  });

  test("annulled key: ANNULLED, key provenance kept, nothing revealed", () => {
    const key: AnswerKey = { published_value: "C", status: "ANNULLED" };
    const result = build(question({ answerKey: key }), key);
    if (!result.ok) throw new Error(result.error);
    expect(result.record).toMatchObject({
      evaluation: "ANNULLED",
      answer_key_status: "ANNULLED",
      answer_key_resource_id: "key",
    });
    expect(attemptOutcome(result.record).answer_key_value).toBeNull();
  });

  test("unmapped area keeps the observed text with a null code", () => {
    const result = build(question({ area: "Área Fictícia" }), null);
    if (!result.ok) throw new Error(result.error);
    expect(result.record.area).toBe("Área Fictícia");
    expect(result.record.area_code).toBeNull();
  });

  test("rejects more than one distinct content or answer-key resource", () => {
    const q1 = question({ extraEvidence: [["PLACEMENT", "other"]] });
    expect(build(q1, q1.answer_key).ok).toBe(false);
    const q2 = question({ extraEvidence: [["ANSWER_KEY", "other"]] });
    expect(build(q2, q2.answer_key).ok).toBe(false);
    expect(build(q2, null).ok).toBe(false);
  });
});
