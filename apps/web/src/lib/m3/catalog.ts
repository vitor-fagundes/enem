/**
 * Server-side only. Carrega o catálogo do M3 (docs/m3-catalogo-questoes.md) a
 * partir de um diretório de arquivos JSON curados e verifica a proveniência
 * com as mesmas funções do M2 (ADR-0002): cada recurso distinto é verificado
 * uma única vez por chamada, sem cache entre requisições.
 */
import { createHash } from "node:crypto";
import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import {
  type CatalogFile,
  type CatalogWarning,
  isCatalogFileName,
  selectCatalogEntries,
} from "../../domain/catalog";
import {
  type AnswerKey,
  type CuratedQuestion,
  assessProvenance,
} from "../../domain/question";
import {
  type ResourceCheck,
  checksFor,
  failedResourceIds,
  verifyResources,
} from "../m2/provenance";

/**
 * VERIFIED: fonte e gabarito verificados; KEY_UNVERIFIED: questão exibida sem
 * correção; BLOCKED: recurso do caderno falhou, a questão não é exibida.
 */
export type SourceState = "VERIFIED" | "KEY_UNVERIFIED" | "BLOCKED";

export interface CatalogEntry {
  id: string;
  fileName: string;
  /** SHA-256 dos bytes do arquivo curado lido nesta chamada (versão da questão). */
  fileSha256: string;
  question: CuratedQuestion;
  source: SourceState;
  /** `null` quando o gabarito não foi verificado ou a questão está bloqueada. */
  verifiedAnswerKey: AnswerKey | null;
  checks: ResourceCheck[];
}

export type CatalogLoadResult =
  | { status: "NOT_CONFIGURED" }
  | { status: "CATALOG_UNREADABLE"; error: string }
  | { status: "READY"; entries: CatalogEntry[]; warnings: CatalogWarning[] };

/**
 * Lê somente arquivos regulares `*.json` (sem seguir links simbólicos) e
 * calcula o SHA-256 dos bytes lidos de cada um.
 */
export async function readCatalogFiles(catalogDir: string): Promise<{
  files: CatalogFile[];
  sha256ByFile: Map<string, string>;
  warnings: CatalogWarning[];
}> {
  const dirents = await readdir(catalogDir, { withFileTypes: true });
  const files: CatalogFile[] = [];
  const sha256ByFile = new Map<string, string>();
  const warnings: CatalogWarning[] = [];
  for (const dirent of dirents) {
    if (!dirent.isFile() || !isCatalogFileName(dirent.name)) continue;
    try {
      const bytes = await readFile(join(catalogDir, dirent.name));
      files.push({ fileName: dirent.name, content: bytes.toString("utf8") });
      sha256ByFile.set(
        dirent.name,
        createHash("sha256").update(bytes).digest("hex"),
      );
    } catch {
      warnings.push({ fileName: dirent.name, reasons: ["arquivo ilegível"] });
    }
  }
  return { files, sha256ByFile, warnings };
}

export async function loadCatalog(
  catalogDir: string | undefined,
  dataRoot: string | undefined,
): Promise<CatalogLoadResult> {
  if (!catalogDir || !dataRoot) return { status: "NOT_CONFIGURED" };

  let read: Awaited<ReturnType<typeof readCatalogFiles>>;
  try {
    read = await readCatalogFiles(catalogDir);
  } catch (error) {
    return {
      status: "CATALOG_UNREADABLE",
      error: (error as NodeJS.ErrnoException).code ?? "erro de leitura",
    };
  }
  const selection = selectCatalogEntries(read.files);
  const warnings = [...read.warnings, ...selection.warnings].sort((a, b) =>
    a.fileName < b.fileName ? -1 : a.fileName > b.fileName ? 1 : 0,
  );

  const verified = await verifyResources(
    dataRoot,
    selection.entries.flatMap((entry) => entry.question.resources),
  );
  const entries = selection.entries.map((candidate): CatalogEntry => {
    const checks = checksFor(candidate.question, verified);
    const assessment = assessProvenance(
      candidate.question,
      failedResourceIds(checks),
    );
    return {
      ...candidate,
      fileSha256: read.sha256ByFile.get(candidate.fileName)!,
      checks,
      source: assessment.blocked
        ? "BLOCKED"
        : assessment.verifiedAnswerKey === null
          ? "KEY_UNVERIFIED"
          : "VERIFIED",
      verifiedAnswerKey: assessment.blocked
        ? null
        : assessment.verifiedAnswerKey,
    };
  });
  return { status: "READY", entries, warnings };
}

/** Questões navegáveis: as bloqueadas por proveniência ficam sem link. */
export function navigableEntries(entries: readonly CatalogEntry[]) {
  return entries.filter((entry) => entry.source !== "BLOCKED");
}
