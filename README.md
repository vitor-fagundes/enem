# enem-rei

Ferramenta pessoal de apoio à decisão para preparação intensiva para o ENEM. O problema é alocar tempo de estudo escasso para maximizar ganho esperado de desempenho por hora, inicialmente visando Relações Econômicas Internacionais na UFMG.

## Estado e princípios

Esta entrega contém somente a fundação técnica e uma página estática de identificação. Não há cadastro de questões, sessão, métricas, recomendações ou dashboard implementados. Os critérios de aceite funcionais das specs permanecem pendentes.

Questões antes de teoria; evidência antes de intuição; fontes oficiais prioritárias; cálculos determinísticos; proveniência; regras separadas da UI; simplicidade e estudo antes de sofisticação técnica. LLM não é fonte de verdade nem necessária para o fluxo principal futuro.

## Specs e arquitetura

- [Objetivo do produto](specs/001-product-goal.md)
- [Fontes e proveniência](specs/002-data-sources.md)
- [Análise técnica, requisitos e questões abertas](docs/spec-analysis.md)
- [ADR-0001](docs/adr/0001-initial-architecture.md)

Monólito Next.js/TypeScript/Tailwind com SQLite via Drizzle (better-sqlite3 no servidor Node). Python/Polars, DuckDB e Parquet para analytics local. Sem serviços distribuídos. A conexão SQLite exige caminho explícito, abre apenas quando chamada e deve ser fechada pelo chamador. Ainda não há schema ou migrações de negócio; futuramente usar apps/web/.local/ para o banco, criando o diretório antes da conexão. A arquitetura é inicial, revisável. O build usa a opção Webpack incluída no Next.js por compatibilidade com o ambiente de validação; o ADR registra essa decisão e a fixação temporária do ESLint 9 devido à incompatibilidade dos plugins com a versão 10.

## Estrutura

```text
AGENTS.md                 regras para agentes
specs/                    fonte de verdade do produto
 docs/                    análise técnica
  adr/                    decisões arquiteturais
  research/               pesquisas futuras
 data/                    política e diretórios sem datasets
  raw/inep/               matrix, microdata, exams, methodology
  raw/ufmg/sisu/           originais institucionais
  interim/                intermediários
  processed/              derivados
 apps/web/                aplicação Next.js e testes Vitest/Playwright
  src/app/                UI
  src/domain/             reservado a regras especificadas
  src/lib/db/             conexão SQLite/Drizzle
 packages/analytics/src/  pacote Python reservado a analytics
 scripts/                 reservado a automação futura
 tests/python/            pytest
```

## Como executar

Pré-requisitos: Node conforme `.nvmrc` (linha 24), npm e Python 3.12 com uv instalado. Lockfiles npm e uv devem ser versionados; use instalação congelada para reproduzir as versões. O adaptador SQLite pode exigir compilador C++/Python se não houver binário pré-compilado para sua plataforma.

Na raiz:

```bash
npm ci
uv sync --frozen
npm run dev
```

Abra http://127.0.0.1:3000. Não são necessários secrets, serviços externos ou datasets para executar a fundação.

```bash
npm run lint
npm run format:check
npm run typecheck
npm test
npm run build
npm exec --workspace @enem-rei/web -- playwright install chromium
npm run test:e2e
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
```

Playwright testa o build de produção na porta 3100; execute o build antes. Em Linux, instale as bibliotecas de sistema quando necessário com `npm exec --workspace @enem-rei/web -- playwright install-deps chromium` (pode exigir sudo). Para servir o build manualmente: `npm start`. Para formatar: `npm run format` e `uv run --frozen ruff format .`.

Vitest verifica persistência real SQLite via Drizzle em arquivo temporário; pytest verifica Polars → Parquet → DuckDB com dados sintéticos; Playwright verifica a página servida. Não representam testes de regras de negócio ainda não implementadas.

## Política de dados

[data/README.md](data/README.md): raw é imutável. Nunca alterar originais; correções geram novas versões. Toda ingestão futura deve preservar manifesto, hash e lineage. Não versionar datasets grandes, bancos locais ou credenciais. Nenhum dataset foi baixado; ainda não existe ingestão ou mecanismo executável de proteção de raw.

## Workflow SDD

1. Ler as specs relevantes e identificar critérios de aceite.
2. Registrar ambiguidades e riscos antes de implementar; decidir questões bloqueantes na spec.
3. Atualizar a spec explicitamente quando a regra mudar; documentar decisões arquiteturais em ADR.
4. Implementar apenas o incremento definido, com regras isoladas da UI e testes relevantes.
5. Executar checks, relatar resultados e limitações e revisar a aderência à spec.

Próxima recomendação: SPEC-003 sobre contrato de recurso de origem e ingestão mínima local, conforme questões da análise. Não implementada nesta etapa.

[Resultados da validação desta fundação e inventário de arquivos](docs/validation.md).
