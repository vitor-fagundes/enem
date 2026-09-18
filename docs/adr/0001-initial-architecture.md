# ADR-0001 — Arquitetura inicial

Status: aceito para a fundação; revisável conforme novas specs.

## Context

Aplicação pessoal, local-first, prazo curto e baixo volume operacional. A preparação tem precedência sobre sofisticação técnica. SPEC-001 e SPEC-002 são Draft v1 e vários contratos de domínio ainda não estão definidos.

## Decision

Monólito Next.js com TypeScript estrito e Tailwind; SQLite operacional acessado por Drizzle ORM com adaptador better-sqlite3. Python com Polars para transformações, Parquet para artefatos analíticos e DuckDB para consultas. Sem serviço Python persistente: execução local por comandos quando houver pipeline especificado.

npm workspaces reúne a aplicação, sem orquestrador adicional. uv e uv.lock fixam o ambiente Python. ESLint/Prettier e Ruff são ferramentas de lint/format; Vitest, Playwright e pytest validam a base. Esses auxiliares atendem os requisitos de qualidade, sem adicionar funcionalidades de produto.

UI em apps/web/src/app; futuras regras operacionais em src/domain; adaptador de persistência em src/lib/db; analytics em packages/analytics/src. Não há schema de negócio, migração ou contrato de integração antecipado. O cliente SQLite é aberto explicitamente e fechado pelo chamador.

## Consequences

Maior simplicidade e velocidade, execução sem infraestrutura distribuída e testes locais. SQLite e seu adaptador exigem runtime Node no servidor; não Edge. Analytics e operacional têm ciclos distintos, e o contrato de intercâmbio aguarda spec. Paralelismo de escrita, backups e volume analítico devem ser revisitados se houver necessidade observada. A arquitetura não é definitiva.

## Referências técnicas

- [Next.js: instalação](https://nextjs.org/docs/app/getting-started/installation)
- [Drizzle: SQLite](https://orm.drizzle.team/docs/get-started/sqlite-new)

## Compatibilidade da fundação

O build usa a opção Webpack já incluída no Next.js, sem nova dependência: o Turbopack falhou neste ambiente ao abrir uma porta interna para processar CSS, inclusive na tentativa com permissão ampliada. Reavaliar o padrão quando houver ambiente compatível.

ESLint 9.39.5 fica fixado temporariamente. A versão 10.10.0 falhou no plugin React da configuração Next instalada (`contextOrFilename.getFilename is not a function`). A linha 9 foi marcada como sem suporte pelo npm; atualizar quando os plugins forem compatíveis, sem desativar regras para mascarar a falha.
