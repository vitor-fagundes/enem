import { describe, expect, test } from "vitest";
import {
  type CuratedQuestion,
  evaluateAnswer,
  validateQuestion,
} from "../../src/domain/question";

const SHA_A = "a".repeat(64);
const SHA_B = "b".repeat(64);

function syntheticQuestion(): CuratedQuestion {
  const locator = (resource_id: string, page_index: number) => ({
    resource_id,
    locator_type: "PDF_PAGE" as const,
    locator_value: { page_index },
  });
  return {
    format: "enem-rei/m2-question/v1",
    identification: {
      edition_year: 1999,
      application: "Aplicação Fictícia",
      day: 9,
      booklet: { number: 9, color: "Cor Fictícia" },
      numbering_context: "COMMON",
      question_number: 99,
      area: "Área Fictícia",
    },
    resources: [
      {
        resource_id: "r-caderno",
        sha256: SHA_A,
        source_url: "https://example.invalid/a",
      },
      {
        resource_id: "r-gabarito",
        sha256: SHA_B,
        source_url: "https://example.invalid/b",
      },
    ],
    content: {
      base_text: ["Parágrafo fictício."],
      source_lines: ["Fonte fictícia."],
      statement: "Enunciado fictício",
      alternatives: (["A", "B", "C", "D", "E"] as const).map((label) => ({
        label,
        text: `opção ${label}`,
      })),
    },
    answer_key: { published_value: "B", status: "VALID" },
    evidence: [
      {
        locator: locator("r-caderno", 1),
        evidence_role: "CONTENT",
        notes: null,
      },
      {
        locator: locator("r-caderno", 1),
        evidence_role: "PLACEMENT",
        notes: null,
      },
      {
        locator: locator("r-gabarito", 0),
        evidence_role: "ANSWER_KEY",
        notes: null,
      },
    ],
    extraction: {
      method: "fixture",
      verified_by: "fixture",
      verified_at: "2000-01-01T00:00:00Z",
    },
  };
}

describe("evaluateAnswer", () => {
  test("correct when the selection matches a valid published key", () => {
    expect(evaluateAnswer("B", { published_value: "B", status: "VALID" })).toBe(
      "CORRECT",
    );
  });
  test("incorrect when the selection differs from a valid published key", () => {
    expect(evaluateAnswer("A", { published_value: "B", status: "VALID" })).toBe(
      "INCORRECT",
    );
  });
  test("not verified without a verified key", () => {
    expect(evaluateAnswer("B", null)).toBe("NOT_VERIFIED");
  });
  test("not verified when status is UNKNOWN or value is missing", () => {
    expect(
      evaluateAnswer("B", { published_value: "B", status: "UNKNOWN" }),
    ).toBe("NOT_VERIFIED");
    expect(
      evaluateAnswer("B", { published_value: null, status: "VALID" }),
    ).toBe("NOT_VERIFIED");
  });
  test("annulled question is never corrected", () => {
    expect(
      evaluateAnswer("B", { published_value: "B", status: "ANNULLED" }),
    ).toBe("ANNULLED");
    expect(
      evaluateAnswer("A", { published_value: null, status: "ANNULLED" }),
    ).toBe("ANNULLED");
  });
});

describe("validateQuestion", () => {
  test("accepts a well-formed synthetic question", () => {
    expect(validateQuestion(syntheticQuestion())).toMatchObject({ ok: true });
  });

  test("accepts an unrecorded verification time (verified_at null)", () => {
    const question = syntheticQuestion();
    question.extraction.verified_at = null;
    expect(validateQuestion(question).ok).toBe(true);
  });

  test("accepts an optional confirmation_recorded_at (ISO, null or absent)", () => {
    const question = syntheticQuestion();
    question.extraction.confirmation_recorded_at = "2000-01-02T00:00:00Z";
    expect(validateQuestion(question).ok).toBe(true);
    question.extraction.confirmation_recorded_at = null;
    expect(validateQuestion(question).ok).toBe(true);
  });

  const rejections: [string, (q: CuratedQuestion) => void][] = [
    ["four alternatives", (q) => void q.content.alternatives.pop()],
    [
      "six alternatives",
      (q) => void q.content.alternatives.push({ label: "E", text: "extra" }),
    ],
    [
      "empty alternative text",
      (q) => void (q.content.alternatives[2]!.text = " "),
    ],
    [
      "labels out of order",
      (q) => {
        q.content.alternatives[0]!.label = "B";
        q.content.alternatives[1]!.label = "A";
      },
    ],
    [
      "negative page_index",
      (q) => void (q.evidence[0]!.locator.locator_value.page_index = -1),
    ],
    [
      "fractional page_index",
      (q) => void (q.evidence[0]!.locator.locator_value.page_index = 1.5),
    ],
    ["uppercase sha256", (q) => void (q.resources[0]!.sha256 = "A".repeat(64))],
    ["short sha256", (q) => void (q.resources[0]!.sha256 = "a".repeat(63))],
    [
      "unknown evidence role",
      (q) =>
        void ((q.evidence[0] as { evidence_role: string }).evidence_role =
          "OTHER"),
    ],
    [
      "unknown answer key status",
      (q) => void ((q.answer_key as { status: string }).status = "MAYBE"),
    ],
    [
      "unknown published value",
      (q) =>
        void ((q.answer_key as { published_value: string }).published_value =
          "F"),
    ],
    [
      "non PDF_PAGE locator",
      (q) =>
        void ((
          q.evidence[0]!.locator as { locator_type: string }
        ).locator_type = "DOCUMENT"),
    ],
    [
      "evidence for unlisted resource",
      (q) => void (q.evidence[0]!.locator.resource_id = "r-desconhecido"),
    ],
    ["missing PLACEMENT evidence", (q) => void q.evidence.splice(1, 1)],
    [
      "answer key without ANSWER_KEY evidence",
      (q) => void q.evidence.splice(2, 1),
    ],
    ["missing verified_by", (q) => void (q.extraction.verified_by = "")],
    ["invalid verified_at", (q) => void (q.extraction.verified_at = "ontem")],
    [
      "invalid confirmation_recorded_at",
      (q) => void (q.extraction.confirmation_recorded_at = "ontem"),
    ],
    ["empty statement", (q) => void (q.content.statement = "")],
    [
      "unknown numbering context",
      (q) =>
        void ((
          q.identification as { numbering_context: string }
        ).numbering_context = "X"),
    ],
    ["wrong format", (q) => void ((q as { format: string }).format = "v0")],
  ];
  test.each(rejections)("rejects %s", (_name, mutate) => {
    const question = syntheticQuestion();
    mutate(question);
    const result = validateQuestion(question);
    expect(result.ok).toBe(false);
  });

  test("rejects non-object input", () => {
    expect(validateQuestion(null).ok).toBe(false);
    expect(validateQuestion([]).ok).toBe(false);
  });

  test("accepts a null answer key without ANSWER_KEY evidence", () => {
    const question = syntheticQuestion();
    question.answer_key = null;
    question.evidence.splice(2, 1);
    expect(validateQuestion(question).ok).toBe(true);
  });
});
