import { describe, expect, test } from "vitest";
import {
  type AttemptForStats,
  computeStats,
  formatRate,
  summarizePerformance,
} from "../../src/domain/performance";

const a = (
  evaluation: AttemptForStats["evaluation"],
  area_code: AttemptForStats["area_code"],
  area = "texto",
): AttemptForStats => ({ evaluation, area_code, area });

describe("computeStats", () => {
  test("empty history has no data", () => {
    const stats = computeStats([]);
    expect(stats).toEqual({
      total: 0,
      correct: 0,
      incorrect: 0,
      notCorrected: 0,
      rate: null,
    });
    expect(formatRate(stats)).toBe("sem dados");
  });

  test("only uncorrected attempts never count as correct or incorrect", () => {
    const stats = computeStats([
      a("NOT_VERIFIED", "LC"),
      a("ANNULLED", "CH"),
      a("ANNULLED", "CH"),
    ]);
    expect(stats).toEqual({
      total: 3,
      correct: 0,
      incorrect: 0,
      notCorrected: 3,
      rate: null,
    });
    expect(formatRate(stats)).toBe("sem dados");
  });

  test("repetitions of the same question are all counted", () => {
    const stats = computeStats([
      a("CORRECT", "MT"),
      a("INCORRECT", "MT"),
      a("CORRECT", "MT"),
      a("NOT_VERIFIED", "MT"),
    ]);
    expect(stats.total).toBe(4);
    expect(stats.correct).toBe(2);
    expect(stats.incorrect).toBe(1);
    expect(stats.notCorrected).toBe(1);
    expect(stats.rate).toBeCloseTo(2 / 3);
    expect(formatRate(stats)).toBe("66,7% (2/3)");
  });

  test("formats the rate with one decimal place and the fraction", () => {
    expect(formatRate(computeStats([a("CORRECT", "LC")]))).toBe("100,0% (1/1)");
    expect(formatRate(computeStats([a("INCORRECT", "LC")]))).toBe("0,0% (0/1)");
    expect(
      formatRate(computeStats([a("CORRECT", "LC"), a("INCORRECT", "LC")])),
    ).toBe("50,0% (1/2)");
  });
});

describe("summarizePerformance", () => {
  test("empty history lists the four areas with no data", () => {
    const summary = summarizePerformance([]);
    expect(summary.byArea.map((row) => row.code)).toEqual([
      "LC",
      "CH",
      "CN",
      "MT",
    ]);
    for (const row of summary.byArea) expect(row.stats.rate).toBeNull();
  });

  test("mixes official areas and unmapped texts in a fixed order", () => {
    const summary = summarizePerformance([
      a("CORRECT", null, "Área Fictícia Zeta"),
      a("CORRECT", "MT"),
      a("INCORRECT", "LC"),
      a("CORRECT", "LC"),
      a("ANNULLED", "CH"),
      a("INCORRECT", null, "Área Fictícia Alfa"),
      a("NOT_VERIFIED", null, "Área Fictícia Zeta"),
    ]);
    expect(summary.overall).toEqual({
      total: 7,
      correct: 3,
      incorrect: 2,
      notCorrected: 2,
      rate: 3 / 5,
    });
    expect(
      summary.byArea.map((row) => [row.code, row.label, row.stats.total]),
    ).toEqual([
      ["LC", "Linguagens, Códigos e suas Tecnologias", 2],
      ["CH", "Ciências Humanas e suas Tecnologias", 1],
      ["CN", "Ciências da Natureza e suas Tecnologias", 0],
      ["MT", "Matemática e suas Tecnologias", 1],
      [null, "Área Fictícia Alfa", 1],
      [null, "Área Fictícia Zeta", 2],
    ]);
    const byLabel = new Map(summary.byArea.map((r) => [r.label, r.stats]));
    expect(
      formatRate(byLabel.get("Linguagens, Códigos e suas Tecnologias")!),
    ).toBe("50,0% (1/2)");
    expect(
      formatRate(byLabel.get("Ciências Humanas e suas Tecnologias")!),
    ).toBe("sem dados");
    expect(byLabel.get("Área Fictícia Zeta")).toEqual({
      total: 2,
      correct: 1,
      incorrect: 0,
      notCorrected: 1,
      rate: 1,
    });
  });
});
