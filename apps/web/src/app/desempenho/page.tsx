import type { Metadata } from "next";
import Link from "next/link";
import { connection } from "next/server";
import type { StoredAttempt } from "../../domain/attempt";
import {
  type PerformanceStats,
  formatRate,
  summarizePerformance,
} from "../../domain/performance";
import { resolveAttemptsDb } from "../../lib/attempts/config";
import { readAttempts } from "../../lib/attempts/store";

export const metadata: Metadata = { title: "Desempenho — enem-rei" };

const EVALUATION_TEXT: Record<StoredAttempt["evaluation"], string> = {
  CORRECT: "Correto",
  INCORRECT: "Incorreto",
  NOT_VERIFIED: "Não corrigida (gabarito não verificado)",
  ANNULLED: "Não corrigida (questão anulada)",
};

function formatDuration(ms: number): string {
  return `${(ms / 1000).toFixed(1).replace(".", ",")} s`;
}

function Indicators({ stats }: { stats: PerformanceStats }) {
  const rows: Array<[string, string, string]> = [
    ["Total de tentativas", String(stats.total), "total"],
    ["Acertos", String(stats.correct), "correct"],
    ["Erros", String(stats.incorrect), "incorrect"],
    ["Não corrigidas", String(stats.notCorrected), "not-corrected"],
    ["Taxa de acerto", formatRate(stats), "rate"],
  ];
  return (
    <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-6 gap-y-1">
      {rows.map(([label, value, testId]) => (
        <div key={testId} className="contents">
          <dt>{label}</dt>
          <dd className="font-semibold" data-testid={`indicator-${testId}`}>
            {value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export default async function PerformancePage() {
  // Página dinâmica: lê o banco de tentativas a cada requisição.
  await connection();
  const config = await resolveAttemptsDb({
    ENEM_ATTEMPTS_DB: process.env.ENEM_ATTEMPTS_DB,
    ENEM_DATA_ROOT: process.env.ENEM_DATA_ROOT,
    ENEM_M2_DATA_ROOT: process.env.ENEM_M2_DATA_ROOT,
  });
  const read = config.status === "OK" ? readAttempts(config.path) : undefined;

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="text-2xl font-semibold">Desempenho</h1>
      {config.status === "NOT_CONFIGURED" && (
        <p role="alert" className="mt-4">
          Registro de tentativas não configurado. Defina ENEM_ATTEMPTS_DB.
        </p>
      )}
      {config.status === "REFUSED" && (
        <p role="alert" className="mt-4">
          Registro de tentativas recusado: {config.reason}.
        </p>
      )}
      {read?.status === "REFUSED" && (
        <p role="alert" className="mt-4">
          Banco de tentativas indisponível: {read.reason}.
        </p>
      )}
      {read?.status === "READY" && (
        <PerformanceReport attempts={read.attempts} />
      )}
      <p className="mt-10 text-sm">
        <Link className="underline" href="/">
          Início
        </Link>{" "}
        ·{" "}
        <Link className="underline" href="/questoes">
          Catálogo de questões
        </Link>
      </p>
    </main>
  );
}

function PerformanceReport({ attempts }: { attempts: StoredAttempt[] }) {
  const summary = summarizePerformance(attempts);
  return (
    <>
      <section aria-labelledby="indicadores" className="mt-6">
        <h2 id="indicadores" className="text-lg font-semibold">
          Indicadores
        </h2>
        <Indicators stats={summary.overall} />
        <p className="mt-3 text-sm text-slate-600">
          Taxa de acerto = acertos / (acertos + erros), sobre todas as
          tentativas registradas, inclusive repetições. Tentativas sem gabarito
          verificado ou de questões anuladas não contam como acerto nem erro. A
          taxa é um indicador simples e não representa domínio do conteúdo.
        </p>
      </section>

      <section aria-labelledby="por-area" className="mt-8">
        <h2 id="por-area" className="text-lg font-semibold">
          Desempenho por área
        </h2>
        <table className="mt-3 w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-300">
              <th className="py-1 pr-3">Área</th>
              <th className="py-1 pr-3">Tentativas</th>
              <th className="py-1 pr-3">Acertos</th>
              <th className="py-1 pr-3">Erros</th>
              <th className="py-1 pr-3">Não corrigidas</th>
              <th className="py-1">Taxa de acerto</th>
            </tr>
          </thead>
          <tbody>
            {summary.byArea.map((row) => (
              <tr
                key={row.code ?? `texto:${row.label}`}
                data-testid="area-row"
                className="border-b border-slate-200"
              >
                <td className="py-1 pr-3">
                  {row.code !== null
                    ? `${row.code} — ${row.label}`
                    : `Área não mapeada: ${row.label}`}
                </td>
                <td className="py-1 pr-3">{row.stats.total}</td>
                <td className="py-1 pr-3">{row.stats.correct}</td>
                <td className="py-1 pr-3">{row.stats.incorrect}</td>
                <td className="py-1 pr-3">{row.stats.notCorrected}</td>
                <td className="py-1">{formatRate(row.stats)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section aria-labelledby="tentativas" className="mt-8">
        <h2 id="tentativas" className="text-lg font-semibold">
          Tentativas registradas
        </h2>
        {attempts.length === 0 ? (
          <p className="mt-3">Nenhuma tentativa registrada.</p>
        ) : (
          <table className="mt-3 w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-300">
                <th className="py-1 pr-3">Horário (UTC)</th>
                <th className="py-1 pr-3">Questão</th>
                <th className="py-1 pr-3">Alternativa</th>
                <th className="py-1 pr-3">Resultado</th>
                <th className="py-1">Duração aproximada</th>
              </tr>
            </thead>
            <tbody>
              {attempts.map((attempt) => (
                <tr
                  key={attempt.id}
                  data-testid="attempt-row"
                  className="border-b border-slate-200"
                >
                  <td className="py-1 pr-3 font-mono">{attempt.answered_at}</td>
                  <td className="py-1 pr-3">
                    <Link
                      className="underline"
                      href={`/questoes/${attempt.question_id}`}
                    >
                      {attempt.question_id}
                    </Link>
                  </td>
                  <td className="py-1 pr-3">{attempt.selected_label}</td>
                  <td className="py-1 pr-3">
                    {EVALUATION_TEXT[attempt.evaluation]}
                  </td>
                  <td className="py-1">
                    {formatDuration(attempt.duration_ms)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="mt-3 text-sm text-slate-600">
          A duração é estimada pelo navegador (do carregamento da questão à
          confirmação) e pode ser imprecisa.
        </p>
      </section>
    </>
  );
}
