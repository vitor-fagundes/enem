"use client";

import { useEffect, useRef, useState } from "react";
import type { AttemptOutcome } from "../../../domain/attempt";
import type { Alternative, AlternativeLabel } from "../../../domain/question";
import { submitAttempt } from "./actions";

const RESULT_TEXT = {
  CORRECT: "Correto",
  INCORRECT: "Incorreto",
  NOT_VERIFIED: "Sem correção: gabarito não verificado.",
  ANNULLED: "Questão anulada: não há correção.",
} as const;

/**
 * Formulário do catálogo (M4): não recebe o gabarito. A correção e o registro
 * ocorrem no servidor; um `submission_id` por formulário montado. Após o
 * registro o formulário fica bloqueado; nova tentativa exige recarregar.
 */
export function AttemptForm({
  alternatives,
  questionId,
  questionFileSha256,
}: {
  alternatives: Alternative[];
  questionId: string;
  questionFileSha256: string;
}) {
  const [selected, setSelected] = useState<AlternativeLabel | null>(null);
  const [pending, setPending] = useState(false);
  const [outcome, setOutcome] = useState<AttemptOutcome | null>(null);
  const [error, setError] = useState<string | null>(null);
  const startedAt = useRef<number | null>(null);
  const submissionId = useRef<string | null>(null);
  const inFlight = useRef(false);

  useEffect(() => {
    startedAt.current = performance.now();
    submissionId.current = crypto.randomUUID();
  }, []);

  const locked = pending || outcome !== null;

  async function confirm() {
    if (
      selected === null ||
      inFlight.current ||
      outcome !== null ||
      startedAt.current === null ||
      submissionId.current === null
    ) {
      return;
    }
    inFlight.current = true;
    setPending(true);
    setError(null);
    try {
      const result = await submitAttempt({
        submission_id: submissionId.current,
        question_id: questionId,
        question_file_sha256: questionFileSha256,
        selected_label: selected,
        duration_ms: Math.round(performance.now() - startedAt.current),
      });
      if (result.status === "REJECTED") setError(result.message);
      else setOutcome(result.attempt);
    } catch {
      setError(
        "Falha de comunicação com o servidor: a resposta pode não ter sido registrada. Tente confirmar novamente.",
      );
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  }

  return (
    <form
      className="mt-6"
      onSubmit={(event) => {
        event.preventDefault();
        void confirm();
      }}
    >
      <fieldset disabled={locked}>
        <legend className="sr-only">Alternativas</legend>
        <ul className="space-y-2">
          {alternatives.map((alternative) => (
            <li key={alternative.label}>
              <label className="flex cursor-pointer gap-3 rounded border border-slate-300 p-3 has-[:checked]:border-slate-900 has-[:checked]:bg-slate-100">
                <input
                  type="radio"
                  name="alternative"
                  value={alternative.label}
                  checked={selected === alternative.label}
                  onChange={() => setSelected(alternative.label)}
                />
                <span className="font-semibold">{alternative.label}</span>{" "}
                <span>{alternative.text}</span>
              </label>
            </li>
          ))}
        </ul>
      </fieldset>
      <button
        type="submit"
        disabled={selected === null || locked}
        className="mt-4 rounded bg-slate-900 px-4 py-2 text-white disabled:cursor-not-allowed disabled:bg-slate-400"
      >
        {pending ? "Registrando…" : "Confirmar"}
      </button>
      {error !== null && (
        <p
          role="alert"
          data-testid="attempt-error"
          className="mt-4 rounded border border-red-500 bg-red-50 p-3"
        >
          {error}
        </p>
      )}
      {outcome !== null && (
        <div role="status" className="mt-4 rounded border border-slate-300 p-4">
          <p className="text-lg font-semibold" data-testid="answer-result">
            {RESULT_TEXT[outcome.evaluation]}
          </p>
          <p>Sua resposta: {outcome.selected_label}</p>
          {outcome.answer_key_value !== null && (
            <p>Gabarito oficial: {outcome.answer_key_value}</p>
          )}
          <p className="mt-2 text-sm text-slate-600">
            Tentativa registrada em {outcome.answered_at} (UTC).
          </p>
          <button
            type="button"
            className="mt-2 text-sm underline"
            onClick={() => window.location.reload()}
          >
            Responder novamente
          </button>
        </div>
      )}
    </form>
  );
}
