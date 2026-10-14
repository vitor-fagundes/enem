# enem-rei

Ferramenta pessoal de apoio à decisão para preparação intensiva para o ENEM. O problema é alocar tempo de estudo escasso para maximizar ganho esperado de desempenho por hora, inicialmente visando Relações Econômicas Internacionais na UFMG.

## Estado e princípios

Esta entrega contém a fundação técnica, a questão interativa do M2 (`/questao`), o catálogo de questões reais verificadas do M3 (`/questoes`) e o registro de tentativas com indicadores simples de desempenho do M4 (`/desempenho`: total, acertos, erros, não corrigidas, taxa de acerto e divisão por área). Não há sessão de estudo, domínio/mastery, diagnóstico de erros, recomendações ou dashboard completo. Os demais critérios de aceite funcionais das specs permanecem pendentes.

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

## M3 — catálogo de questões (`/questoes`)

Escopo e aceitação em [docs/m3-catalogo-questoes.md](docs/m3-catalogo-questoes.md); leitura do SQLite pela web em [ADR-0002](docs/adr/0002-web-readonly-ingestion-sqlite.md). Os dados continuam **fora do Git**:

- `ENEM_CATALOG_DIR`: diretório com um arquivo JSON por questão (formato `enem-rei/m2-question/v1`). Só arquivos regulares `*.json` são lidos; backups `.bak-*`, outros arquivos, diretórios e links simbólicos são ignorados.
- `ENEM_DATA_ROOT`: data_root da ingestão (`ingestion.db` e payloads), como no M2.

```bash
npm run build
R=$HOME/.local/share/enem-rei/m2
ENEM_CATALOG_DIR=$R/curation ENEM_DATA_ROOT=$R/data_root \
ENEM_M2_QUESTION_PATH=$R/curation/enem-2024-d1-cd1-q10.json ENEM_M2_DATA_ROOT=$R/data_root \
npm run start
```

Abra http://127.0.0.1:3000/questoes. Sem as duas variáveis, a página informa que o catálogo não está configurado. Regras de entrada: JSON válido pelo domínio do M2, contexto de numeração `COMMON`, confirmação humana registrada (`extraction.confirmation_recorded_at`) e nome do arquivo igual a `<id>.json`, com `id = enem-<ano>-d<dia>-cd<caderno>-q<N>`. JSON malformado, estrutura inválida, outro contexto, falta de confirmação, nome divergente ou posição duplicada (todas as entradas conflitantes) ficam fora do catálogo e aparecem em "Arquivos fora do catálogo". A lista segue a ordem numérica; `/questoes/<id>` reutiliza o corpo, o formulário e o bloco de fonte do M2, com anterior/próxima (a resposta é descartada ao navegar). ID inexistente ou excluído responde 404.

A cada requisição, cada recurso distinto referenciado pelas questões é verificado uma única vez (mesmas conferências do M2, SQLite aberto uma vez, somente leitura), sem cache entre requisições. Falha no caderno marca apenas as questões dependentes como "Erro de proveniência: questão indisponível" (sem link; a página mostra o erro e não a questão; a navegação a pula); falha só no gabarito exibe a questão com "Gabarito não verificado" e sem correção. Testes usam o catálogo sintético gerado por `build_m2_fixture.py` (diretórios `catalog/` e `catalog-compromised/`), servido nas portas 3100/3101 do Playwright.

## M4 — registro de tentativas e desempenho (`/desempenho`)

Escopo e aceitação em [docs/m4-registro-tentativas.md](docs/m4-registro-tentativas.md); decisão em [ADR-0003](docs/adr/0003-web-attempts-sqlite.md). Cada resposta confirmada em `/questoes/<id>` é corrigida **no servidor** (Server Action, `evaluateAnswer` com o gabarito verificado pela proveniência do M3, refeita a cada envio) e gravada em um SQLite operacional próprio, separado do `ingestion.db`:

- `ENEM_ATTEMPTS_DB`: arquivo SQLite de tentativas, **fora do Git** (sugestão: `apps/web/.local/attempts.sqlite`, já ignorado). O diretório pai deve existir; o arquivo e o esquema (`PRAGMA user_version = 1`) são criados no primeiro registro. O caminho é recusado se for o `ingestion.db` de `ENEM_DATA_ROOT`/`ENEM_M2_DATA_ROOT` ou ficar dentro de `raw/` desses data roots ou de `data/raw`.

```bash
npm run build
R=$HOME/.local/share/enem-rei/m2
mkdir -p $HOME/.local/share/enem-rei/m4
ENEM_CATALOG_DIR=$R/curation ENEM_DATA_ROOT=$R/data_root \
ENEM_M2_QUESTION_PATH=$R/curation/enem-2024-d1-cd1-q10.json ENEM_M2_DATA_ROOT=$R/data_root \
ENEM_ATTEMPTS_DB=$HOME/.local/share/enem-rei/m4/attempts.sqlite \
npm run start
```

Abra http://127.0.0.1:3000/questoes, responda e consulte http://127.0.0.1:3000/desempenho. Regras principais:

- O navegador envia só `submission_id` (UUID v4, um por formulário), `question_id`, `question_file_sha256` (SHA-256 do arquivo curado exibido), a alternativa e `duration_ms` (estimativa via `performance.now()`, inteiro de 0 a 86 400 000). Resultado, gabarito, área e horário são determinados pelo servidor; o gabarito não é enviado à página do catálogo e só volta na resposta do registro, para `CORRECT`/`INCORRECT`.
- São rejeitados sem gravar: envio malformado, questão inexistente ou bloqueada, arquivo da questão alterado desde a exibição, banco não configurado ou recusado. Sem `ENEM_ATTEMPTS_DB`, a confirmação mostra "Registro de tentativas não configurado" e nenhum resultado.
- Uma linha imutável por tentativa (gatilhos impedem `UPDATE`/`DELETE`); responder de novo (recarregar, navegar ou "Responder novamente") cria outra linha. Reenvio do mesmo `submission_id` com o mesmo conteúdo não duplica; com conteúdo diferente é rejeitado.
- `NOT_VERIFIED` (gabarito não verificado) e `ANNULLED` são gravados, mas não contam como acerto nem erro. `/desempenho` lê o banco somente leitura e mostra total, acertos, erros, não corrigidas, taxa de acerto = acertos/(acertos + erros) ("sem dados" com denominador 0), divisão por área (`LC`, `CH`, `CN`, `MT` por nome oficial exato; demais textos como "área não mapeada") e a lista das tentativas (mais recente primeiro). A taxa não representa domínio.
- `/questao` (M2) continua sem persistência.

Bancos de tentativas locais (fora do Git, em `~/.local/share/enem-rei/m4/`), com papéis separados:

- `attempts.sqlite`: banco de **validação** do M4, com as tentativas de teste feitas na verificação manual. Preservado como registro dessa validação; não usar para estudo nem alterar.
- `attempts-study.sqlite`: banco pessoal de **estudos**, o histórico real. É o `ENEM_ATTEMPTS_DB` do servidor local de uso diário; começa vazio (o arquivo é criado na primeira resposta confirmada) e não recebe cópia das tentativas de validação.

Para estudar, inicie o servidor com `ENEM_ATTEMPTS_DB=$HOME/.local/share/enem-rei/m4/attempts-study.sqlite` (em vez do caminho de exemplo acima). O banco de tentativas não tem backup automático: apagar o arquivo apaga o histórico. Para consultá-lo sem alterar: `sqlite3 -readonly "$ENEM_ATTEMPTS_DB" 'SELECT * FROM attempt'`. Os e2e do M4 usam o catálogo sintético `catalog-m4/` e bancos de tentativas temporários por servidor e por execução (3102 com banco; 3103 sem `ENEM_ATTEMPTS_DB`).

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
