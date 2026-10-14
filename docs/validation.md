# Validation — fundação

## Ambiente

Node 24.21.0 preparado em /tmp e verificado contra SHA-256 publicado pelo fornecedor; npm 11.19.0; Python 3.12.3. Dependências fixadas em package-lock.json e uv.lock. Nenhum dataset real foi baixado.

## Comandos e resultados

| Comando                                                    | Resultado                                                                                                                                                                                                           |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `npm install` (dependências e ferramentas, versões exatas) | Concluído; lockfile gerado; auditoria retornou zero vulnerabilidades.                                                                                                                                               |
| `uv lock` e `uv sync --frozen`                             | Concluídos; ambiente Python instalado.                                                                                                                                                                              |
| `npm run lint`                                             | Passou sem avisos após ajuste do export do PostCSS.                                                                                                                                                                 |
| `npm run format` e `npm run format:check`                  | Formatação aplicada e check aprovado; specs excluídas do formatter.                                                                                                                                                 |
| `npm run typecheck`                                        | Passou: tipos de rotas e TypeScript estrito.                                                                                                                                                                        |
| `npm test`                                                 | 1 teste Vitest passou: Drizzle/SQLite em arquivo temporário, persistência após reabertura e foreign keys habilitadas.                                                                                               |
| `npm run build` com Turbopack                              | Falhou por restrição de abertura de porta interna, também na tentativa com permissão ampliada.                                                                                                                      |
| `npm run build --workspace @enem-rei/web -- --webpack`     | Passou; página inicial e not-found pré-renderizadas. O script build agora incorpora essa opção.                                                                                                                     |
| `uv run --frozen ruff check .`                             | Passou.                                                                                                                                                                                                             |
| `uv run --frozen ruff format --check .`                    | Passou.                                                                                                                                                                                                             |
| `uv run --frozen pytest`                                   | 1 teste passou: Polars → Parquet → consulta DuckDB.                                                                                                                                                                 |
| `playwright install chromium` via npm exec                 | Concluído com permissão de rede; navegador em /tmp.                                                                                                                                                                 |
| `npm run test:e2e`                                         | Bloqueado pelo ambiente: tentativa inicial não iniciou servidor; repetição autorizada confirmou HTTP 200, mas Chromium falhou por ausência de libnspr4.so. Nenhuma asserção de navegador foi executada com sucesso. |
| `playwright install-deps chromium` via npm exec            | Tentativa autorizada falhou: sudo exige senha indisponível na sessão.                                                                                                                                               |
| `git check-ignore`                                         | Dados, Parquet, banco local e .env ignorados; README de dados e .gitkeep não ignorados.                                                                                                                             |
| `git diff --check`                                         | Sem erros; arquivos da entrega ainda não adicionados ao index.                                                                                                                                                      |

As chamadas locais usaram PATH do Node temporário, UV_CACHE_DIR em /tmp e PLAYWRIGHT_BROWSERS_PATH=/tmp/enem-playwright. Instalações com acesso de rede foram repetidas com permissão ampliada após bloqueio de DNS no sandbox.

## Limitações e compatibilidade

Playwright está configurado, mas o teste E2E ainda precisa passar em ambiente com bibliotecas Linux do Chromium. Instale as dependências conforme README, execute `npm run build` e `npm run test:e2e`.
ESLint 10 foi testado e falhou por incompatibilidade do plugin React; 9.39.5 foi fixado temporariamente. O ADR registra essa dívida e a opção de build. Os testes verificam infraestrutura, não os critérios funcionais futuros das specs. Imutabilidade de raw é política documentada, ainda sem ingestão executável.

## Arquivos criados

- `.gitignore`
- `.nvmrc`
- `.prettierignore`
- `.prettierrc.json`
- `.python-version`
- `AGENTS.md`
- `README.md`
- `apps/web/eslint.config.mjs`
- `apps/web/next-env.d.ts`
- `apps/web/package.json`
- `apps/web/playwright.config.ts`
- `apps/web/postcss.config.mjs`
- `apps/web/src/app/globals.css`
- `apps/web/src/app/layout.tsx`
- `apps/web/src/app/page.tsx`
- `apps/web/src/domain/.gitkeep`
- `apps/web/src/lib/db/client.ts`
- `apps/web/tests/e2e/home.spec.ts`
- `apps/web/tests/unit/database.test.ts`
- `apps/web/tsconfig.json`
- `apps/web/vitest.config.ts`
- `data/README.md`
- `data/interim/.gitkeep`
- `data/processed/.gitkeep`
- `data/raw/inep/exams/.gitkeep`
- `data/raw/inep/matrix/.gitkeep`
- `data/raw/inep/methodology/.gitkeep`
- `data/raw/inep/microdata/.gitkeep`
- `data/raw/ufmg/sisu/.gitkeep`
- `docs/adr/0001-initial-architecture.md`
- `docs/research/.gitkeep`
- `docs/spec-analysis.md`
- `docs/validation.md`
- `package-lock.json`
- `package.json`
- `packages/analytics/src/enem_rei_analytics/__init__.py`
- `pyproject.toml`
- `scripts/.gitkeep`
- `tests/python/test_analytics_stack.py`
- `uv.lock`

## Arquivos existentes

As duas specs existentes foram preservadas sem alteração. Nenhum arquivo existente foi removido. Não foi criado commit.

## M2 — primeira questão interativa

Escopo: [m2-primeira-questao.md](m2-primeira-questao.md). Execução em Node 24.21.0 Linux, Chromium do Playwright em `~/.cache/ms-playwright` (sem bibliotecas de sistema faltantes neste ambiente).

| Comando                                 | Resultado                                                                                                     |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `npm run lint`                          | Passou.                                                                                                       |
| `npm run format:check`                  | Falha preexistente apenas em 28 arquivos de `.agents/`, `.claude/skills/` e `.specify/`, não alterados no M2. |
| `npm run typecheck`                     | Passou.                                                                                                       |
| `npm test`                              | 3 arquivos, 40 testes Vitest passaram (correção, validação estrutural, proveniência com SQLite sintético).    |
| `npm run build`                         | Passou sem dados reais; `/questao` dinâmica (ƒ).                                                              |
| `npm run test:e2e`                      | 8 testes passaram (home + 7 do M2 com data_root sintético nas portas 3100/3101).                              |
| `uv run --frozen ruff check .`          | Passou.                                                                                                       |
| `uv run --frozen ruff format --check .` | Passou.                                                                                                       |
| `uv run --frozen pytest -q`             | 268 testes passaram.                                                                                          |

Verificação com dados reais (fora do Git): `GET /questao` retornou 200 com enunciado, cinco alternativas, os dois SHA-256 e as páginas físicas, sem erro de proveniência; seleção da alternativa do gabarito mostrou "Correto" e outra alternativa "Incorreto"; recarregar descartou a resposta. O `ingestion.db` e os payloads não foram alterados.

Proveniência da transcrição real: rascunho por leitura visual assistida por LLM (Claude Code) dos PDFs oficiais, conferido por comparação visual de capturas da prova e do gabarito em conversa com o ChatGPT e, depois, confirmado pessoalmente pelo usuário vitor-fagundes contra o material oficial (texto-base, enunciado, alternativas A–E e gabarito), conforme declaração dele em conversa. O horário dessa conferência pessoal não é conhecido (`verified_at = null`); `confirmation_recorded_at` guarda apenas o horário em que a confirmação foi registrada. A página exibe o rótulo "Transcrição assistida por LLM, conferida visualmente e confirmada pessoalmente pelo usuário" quando há confirmação registrada (sem ela, mantém o rótulo "não verificada pessoalmente pelo usuário"). A pendência anterior dos critérios 5 e 7 de `docs/m2-primeira-questao.md` (transcrição conferida pelo usuário) foi resolvida por essa confirmação declarada pelo usuário; o arquivo anterior foi preservado como backup fora do Git.

## M3 — catálogo de questões

Escopo: [m3-catalogo-questoes.md](m3-catalogo-questoes.md). Node 24.21.0 Linux; dados reais fora do Git.

| Comando                                 | Resultado                                                                                                                                                      |
| --------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `npm run lint`                          | Passou.                                                                                                                                                        |
| `npm run format:check`                  | Passou (todos os arquivos).                                                                                                                                    |
| `npm run typecheck`                     | Passou.                                                                                                                                                        |
| `npm test`                              | 5 arquivos, 72 testes Vitest passaram (40 do M2 + 32 do M3: seleção, ordenação, navegação, classificação de proveniência e carregamento com SQLite sintético). |
| `npm run build`                         | Passou sem dados reais; `/questao`, `/questoes` e `/questoes/[id]` dinâmicas (ƒ).                                                                              |
| `npm run test:e2e`                      | 19 testes passaram (home + 7 do M2 + 11 do M3; catálogos sintéticos nas portas 3100/3101).                                                                     |
| `uv run --frozen ruff check .`          | Passou.                                                                                                                                                        |
| `uv run --frozen ruff format --check .` | Passou.                                                                                                                                                        |
| `uv run --frozen pytest -q`             | 268 testes passaram.                                                                                                                                           |

Verificação única por recurso: o teste unitário espiona a leitura dos payloads (`createReadStream`) e confirma exatamente duas leituras por requisição para três questões que compartilham dois PDFs sintéticos, e nova leitura a cada requisição (sem cache).

Verificação com dados reais (fora do Git), servidor em `127.0.0.1:3300` com `ENEM_CATALOG_DIR` e `ENEM_DATA_ROOT` apontando para a curadoria e o data_root locais: `GET /questoes` retornou 200 listando as questões 9, 10 e 54 nessa ordem, todas com "Fonte verificada" e sem avisos (os backups `.bak-*` foram ignorados); `/questoes/enem-2024-d1-cd1-q9`, `-q10` e `-q54` retornaram 200 sem erro de proveniência; `/questoes/inexistente` retornou 404; `/questao` continuou retornando 200. No navegador (Playwright), a alternativa do gabarito mostrou "Correto" e "Gabarito oficial: X" (9 → E, 10 → C, 54 → D), outra alternativa mostrou "Incorreto", anterior/próxima respeitaram as bordas e a resposta foi descartada ao navegar. Os arquivos de curadoria e o `ingestion.db` mantiveram os mesmos SHA-256 antes e depois.

## M4 — registro de tentativas e desempenho

Escopo: [m4-registro-tentativas.md](m4-registro-tentativas.md); decisão: [ADR-0003](adr/0003-web-attempts-sqlite.md). Node 24.21.0 Linux, `next` 16.4.0; dados reais e banco de tentativas fora do Git.

| Comando                                 | Resultado                                                                                                                                                                                                                                                                              |
| --------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `npm run format:check`                  | Passou.                                                                                                                                                                                                                                                                                |
| `npm run lint`                          | Passou.                                                                                                                                                                                                                                                                                |
| `npm run typecheck`                     | Passou.                                                                                                                                                                                                                                                                                |
| `npm test`                              | 11 arquivos, 160 testes Vitest passaram (72 do M2/M3 + 88 do M4: área, envio e `duration_ms`, idempotência, indicadores, configuração, armazenamento com gatilhos/`CHECK`/`user_version` e registro no servidor com catálogo sintético).                                               |
| `npm run build`                         | Passou sem dados reais; `/desempenho`, `/questao`, `/questoes` e `/questoes/[id]` dinâmicas (ƒ).                                                                                                                                                                                       |
| `npm run test:e2e`                      | 34 testes passaram (19 do M2/M3 sem alteração + 15 do M4). Servidores 3100/3101 (M2/M3, agora com banco de tentativas próprio), 3102 (catálogo `catalog-m4/` com banco) e 3103 (sem `ENEM_ATTEMPTS_DB`); reinício simulado com um novo `next start` na porta 3104 sobre o mesmo banco. |
| `git diff --check`                      | Sem erros.                                                                                                                                                                                                                                                                             |
| `uv run --frozen ruff check .`          | Passou.                                                                                                                                                                                                                                                                                |
| `uv run --frozen ruff format --check .` | Passou.                                                                                                                                                                                                                                                                                |
| `uv run --frozen pytest -q`             | 268 testes passaram.                                                                                                                                                                                                                                                                   |

Isolamento dos e2e: o processo principal do Playwright cria um diretório temporário por execução (`ENEM_E2E_RUN_DIR`, herdado pelos workers); cada servidor recria sua fixture em um subdiretório próprio e usa um banco de tentativas próprio fora dele; o diretório é removido no `globalTeardown`. O e2e confere que o HTML e o payload RSC (`RSC: 1`) de `/questoes/[id]` não contêm `answer_key`, `published_value` nem "Gabarito oficial" antes da confirmação (controle positivo: `/questao` do M2 ainda contém `published_value`).

Verificação com dados reais (servidor de produção em `127.0.0.1:3000`, `ENEM_CATALOG_DIR`/`ENEM_DATA_ROOT` na curadoria e no data_root locais, `ENEM_ATTEMPTS_DB=~/.local/share/enem-rei/m4/attempts.sqlite`, navegador via Playwright):

1. `/desempenho` antes de responder: total 0, taxa "sem dados", e o arquivo do banco não foi criado pela leitura.
2. Q9 respondida com E: "Correto", "Gabarito oficial: E"; `/desempenho`: total 1, taxa 100,0% (1/1).
3. Q10 respondida com A: "Incorreto", gabarito C. Q9 respondida de novo com B: "Incorreto", gabarito E.
4. `/desempenho`: total 3, acertos 1, erros 2, não corrigidas 0, taxa 33,3% (1/3); LC 3 tentativas, 33,3% (1/3); CH, CN e MT "sem dados".
5. Servidor encerrado e iniciado de novo: `/desempenho` mostrou os mesmos indicadores e as três tentativas; as linhas no SQLite (consultado com `sqlite3 -readonly`) ficaram idênticas antes e depois (`user_version = 1`, `evaluation_rule_version = evaluateAnswer/v1`, SHA-256 do arquivo da questão, do caderno e do gabarito gravados).
6. O HTML e o payload RSC das páginas das questões não continham o gabarito antes da confirmação; `/questao`, `/questoes` (três questões) e o 404 de ID inexistente continuaram funcionando.
7. Os SHA-256 dos arquivos de curadoria, do `ingestion.db` e dos payloads foram os mesmos antes e depois.
