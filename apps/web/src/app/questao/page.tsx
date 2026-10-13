import type { Metadata } from "next";
import { connection } from "next/server";
import { loadVerifiedQuestion } from "../../lib/m2/provenance";
import { Checks, QuestionView } from "./question-view";

export const metadata: Metadata = { title: "Questão — enem-rei" };

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
        <QuestionView
          question={result.question}
          verifiedAnswerKey={result.verifiedAnswerKey}
        />
      )}
    </main>
  );
}
