/**
 * Regras do marco M3 (docs/m3-catalogo-questoes.md): seleção das questões
 * curadas que entram no catálogo, ordenação e navegação. Funções puras, sem
 * I/O; reutilizam a validação estrutural do M2.
 */
import { type CuratedQuestion, validateQuestion } from "./question";

/** O M3 só aceita questões do contexto de numeração comum (números ≥ 6). */
export const CATALOG_NUMBERING_CONTEXT = "COMMON";

/**
 * ID estável da ocorrência no caderno (QuestionPlacement, não Question da
 * SPEC-003): `enem-<ano>-d<dia>-cd<caderno>-q<N>`. `null` fora do contexto
 * COMMON, que o ID não distingue.
 */
export function placementId(
  identification: CuratedQuestion["identification"],
): string | null {
  if (identification.numbering_context !== CATALOG_NUMBERING_CONTEXT) {
    return null;
  }
  const { edition_year, day, booklet, question_number } = identification;
  return `enem-${edition_year}-d${day}-cd${booklet.number}-q${question_number}`;
}

/** Somente `*.json`; backups `.bak-*` são ignorados mesmo se terminarem em `.json`. */
export function isCatalogFileName(fileName: string): boolean {
  return fileName.endsWith(".json") && !fileName.includes(".bak-");
}

export interface CatalogFile {
  fileName: string;
  content: string;
}

export interface CatalogWarning {
  fileName: string;
  reasons: string[];
}

export interface CatalogCandidate {
  id: string;
  fileName: string;
  question: CuratedQuestion;
}

function hasRecordedConfirmation(question: CuratedQuestion): boolean {
  const recordedAt = question.extraction.confirmation_recorded_at;
  return typeof recordedAt === "string" && recordedAt.trim().length > 0;
}

function compareText(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

/** Ordem determinística: edição, dia, caderno e número da questão (numérico). */
export function compareCandidates(
  a: CatalogCandidate,
  b: CatalogCandidate,
): number {
  const x = a.question.identification;
  const y = b.question.identification;
  return (
    x.edition_year - y.edition_year ||
    x.day - y.day ||
    x.booklet.number - y.booklet.number ||
    x.question_number - y.question_number ||
    compareText(a.id, b.id)
  );
}

/**
 * Seleciona as entradas utilizáveis. Ficam fora, com aviso: JSON malformado,
 * estrutura inválida, contexto de numeração diferente de COMMON, posição
 * duplicada (todas as entradas conflitantes), confirmação humana não
 * registrada e nome de arquivo diferente de `<id>.json`.
 */
export function selectCatalogEntries(files: readonly CatalogFile[]): {
  entries: CatalogCandidate[];
  warnings: CatalogWarning[];
} {
  const warnings: CatalogWarning[] = [];
  const byId = new Map<string, CatalogCandidate[]>();

  for (const { fileName, content } of files) {
    let parsed: unknown;
    try {
      parsed = JSON.parse(content);
    } catch {
      // Mensagem genérica: o erro do parser pode ecoar trechos do arquivo.
      warnings.push({ fileName, reasons: ["JSON malformado"] });
      continue;
    }
    const validation = validateQuestion(parsed);
    if (!validation.ok) {
      warnings.push({ fileName, reasons: validation.errors });
      continue;
    }
    const question = validation.question;
    const id = placementId(question.identification);
    if (id === null) {
      warnings.push({
        fileName,
        reasons: [
          `contexto de numeração ${question.identification.numbering_context} não suportado no catálogo (somente ${CATALOG_NUMBERING_CONTEXT})`,
        ],
      });
      continue;
    }
    const group = byId.get(id) ?? [];
    group.push({ id, fileName, question });
    byId.set(id, group);
  }

  const entries: CatalogCandidate[] = [];
  for (const [id, group] of byId) {
    if (group.length > 1) {
      for (const candidate of group) {
        const others = group
          .filter((other) => other !== candidate)
          .map((other) => other.fileName)
          .sort();
        warnings.push({
          fileName: candidate.fileName,
          reasons: [
            `posição duplicada (${id}) também em: ${others.join(", ")}`,
          ],
        });
      }
      continue;
    }
    const candidate = group[0]!;
    const reasons: string[] = [];
    if (!hasRecordedConfirmation(candidate.question)) {
      reasons.push(
        "sem confirmação humana registrada (extraction.confirmation_recorded_at)",
      );
    }
    if (candidate.fileName !== `${id}.json`) {
      reasons.push(`nome do arquivo deve ser ${id}.json`);
    }
    if (reasons.length > 0) {
      warnings.push({ fileName: candidate.fileName, reasons });
    } else {
      entries.push(candidate);
    }
  }

  entries.sort(compareCandidates);
  warnings.sort((a, b) => compareText(a.fileName, b.fileName));
  return { entries, warnings };
}

/** Anterior e próxima na ordem dada; `null` nas bordas ou se `id` não existe. */
export function neighbors<T extends { id: string }>(
  ordered: readonly T[],
  id: string,
): { previous: T | null; next: T | null } | null {
  const index = ordered.findIndex((item) => item.id === id);
  if (index < 0) return null;
  return {
    previous: ordered[index - 1] ?? null,
    next: ordered[index + 1] ?? null,
  };
}
