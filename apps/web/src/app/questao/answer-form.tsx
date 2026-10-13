"use client";

import { useState } from "react";
import {
  type AlternativeLabel,
  type AnswerKey,
  type Alternative,
  evaluateAnswer,
} from "../../domain/question";

const RESULT_TEXT = {
  CORRECT: "Correto",
  INCORRECT: "Incorreto",
  NOT_VERIFIED: "Sem correção: gabarito não verificado.",
  ANNULLED: "Questão anulada: não há correção.",
} as const;

/** Estado somente em memória: recarregar a página descarta a resposta. */
export function AnswerForm({
  alternatives,
  answerKey,
}: {
  alternatives: Alternative[];
  answerKey: AnswerKey | null;
}) {
  const [selected, setSelected] = useState<AlternativeLabel | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const result =
    confirmed && selected !== null ? evaluateAnswer(selected, answerKey) : null;

  return (
    <form
      className="mt-6"
      onSubmit={(event) => {
        event.preventDefault();
        if (selected !== null) setConfirmed(true);
      }}
    >
      <fieldset disabled={confirmed}>
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
        disabled={selected === null || confirmed}
        className="mt-4 rounded bg-slate-900 px-4 py-2 text-white disabled:cursor-not-allowed disabled:bg-slate-400"
      >
        Confirmar
      </button>
      {result !== null && (
        <div role="status" className="mt-4 rounded border border-slate-300 p-4">
          <p className="text-lg font-semibold" data-testid="answer-result">
            {RESULT_TEXT[result]}
          </p>
          <p>Sua resposta: {selected}</p>
          {(result === "CORRECT" || result === "INCORRECT") && (
            <p>Gabarito oficial: {answerKey?.published_value}</p>
          )}
        </div>
      )}
    </form>
  );
}
