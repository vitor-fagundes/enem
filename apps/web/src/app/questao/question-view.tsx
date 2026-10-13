import type { ReactNode } from "react";
import type { ResourceCheck } from "../../lib/m2/provenance";
import {
  type AnswerKey,
  type CuratedQuestion,
  resourceIdsForRoles,
} from "../../domain/question";
import { AnswerForm } from "./answer-form";

/**
 * Corpo da questão e bloco de proveniência compartilhados por /questao (M2) e
 * /questoes/[id] (M3).
 */
export function Checks({ checks }: { checks: ResourceCheck[] }) {
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

export function SourceBlock({ question }: { question: CuratedQuestion }) {
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

export function QuestionView({
  question,
  verifiedAnswerKey,
  formKey,
  children,
}: {
  question: CuratedQuestion;
  verifiedAnswerKey: AnswerKey | null;
  /** Chave do formulário: trocar de questão descarta a resposta. */
  formKey?: string;
  /** Conteúdo exibido entre o formulário e o bloco de fonte. */
  children?: ReactNode;
}) {
  return (
    <>
      <p className="mt-1 text-sm text-slate-600">
        {question.identification.area} · Questão{" "}
        {question.identification.question_number}
      </p>
      {verifiedAnswerKey === null && (
        <p
          role="alert"
          className="mt-4 rounded border border-amber-500 bg-amber-50 p-3"
        >
          Gabarito não verificado: a resposta não será corrigida.
        </p>
      )}
      <article className="mt-6 space-y-3">
        {question.content.base_text.map((paragraph, i) => (
          <p key={i}>{paragraph}</p>
        ))}
        <p className="text-right text-sm">
          {question.content.source_lines.map((line, i) => (
            <span key={i} className="block">
              {line}
            </span>
          ))}
        </p>
        <p className="font-medium">{question.content.statement}</p>
      </article>
      <AnswerForm
        key={formKey}
        alternatives={question.content.alternatives}
        answerKey={verifiedAnswerKey}
      />
      {children}
      <SourceBlock question={question} />
    </>
  );
}
