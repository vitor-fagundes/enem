/**
 * Indicadores de /desempenho (docs/m4-registro-tentativas.md, Decisões >
 * Indicadores), calculados de forma determinística sobre todas as tentativas
 * registradas, inclusive repetições. A taxa de acerto é um indicador simples,
 * não domínio/mastery (SPEC-001 FR-018). Funções puras, sem I/O.
 */
import { AREA_CODES, AREA_NAMES, type AreaCode } from "./area";
import type { AnswerEvaluation } from "./question";

export interface AttemptForStats {
  evaluation: AnswerEvaluation;
  area: string;
  area_code: AreaCode | null;
}

export interface PerformanceStats {
  total: number;
  correct: number;
  incorrect: number;
  /** NOT_VERIFIED + ANNULLED: nunca contam como acerto nem erro. */
  notCorrected: number;
  /** acertos / (acertos + erros); `null` quando o denominador é 0. */
  rate: number | null;
}

export interface AreaPerformance {
  /** Código canônico ou `null` para área não mapeada. */
  code: AreaCode | null;
  /** Nome oficial (áreas mapeadas) ou texto observado (não mapeadas). */
  label: string;
  stats: PerformanceStats;
}

export interface PerformanceSummary {
  overall: PerformanceStats;
  byArea: AreaPerformance[];
}

export function computeStats(
  attempts: readonly AttemptForStats[],
): PerformanceStats {
  let correct = 0;
  let incorrect = 0;
  for (const attempt of attempts) {
    if (attempt.evaluation === "CORRECT") correct++;
    else if (attempt.evaluation === "INCORRECT") incorrect++;
  }
  const graded = correct + incorrect;
  return {
    total: attempts.length,
    correct,
    incorrect,
    notCorrected: attempts.length - graded,
    rate: graded === 0 ? null : correct / graded,
  };
}

/**
 * Totais e divisão por área: LC, CH, CN, MT nessa ordem (mesmo sem
 * tentativas) e depois uma linha por texto de área não mapeada, em ordem
 * lexicográfica.
 */
export function summarizePerformance(
  attempts: readonly AttemptForStats[],
): PerformanceSummary {
  const mapped = AREA_CODES.map((code): AreaPerformance => ({
    code,
    label: AREA_NAMES[code],
    stats: computeStats(attempts.filter((a) => a.area_code === code)),
  }));
  const unmappedByText = new Map<string, AttemptForStats[]>();
  for (const attempt of attempts) {
    if (attempt.area_code !== null) continue;
    const group = unmappedByText.get(attempt.area) ?? [];
    group.push(attempt);
    unmappedByText.set(attempt.area, group);
  }
  const unmapped = [...unmappedByText.keys()]
    .sort((a, b) => (a < b ? -1 : a > b ? 1 : 0))
    .map((text): AreaPerformance => ({
      code: null,
      label: text,
      stats: computeStats(unmappedByText.get(text)!),
    }));
  return { overall: computeStats(attempts), byArea: [...mapped, ...unmapped] };
}

/** "66,7% (2/3)" ou "sem dados" quando não há acertos nem erros. */
export function formatRate(stats: PerformanceStats): string {
  if (stats.rate === null) return "sem dados";
  const percent = (stats.rate * 100).toFixed(1).replace(".", ",");
  return `${percent}% (${stats.correct}/${stats.correct + stats.incorrect})`;
}
