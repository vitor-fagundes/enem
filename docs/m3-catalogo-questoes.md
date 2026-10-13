# M3 — Catálogo de Questões

Documento curto de escopo e aceitação do marco M3. Não é uma spec Spec Kit; estende o M2 (`docs/m2-primeira-questao.md`) e aplica as regras de proveniência já aprovadas na SPEC-003 (modelo de questão) e na SPEC-004 (SourceResource, aquisição e localizadores), sem implementá-las por completo. A leitura do SQLite de ingestão pela aplicação web está registrada em `docs/adr/0002-web-readonly-ingestion-sqlite.md`.

## Objetivo

Permitir, em `apps/web` executado localmente, escolher entre três questões reais do ENEM verificadas, respondê-las e navegar entre elas, mantendo a página `/questao` do M2 sem alteração de comportamento.

## Entregas

1. Rota `/questoes`: catálogo (lista) das questões utilizáveis, em ordem determinística.
2. Rota `/questoes/[id]`: página de resolução com enunciado, alternativas, confirmação, correção e referência à fonte, como no M2, e navegação anterior/próxima.
3. Duas questões reais novas, além da Q10 já existente, curadas no formato v1 do M2 (`enem-rei/m2-question/v1`), fora do Git.
4. Carregamento do catálogo a partir de um diretório de arquivos JSON individuais, com exclusão explícita e aviso para arquivos inválidos, duplicados ou sem confirmação humana.
5. Testes proporcionais: unitários para carregamento, exclusão, ordenação, navegação e verificação única por recurso; e2e com fixtures sintéticas.

## Decisões

- Catálogo com 3 questões reais no total: a Q10 já existente (`enem-2024-d1-cd1-q10`) e 2 novas.
- Somente ENEM 2024, Dia 1, Caderno 1 (Azul), aplicação regular, a partir dos PDFs já ingeridos; nenhuma nova ingestão é necessária:
  - prova: SHA-256 `b0adc1dc79a002aba36f725f1ef792cf53e47ff75ee012638ef34a4e6fbb18f5`;
  - gabarito: SHA-256 `673d3d060156d6ad610ecf96c3dd0b8c61f361e16c57860c4ca5b5fecc8be050`.
- Novas questões: número maior ou igual a 6 (contexto de numeração `COMMON`), exclusivamente textuais, com texto-base e referência (fonte), compatíveis com o formato v1 do M2 (`base_text` e `source_lines` obrigatórios).
- Cada questão exige confirmação humana antes de ficar disponível para resposta, pelo processo do M2: rascunho assistido por LLM e confirmação pessoal declarada pelo usuário, registrada no JSON (`extraction.confirmation_recorded_at`) sem inventar horário.
- ID estável por ocorrência no caderno: `enem-2024-d1-cd1-q<N>`; o arquivo se chama `<id>.json`. Esse ID identifica a ocorrência (QuestionPlacement no caderno), não a Question da SPEC-003, cuja identidade independe de posição, cor e caderno (FR-005). Deduplicação entre cores fica fora do M3.
- Arquivos JSON individuais ficam fora do Git; o diretório de curadoria existente (`~/.local/share/enem-rei/m2/curation/`) pode ser reutilizado. Somente arquivos `*.json` são lidos; backups `.bak-*` são ignorados.
- `ENEM_CATALOG_DIR` indica o diretório das questões; `ENEM_DATA_ROOT` indica os recursos ingeridos (data root com `ingestion.db`).
- `ENEM_M2_*` e a página `/questao` continuam funcionando sem alteração de comportamento.
- A resposta não persiste ao navegar entre questões.
- Reutilizar o domínio existente (`validateQuestion`, `evaluateAnswer`), a correção e a verificação de proveniência do M2.
- Cada recurso compartilhado é verificado uma única vez por requisição, sem cache entre requisições.
- Arquivos inválidos, duplicados (mesma posição) ou sem confirmação humana não entram no catálogo utilizável: ficam fora, com aviso. ID inexistente ou excluído responde 404.
- Falhas de proveniência não derrubam o catálogo inteiro; bloqueiam apenas as questões afetadas, conforme as regras do M2: falha no recurso do caderno impede a exibição da questão; falha apenas no gabarito exibe a questão sem correção, com "gabarito não verificado".
- Gabarito enviado ao navegador: aceito neste MVP estritamente local (servidor só em `127.0.0.1`), como decisão consciente e risco aceito.

## Regras

- Proveniência: cada questão referencia os PDFs ingeridos pelo SHA-256 e pela página física zero-based (`PDF_PAGE`), com evidências separadas para conteúdo, posição e gabarito (SPEC-003 FR-025). Antes do uso, os SHA-256 devem corresponder a `source_resource` no SQLite da ingestão e os payloads devem revalidar (hash e tamanho). O SQLite continua a única autoridade dos metadados de recurso (SPEC-004 FR-019); a web só lê.
- Verificação humana: transcrição, página e gabarito são conferidos pelo usuário; texto produzido por LLM é só rascunho e nunca fonte de verdade. Questão sem confirmação humana registrada não fica disponível para resposta.
- Dados reais fora do Git: PDFs, banco de ingestão e transcrições reais ficam fora do repositório, informados por variável de ambiente. Testes usam apenas fixtures sintéticas versionadas.
- Sem persistência: nenhuma tentativa é gravada e nenhuma métrica ou histórico é atualizado. A persistência de tentativas e histórico (SPEC-001 FR-012/FR-016) continua prevista para marcos posteriores; exceção explícita renovada para o M3.

## Fora de escopo

- Parser generalizado de PDF, OCR, scraping ou extração automática.
- Nova ingestão, outros cadernos, cores, dias, edições ou aplicações.
- Questões com figura, tabela ou imagem necessária à resposta, e questões de língua estrangeira (números 1 a 5).
- Modelo físico completo da SPEC-003 (Edition, Application, Booklet, deduplicação entre cores, assets, taxonomia, revisões, retificações).
- Banco de dados próprio da web, exportador ou snapshot de questões, cache entre requisições ou infraestrutura genérica.
- Persistência de respostas, histórico de tentativas, métricas, login, dashboard ou recomendação.
- APIs pagas ou LLM em tempo de execução.
- Atualização de dependências (tarefa separada; ver Segurança).

## Pré-condições

- Ambiente local do M2 funcionando (Node 24 Linux, `npm ci`, navegador do Playwright).
- PDFs do caderno e do gabarito já ingeridos em `ENEM_DATA_ROOT` com os SHA-256 acima.
- Q10 curada e confirmada no diretório de curadoria; as duas novas questões curadas e confirmadas pelo usuário antes da verificação manual.

## Critérios de aceitação

1. Critério principal: o usuário abre `/questoes`, escolhe entre três questões reais verificadas, responde e navega entre elas, sem perder a funcionalidade original do M2.
2. `/questoes` lista as questões utilizáveis em ordem determinística (por número da questão).
3. `/questoes/[id]` exibe enunciado, exatamente cinco alternativas, confirmação, correção e referência à fonte como no M2.
4. Anterior/próxima seguem a ordem do catálogo; a primeira questão não tem anterior e a última não tem próxima.
5. Navegar ou recarregar não preserva resposta.
6. Arquivo inválido, duplicado (mesma posição) ou sem confirmação humana fica fora do catálogo, com aviso; arquivos não `*.json` e backups `.bak-*` são ignorados.
7. ID inexistente ou excluído responde 404.
8. Falha de proveniência no recurso do caderno bloqueia apenas a questão afetada; falha só no gabarito exibe a questão com "gabarito não verificado" e sem resultado.
9. Teste unitário comprova uma única verificação por recurso distinto por requisição.
10. Testes unitários e e2e usam somente dados sintéticos.
11. `/questao` e seus e2e permanecem inalterados e passando.
12. Verificação manual com dados reais: as três questões aparecem no app local, os SHA-256 conferem com os PDFs ingeridos e texto, página e gabarito conferem com os PDFs.
13. Validações do `AGENTS.md` passam e `git status` não mostra PDF, banco de ingestão ou transcrição real.

## Segurança (triagem)

- `npm audit` executado em 2026-10-13, sem atualizar dependências: 9 vulnerabilidades (1 crítica, 8 altas).
- Produção (3): `next` 16.3.5 (crítica; correção em 16.4.0), `sharp` 0.35.4 (alta; via `next`) e `source-map-js` 1.2.1 (alta; via postcss/tailwind).
- Desenvolvimento: cadeia do `eslint-config-next` (`@next/eslint-plugin-next` → `fast-glob` → `micromatch` → `braces`) e `brace-expansion` (DoS em lint).
- Conclusão: PROCEED para uso local, com condições:
  - servidor só em `127.0.0.1`;
  - não usar `next/og`, `next/image` com imagens remotas, ISR/`revalidate`, `use cache` nem `draftMode`;
  - atualizar `next` (16.4.0 ou superior) e transitivas como tarefa separada e intencional antes de qualquer exposição além do localhost;
  - não aplicar o downgrade sugerido para `eslint-config-next`.
