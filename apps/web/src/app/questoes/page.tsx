import type { Metadata } from "next";
import Link from "next/link";
import { connection } from "next/server";
import { loadCatalog } from "../../lib/m3/catalog";
import { CatalogUnavailable, SOURCE_STATE_TEXT } from "./catalog-status";

export const metadata: Metadata = { title: "Questões — enem-rei" };

export default async function CatalogPage() {
  // Página dinâmica: os dados reais só existem em tempo de execução.
  await connection();
  const result = await loadCatalog(
    process.env.ENEM_CATALOG_DIR,
    process.env.ENEM_DATA_ROOT,
  );

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <h1 className="text-2xl font-semibold">Questões</h1>
      {result.status !== "READY" && <CatalogUnavailable result={result} />}
      {result.status === "READY" && (
        <>
          {result.entries.length === 0 ? (
            <p className="mt-4">Nenhuma questão disponível no catálogo.</p>
          ) : (
            <ol aria-label="Catálogo" className="mt-6 space-y-2">
              {result.entries.map((entry) => {
                const { question_number, area } = entry.question.identification;
                return (
                  <li
                    key={entry.id}
                    data-testid="catalog-entry"
                    className="rounded border border-slate-300 p-3"
                  >
                    {entry.source === "BLOCKED" ? (
                      <span className="font-semibold">
                        Questão {question_number}
                      </span>
                    ) : (
                      <Link
                        className="font-semibold underline"
                        href={`/questoes/${entry.id}`}
                      >
                        Questão {question_number}
                      </Link>
                    )}
                    <span className="block text-sm">{area}</span>
                    <span className="block text-sm text-slate-600">
                      {SOURCE_STATE_TEXT[entry.source]}
                    </span>
                  </li>
                );
              })}
            </ol>
          )}
          {result.warnings.length > 0 && (
            <section
              aria-labelledby="avisos"
              className="mt-10 border-t border-slate-300 pt-6 text-sm"
            >
              <h2 id="avisos" className="text-lg font-semibold">
                Arquivos fora do catálogo
              </h2>
              <ul className="mt-2 list-disc pl-6">
                {result.warnings.map((warning) => (
                  <li key={warning.fileName} data-testid="catalog-warning">
                    <span className="font-mono break-all">
                      {warning.fileName}
                    </span>
                    : {warning.reasons.join("; ")}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
      <p className="mt-10 text-sm">
        <Link className="underline" href="/">
          Início
        </Link>
      </p>
    </main>
  );
}
