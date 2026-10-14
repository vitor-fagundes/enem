import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { connection } from "next/server";
import { neighbors } from "../../../domain/catalog";
import { loadCatalog, navigableEntries } from "../../../lib/m3/catalog";
import { Checks, QuestionView } from "../../questao/question-view";
import { CatalogUnavailable } from "../catalog-status";
import { AttemptForm } from "./attempt-form";

export const metadata: Metadata = { title: "Questão — enem-rei" };

export default async function CatalogQuestionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  // Página dinâmica: os dados reais só existem em tempo de execução.
  await connection();
  const { id } = await params;
  const result = await loadCatalog(
    process.env.ENEM_CATALOG_DIR,
    process.env.ENEM_DATA_ROOT,
  );
  if (result.status !== "READY") {
    return (
      <main className="mx-auto max-w-2xl px-6 py-12">
        <h1 className="text-2xl font-semibold">Questão</h1>
        <CatalogUnavailable result={result} />
      </main>
    );
  }
  const entry = result.entries.find((candidate) => candidate.id === id);
  if (entry === undefined) notFound();

  const catalogLink = (
    <Link className="underline" href="/questoes">
      Catálogo
    </Link>
  );

  if (entry.source === "BLOCKED") {
    return (
      <main className="mx-auto max-w-2xl px-6 py-12">
        <h1 className="text-2xl font-semibold">Questão</h1>
        <div role="alert" className="mt-4">
          <p className="font-semibold">
            Erro de proveniência: a questão não pode ser exibida como
            verificada.
          </p>
          <Checks checks={entry.checks} />
        </div>
        <p className="mt-6 text-sm">{catalogLink}</p>
      </main>
    );
  }

  const around = neighbors(navigableEntries(result.entries), entry.id);
  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <h1 className="text-2xl font-semibold">Questão</h1>
      <QuestionView
        question={entry.question}
        verifiedAnswerKey={entry.verifiedAnswerKey}
        form={
          // Sem gabarito: a correção ocorre no servidor, junto do registro (M4).
          <AttemptForm
            key={entry.id}
            alternatives={entry.question.content.alternatives}
            questionId={entry.id}
            questionFileSha256={entry.fileSha256}
          />
        }
      >
        <nav
          aria-label="Navegação entre questões"
          className="mt-8 flex justify-between gap-4 text-sm"
        >
          {around?.previous ? (
            <Link
              className="underline"
              href={`/questoes/${around.previous.id}`}
            >
              Anterior: questão{" "}
              {around.previous.question.identification.question_number}
            </Link>
          ) : (
            <span aria-hidden="true" />
          )}
          {catalogLink}
          {around?.next ? (
            <Link className="underline" href={`/questoes/${around.next.id}`}>
              Próxima: questão{" "}
              {around.next.question.identification.question_number}
            </Link>
          ) : (
            <span aria-hidden="true" />
          )}
        </nav>
      </QuestionView>
    </main>
  );
}
