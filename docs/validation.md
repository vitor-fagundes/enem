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
