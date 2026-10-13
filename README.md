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

## M2 — primeira questão (`/questao`)

Escopo e aceitação em [docs/m2-primeira-questao.md](docs/m2-primeira-questao.md). A página lê um arquivo de questão curado (JSON, formato `enem-rei/m2-question/v1`) e o data_root da ingestão (SPEC-004), ambos **fora do Git**, informados por variáveis de ambiente:

- `ENEM_M2_QUESTION_PATH`: arquivo da questão curada; o bloco `extraction` registra o método da transcrição e da conferência (`verified_at` pode ser `null` quando o horário da conferência não foi registrado; `confirmation_recorded_at`, opcional, é o horário do registro da confirmação pessoal declarada pelo usuário, não o da conferência). A página só afirma confirmação pessoal quando `confirmation_recorded_at` está preenchido.
- `ENEM_M2_DATA_ROOT`: data_root da ingestão (`<data_root>/ingestion.db` e `raw/resources/<sha256>/payload`).

```bash
npm run build
ENEM_M2_QUESTION_PATH=$HOME/.local/share/enem-rei/m2/curation/enem-2024-d1-cd1-q10.json \
ENEM_M2_DATA_ROOT=$HOME/.local/share/enem-rei/m2/data_root \
npm run start
```

Abra http://127.0.0.1:3000/questao. Sem as variáveis, a página informa que a questão não está configurada. A cada requisição o servidor abre o SQLite somente leitura e confere, para cada recurso referenciado: `source_resource` com o mesmo SHA-256 e `resource_id`, `storage_locator = raw/resources/<sha256>/payload`, aquisição registrada com a URL referenciada e SHA-256/tamanho recalculados do payload. Falha em recurso do caderno mostra erro de proveniência (a questão não é exibida); falha só no gabarito mostra a questão com "gabarito não verificado" e sem correção. Respostas ficam apenas na memória da página. Testes usam somente dados sintéticos gerados por `apps/web/tests/e2e/support/build_m2_fixture.py` (que chama `ingest_local_file`).

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
