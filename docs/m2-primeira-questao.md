# M2 — Primeira Questão Interativa do ENEM

Documento curto de escopo e aceitação do marco M2. Não é uma spec Spec Kit; aplica as regras de proveniência já aprovadas na SPEC-003 (modelo de questão) e na SPEC-004 (SourceResource, aquisição e localizadores), sem implementá-las por completo.

## Objetivo

Exibir e responder, em `apps/web` executado localmente, uma única questão real do ENEM, textual e verificada por humano, corrigida pelo gabarito oficial e com referência rastreável ao PDF oficial do INEP.

## Entregas

1. Uma questão real do ENEM, somente texto (sem figura, tabela ou imagem necessária à resposta), transcrita manualmente e verificada pelo usuário contra o PDF oficial.
2. Cinco alternativas, rotuladas como no caderno, sem alternativa inventada.
3. Seleção de uma alternativa e confirmação explícita da resposta.
4. Correção contra o gabarito oficial verificado: resultado correto ou incorreto e a alternativa do gabarito.
5. Referência à fonte visível na página: URL oficial do INEP, SHA-256 do PDF do caderno, página física do PDF e identificação de que o texto é transcrição manual verificada (método, responsável e data).
6. Execução local no Next.js existente (`apps/web`).
7. Testes proporcionais: regra de correção em `apps/web/src/domain`, teste unitário e um e2e com fixture sintética.

## Regras

- Proveniência: o caderno e o gabarito oficiais são ingeridos com `ingest_local_file` (SPEC-004, `source_definition_id` DS-003, URL oficial confirmada no portal do INEP). A questão referencia cada PDF pelo SHA-256 e pela página física zero-based (`PDF_PAGE`, conforme `specs/004-source-resource-and-local-ingestion/contracts/locator.md`), com evidências separadas para conteúdo, posição e gabarito (SPEC-003 FR-025).
- Verificação: antes do uso, os SHA-256 referenciados devem corresponder a `source_resource` registrados no SQLite da ingestão e os payloads devem revalidar (hash e tamanho). Transcrição, página e gabarito são conferidos pelo usuário; texto produzido por LLM é só rascunho e nunca fonte de verdade.
- Gabarito: só há correção quando o gabarito oficial estiver verificado. Sem gabarito verificado, a página mostra "gabarito não verificado" e nenhum resultado de acerto ou erro; questão anulada não é corrigida.
- Dados reais fora do Git: PDFs, banco de ingestão e a transcrição real ficam fora do repositório (ou em caminho ignorado), informados à aplicação por variável de ambiente. Testes usam apenas fixtures sintéticas versionadas.
- Respostas não são persistidas neste marco: nenhuma tentativa é gravada e nenhuma métrica ou histórico é atualizado (exceção explícita à SPEC-001 FR-012/FR-016 para o M2).
- O SQLite da ingestão continua a única autoridade dos metadados de recurso; a questão curada apenas o referencia.

## Fora de escopo e não pré-requisitos

- Parser generalizado de PDF, OCR ou extração automática.
- Modelo físico completo da SPEC-003 (Edition, Application, Booklet, deduplicação, assets, taxonomia, revisões, retificações).
- T-029 e T-030 da SPEC-004, salvo dependência concreta identificada durante a implementação.
- Exportador genérico de questões, banco de questões ou mais de uma questão.
- Histórico de tentativas, métricas, login, dashboard ou recomendação.
- APIs pagas ou LLM em tempo de execução.

## Pré-condições de execução

- Node 24 Linux, `npm ci` e navegador do Playwright no ambiente local (não instalados neste passo).
- PDFs oficiais do caderno e do gabarito obtidos manualmente e ingeridos fora do repositório (não baixados neste passo).

## Critérios de aceitação

1. A rota da questão exibe o enunciado e exatamente cinco alternativas rotuladas.
2. Confirmar fica indisponível até haver uma alternativa selecionada.
3. Após confirmar, a página mostra correto ou incorreto e a alternativa do gabarito oficial.
4. Sem gabarito verificado, a página mostra "gabarito não verificado" e nenhum resultado de acerto ou erro.
5. A página mostra URL oficial, SHA-256 do caderno, página física e o rótulo de transcrição manual verificada.
6. Testes unitários da regra de correção cobrem correto, incorreto, não verificado e anulada; o e2e cobre os critérios 1 a 5 com fixture sintética.
7. Verificação manual com dados reais: a questão aparece no app local, o SHA-256 confere com o PDF oficial ingerido e o texto, a página e o gabarito conferem com os PDFs.
8. Recarregar a página não preserva resposta (nada é persistido).
9. Validações do `AGENTS.md` passam e `git status` não mostra PDF, banco de ingestão ou transcrição real.
