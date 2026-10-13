import { describe, expect, test } from "vitest";
import {
  type CatalogFile,
  isCatalogFileName,
  neighbors,
  placementId,
  selectCatalogEntries,
} from "../../src/domain/catalog";
import {
  type CuratedQuestion,
  assessProvenance,
} from "../../src/domain/question";

// Somente dados sintéticos e textos claramente fictícios.
function syntheticQuestion(
  number: number,
  overrides: {
    confirmation?: string | null;
    context?: CuratedQuestion["identification"]["numbering_context"];
  } = {},
): CuratedQuestion {
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
      numbering_context: overrides.context ?? "COMMON",
      question_number: number,
      area: "Área Fictícia",
    },
    resources: [
      {
        resource_id: "r-caderno",
        sha256: "a".repeat(64),
        source_url: "https://example.invalid/a",
      },
      {
        resource_id: "r-gabarito",
        sha256: "b".repeat(64),
        source_url: "https://example.invalid/b",
      },
    ],
    content: {
      base_text: ["Parágrafo fictício."],
      source_lines: ["Fonte fictícia."],
      statement: `Enunciado fictício ${number}`,
      alternatives: (["A", "B", "C", "D", "E"] as const).map((label) => ({
        label,
        text: `opção fictícia ${label}`,
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
      verified_at: null,
      ...(overrides.confirmation !== undefined
        ? { confirmation_recorded_at: overrides.confirmation }
        : { confirmation_recorded_at: "2000-01-02T00:00:00Z" }),
    },
  };
}

const idOf = (n: number) => `enem-1999-d9-cd9-q${n}`;

function file(
  number: number,
  fileName = `${idOf(number)}.json`,
  overrides: Parameters<typeof syntheticQuestion>[1] = {},
): CatalogFile {
  return {
    fileName,
    content: JSON.stringify(syntheticQuestion(number, overrides)),
  };
}

describe("placementId", () => {
  test("derives enem-<ano>-d<dia>-cd<caderno>-q<N> from identification", () => {
    const question = syntheticQuestion(10);
    expect(placementId(question.identification)).toBe("enem-1999-d9-cd9-q10");
    question.identification.edition_year = 2024;
    question.identification.day = 1;
    question.identification.booklet.number = 1;
    expect(placementId(question.identification)).toBe("enem-2024-d1-cd1-q10");
  });

  test("is null outside the COMMON numbering context", () => {
    for (const context of ["ENGLISH", "SPANISH", "UNKNOWN"] as const) {
      expect(
        placementId(syntheticQuestion(3, { context }).identification),
      ).toBeNull();
    }
  });
});

describe("isCatalogFileName", () => {
  test("accepts *.json and ignores backups and other extensions", () => {
    expect(isCatalogFileName("enem-1999-d9-cd9-q7.json")).toBe(true);
    expect(isCatalogFileName("qualquer.json")).toBe(true);
    expect(
      isCatalogFileName("enem-1999-d9-cd9-q7.json.bak-20000101T000000Z"),
    ).toBe(false);
    expect(isCatalogFileName("enem-1999-d9-cd9-q7.bak-1.json")).toBe(false);
    expect(isCatalogFileName("notas.txt")).toBe(false);
    expect(isCatalogFileName("questao.JSON")).toBe(false);
    expect(isCatalogFileName("json")).toBe(false);
  });
});

describe("selectCatalogEntries", () => {
  test("accepts valid, confirmed entries named after their ID", () => {
    const { entries, warnings } = selectCatalogEntries([file(7), file(12)]);
    expect(entries.map((e) => e.id)).toEqual([idOf(7), idOf(12)]);
    expect(warnings).toEqual([]);
  });

  test("sorts numerically, not lexicographically", () => {
    const { entries } = selectCatalogEntries([file(54), file(10), file(9)]);
    expect(
      entries.map((e) => e.question.identification.question_number),
    ).toEqual([9, 10, 54]);
  });

  test("ordering does not depend on directory order", () => {
    const files = [file(30), file(7), file(12)];
    const a = selectCatalogEntries(files).entries.map((e) => e.id);
    const b = selectCatalogEntries([...files].reverse()).entries.map(
      (e) => e.id,
    );
    expect(a).toEqual(b);
  });

  test("requires a recorded human confirmation", () => {
    for (const confirmation of [null]) {
      const { entries, warnings } = selectCatalogEntries([
        file(7, undefined, { confirmation }),
        file(12),
      ]);
      expect(entries.map((e) => e.id)).toEqual([idOf(12)]);
      expect(warnings).toHaveLength(1);
      expect(warnings[0]!.fileName).toBe(`${idOf(7)}.json`);
      expect(warnings[0]!.reasons.join()).toMatch(/confirmação humana/);
    }
    const missing = syntheticQuestion(7);
    delete missing.extraction.confirmation_recorded_at;
    const result = selectCatalogEntries([
      { fileName: `${idOf(7)}.json`, content: JSON.stringify(missing) },
    ]);
    expect(result.entries).toEqual([]);
    expect(result.warnings[0]!.reasons.join()).toMatch(/confirmação humana/);
  });

  test("requires the file name to equal <id>.json", () => {
    const { entries, warnings } = selectCatalogEntries([
      file(7, "outro-nome.json"),
      file(12, `${idOf(13)}.json`),
    ]);
    expect(entries).toEqual([]);
    expect(warnings.map((w) => w.reasons)).toEqual([
      [`nome do arquivo deve ser ${idOf(12)}.json`],
      [`nome do arquivo deve ser ${idOf(7)}.json`],
    ]);
  });

  test("malformed JSON is excluded with a generic warning", () => {
    const { entries, warnings } = selectCatalogEntries([
      { fileName: "quebrado.json", content: "{ texto fictício" },
      file(7),
    ]);
    expect(entries.map((e) => e.id)).toEqual([idOf(7)]);
    expect(warnings).toEqual([
      { fileName: "quebrado.json", reasons: ["JSON malformado"] },
    ]);
  });

  test("structurally invalid files are excluded with validation errors", () => {
    const invalid = syntheticQuestion(7);
    invalid.content.alternatives.pop();
    const { entries, warnings } = selectCatalogEntries([
      { fileName: `${idOf(7)}.json`, content: JSON.stringify(invalid) },
      { fileName: "lista.json", content: "[]" },
    ]);
    expect(entries).toEqual([]);
    expect(warnings.map((w) => w.fileName)).toEqual([
      `${idOf(7)}.json`,
      "lista.json",
    ]);
    expect(warnings[0]!.reasons).toContain(
      "alternatives deve ter exatamente A–E, em ordem, com texto",
    );
  });

  test("non-COMMON numbering context is excluded with a warning", () => {
    const { entries, warnings } = selectCatalogEntries([
      file(3, undefined, { context: "UNKNOWN" }),
    ]);
    expect(entries).toEqual([]);
    expect(warnings[0]!.reasons.join()).toMatch(/somente COMMON/);
  });

  test("duplicated position excludes every conflicting entry", () => {
    const { entries, warnings } = selectCatalogEntries([
      file(50),
      file(50, "copia.json"),
      file(50, "outra-copia.json", { confirmation: null }),
      file(7),
    ]);
    expect(entries.map((e) => e.id)).toEqual([idOf(7)]);
    expect(warnings.map((w) => w.fileName)).toEqual([
      "copia.json",
      `${idOf(50)}.json`,
      "outra-copia.json",
    ]);
    for (const warning of warnings) {
      expect(warning.reasons.join()).toMatch(
        new RegExp(`posição duplicada \\(${idOf(50)}\\)`),
      );
    }
  });

  test("an empty directory yields an empty catalog", () => {
    expect(selectCatalogEntries([])).toEqual({ entries: [], warnings: [] });
  });
});

describe("neighbors", () => {
  const list = [{ id: "q9" }, { id: "q10" }, { id: "q54" }];

  test("first has no previous and last has no next", () => {
    expect(neighbors(list, "q9")).toEqual({ previous: null, next: list[1] });
    expect(neighbors(list, "q10")).toEqual({
      previous: list[0],
      next: list[2],
    });
    expect(neighbors(list, "q54")).toEqual({ previous: list[1], next: null });
  });

  test("single entry has no neighbors; unknown id is null", () => {
    expect(neighbors([{ id: "q9" }], "q9")).toEqual({
      previous: null,
      next: null,
    });
    expect(neighbors(list, "q99")).toBeNull();
  });
});

describe("assessProvenance", () => {
  const question = syntheticQuestion(7);

  test("all resources verified exposes the answer key", () => {
    expect(assessProvenance(question, new Set())).toEqual({
      blocked: false,
      verifiedAnswerKey: { published_value: "B", status: "VALID" },
    });
  });

  test("booklet failure blocks the question", () => {
    expect(assessProvenance(question, new Set(["r-caderno"]))).toEqual({
      blocked: true,
    });
    expect(
      assessProvenance(question, new Set(["r-caderno", "r-gabarito"])),
    ).toEqual({ blocked: true });
  });

  test("answer key failure only removes the correction", () => {
    expect(assessProvenance(question, new Set(["r-gabarito"]))).toEqual({
      blocked: false,
      verifiedAnswerKey: null,
    });
  });

  test("failure of an unrelated resource does not affect the question", () => {
    expect(assessProvenance(question, new Set(["r-outro"]))).toEqual({
      blocked: false,
      verifiedAnswerKey: { published_value: "B", status: "VALID" },
    });
  });
});
