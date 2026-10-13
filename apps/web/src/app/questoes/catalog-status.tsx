import type { CatalogLoadResult, SourceState } from "../../lib/m3/catalog";

export const SOURCE_STATE_TEXT: Record<SourceState, string> = {
  VERIFIED: "Fonte verificada",
  KEY_UNVERIFIED: "Fonte verificada; gabarito não verificado",
  BLOCKED: "Erro de proveniência: questão indisponível",
};

/** Estados do catálogo sem questões a exibir (não configurado ou ilegível). */
export function CatalogUnavailable({
  result,
}: {
  result: Exclude<CatalogLoadResult, { status: "READY" }>;
}) {
  return result.status === "NOT_CONFIGURED" ? (
    <p role="alert" className="mt-4">
      Catálogo não configurado. Defina ENEM_CATALOG_DIR e ENEM_DATA_ROOT.
    </p>
  ) : (
    <p role="alert" className="mt-4">
      Diretório do catálogo ilegível ({result.error}).
    </p>
  );
}
