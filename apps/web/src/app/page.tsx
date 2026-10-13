import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-20">
      <h1 className="text-3xl font-semibold">enem-rei</h1>
      <p className="mt-4 text-lg">
        Apoio pessoal à decisão de estudo para o ENEM.
      </p>
      <p className="mt-4 text-slate-600">
        Fundação técnica. As funcionalidades de estudo serão implementadas
        conforme as próximas especificações.
      </p>
      <p className="mt-4">
        <Link className="underline" href="/questao">
          Responder a questão do M2
        </Link>
      </p>
      <p className="mt-2">
        <Link className="underline" href="/questoes">
          Catálogo de questões (M3)
        </Link>
      </p>
    </main>
  );
}
