import type { Metadata } from "next";
import { connection } from "next/server";
import {
  loadVerifiedQuestion,
  type ResourceCheck,
} from "../../lib/m2/provenance";
import {
  type CuratedQuestion,
  resourceIdsForRoles,
} from "../../domain/question";
import { AnswerForm } from "./answer-form";

export const metadata: Metadata = { title: "Questão — enem-rei" };

function Checks({ checks }: { checks: ResourceCheck[] }) {
  return (
    <ul className="mt-2 list-disc pl-6">
      {checks.map((check) => (
        <li key={check.resource_id}>
          <span className="font-mono break-all">{check.sha256}</span>:{" "}
          {check.ok ? "verificado" : check.problems.join("; ")}
        </li>
      ))}
    </ul>
  );
}

function SourceBlock({ question }: { question: CuratedQuestion }) {
  const { identification: id, extraction } = question;
  const confirmedAt = extraction.confirmation_recorded_at ?? null;
  const byId = new Map(question.resources.map((r) => [r.resource_id, r]));
  const rows = [
    {
      title: "Caderno (texto e posição)",
      roles: ["CONTENT", "PLACEMENT"] as const,
    },
    { title: "Gabarito", roles: ["ANSWER_KEY"] as const },
  ];
  return (
    <section
      aria-labelledby="fonte"
      className="mt-10 border-t border-slate-300 pt-6 text-sm"
    >
      <h2 id="fonte" className="text-lg font-semibold">
        Fonte
      </h2>
      <p className="mt-2">
        ENEM {id.edition_year}, {id.application}, Dia {id.day}, Caderno{" "}
        {id.booklet.number} {id.booklet.color}, questão {id.question_number}.
      </p>
      {rows.map(({ title, roles }) => {
        const evidence = question.evidence.filter((e) =>
          (roles as readonly string[]).includes(e.evidence_role),
        );
        const resourceIds = resourceIdsForRoles(question, roles);
        if (resourceIds.size === 0) return null;
        return (
          <div key={title} className="mt-4">
            <h3 className="font-semibold">{title}</h3>
            {[...resourceIds].map((resourceId) => {
              const resource = byId.get(resourceId);
              if (resource === undefined) return null;
              const pages = [
                ...new Set(
                  evidence
                    .filter((e) => e.locator.resource_id === resourceId)
                    .map((e) => e.locator.locator_value.page_index),
                ),
              ];
              return (
                <dl
                  key={resourceId}
                  className="mt-1 grid grid-cols-[auto_1fr] gap-x-3"
                >
                  <dt>URL oficial</dt>
                  <dd className="break-all">
                    <a className="underline" href={resource.source_url}>
                      {resource.source_url}
                    </a>
                  </dd>
                  <dt>SHA-256</dt>
                  <dd className="font-mono break-all">{resource.sha256}</dd>
                  <dt>Página física</dt>
                  <dd>
                    {pages
                      .map(
                        (page) =>
                          `índice zero-based ${page} (página ${page + 1} do PDF)`,
                      )
                      .join("; ")}
                  </dd>
                </dl>
              );
            })}
          </div>
        );
      })}
      <p className="mt-4">
        <strong>
          {confirmedAt
            ? "Transcrição assistida por LLM, conferida visualmente e confirmada pessoalmente pelo usuário."
            : "Transcrição assistida por LLM, conferida por comparação visual (não verificada pessoalmente pelo usuário)."}
        </strong>{" "}
        Método: {extraction.method}. Conferência: {extraction.verified_by}.
        Horário da conferência: {extraction.verified_at ?? "não registrado"}.
        {confirmedAt && ` Confirmação registrada em: ${confirmedAt}.`}
      </p>
    </section>
  );
}

export default async function QuestionPage() {
  // Página dinâmica: os dados reais só existem em tempo de execução.
  await connection();
  const result = await loadVerifiedQuestion(
    process.env.ENEM_M2_QUESTION_PATH,
    process.env.ENEM_M2_DATA_ROOT,
  );

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <h1 className="text-2xl font-semibold">Questão</h1>
      {result.status === "NOT_CONFIGURED" && (
        <p role="alert" className="mt-4">
          Questão não configurada. Defina ENEM_M2_QUESTION_PATH e
          ENEM_M2_DATA_ROOT.
        </p>
      )}
      {result.status === "INVALID_QUESTION_FILE" && (
        <div role="alert" className="mt-4">
          <p className="font-semibold">Arquivo da questão inválido.</p>
          <ul className="mt-2 list-disc pl-6">
            {result.errors.map((error) => (
              <li key={error}>{error}</li>
            ))}
          </ul>
        </div>
      )}
      {result.status === "PROVENANCE_ERROR" && (
        <div role="alert" className="mt-4">
          <p className="font-semibold">
            Erro de proveniência: a questão não pode ser exibida como
            verificada.
          </p>
          <Checks checks={result.checks} />
        </div>
      )}
      {result.status === "READY" && (
        <>
          <p className="mt-1 text-sm text-slate-600">
            {result.question.identification.area} · Questão{" "}
            {result.question.identification.question_number}
          </p>
          {result.verifiedAnswerKey === null && (
            <p
              role="alert"
              className="mt-4 rounded border border-amber-500 bg-amber-50 p-3"
            >
              Gabarito não verificado: a resposta não será corrigida.
            </p>
          )}
          <article className="mt-6 space-y-3">
            {result.question.content.base_text.map((paragraph, i) => (
              <p key={i}>{paragraph}</p>
            ))}
            <p className="text-right text-sm">
              {result.question.content.source_lines.map((line, i) => (
                <span key={i} className="block">
                  {line}
                </span>
              ))}
            </p>
            <p className="font-medium">{result.question.content.statement}</p>
          </article>
          <AnswerForm
            alternatives={result.question.content.alternatives}
            answerKey={result.verifiedAnswerKey}
          />
          <SourceBlock question={result.question} />
        </>
      )}
    </main>
  );
}
