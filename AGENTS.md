# Regras para agentes

1. Leia integralmente as specs relevantes antes de modificar código. A especificação é a fonte de verdade.
2. Não implemente requisitos inexistentes nem antecipe funcionalidades futuras.
3. Não altere regras de negócio sem atualizar a spec explicitamente; registre decisões antes de implementar.
4. Prefira a solução simples. Não introduza tecnologias sem justificativa em ADR.
5. Separe regras de negócio da UI; use `apps/web/src/domain` para regras operacionais futuras.
6. Escreva testes para regras de negócio, incluindo invariantes e casos de borda.
7. Não use LLM para cálculo determinístico nem como fonte de verdade.
8. Preserve proveniência, hashes, versões e lineage de dados externos e derivados.
9. Nunca modifique dados em `data/raw`. Correções geram novos artefatos/versionamento.
10. Não insira secrets no repositório, datasets ou manifestos. Use variáveis de ambiente.
11. Reporte ambiguidades, contradições, riscos e falta de critérios de aceite antes da implementação. Registre questões futuras em documentação; não improvise decisões de produto.
12. Execute testes e checks relevantes antes de declarar a tarefa concluída e relate impedimentos.

## Escopo atual

Fundação técnica e implementação incremental da SPEC-004 (`specs/004-source-resource-and-local-ingestion/`), incluindo ingestão de arquivos locais, conforme suas tarefas e contratos aprovados, uma tarefa explicitamente atribuída por vez (ver "Fluxo de desenvolvimento por tarefa"). Também autorizado: marco M2 — uma única questão real do ENEM, interativa em `apps/web`, estritamente conforme `docs/m2-primeira-questao.md`. Também autorizado: marco M3 — catálogo local de três questões reais verificadas do ENEM em `apps/web`, estritamente conforme `docs/m3-catalogo-questoes.md` e `docs/adr/0002-web-readonly-ingestion-sqlite.md`. Também autorizado: marco M4 — registro de tentativas do catálogo e página de desempenho em `apps/web`, estritamente conforme `docs/m4-registro-tentativas.md` e `docs/adr/0003-web-attempts-sqlite.md`, incluindo seus pré-requisitos. Não implementar o que estiver fora dessas tarefas, do M2, do M3 e do M4: parser de microdados, login/autenticação, RAG/OpenAI, recommendation engine, mastery, redação, scraping ou dashboard completo.
Não remover arquivos existentes. Não baixar grandes datasets nem versionar dados reais.
Sem microsserviços, Swarm, Kubernetes, Kafka, Spark, Redis, Elasticsearch, banco vetorial, filas distribuídas, event sourcing ou CQRS nesta etapa.

## Validação

Na raiz: `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm test`, `npm run build`, `npm run test:e2e`.
Python: `uv run --frozen ruff check .`, `uv run --frozen ruff format --check .`, `uv run --frozen pytest`.
Use os lockfiles; atualizações de dependências devem ser intencionais.

## Fluxo de desenvolvimento por tarefa

Vale para qualquer agente: subagente `implementador` (Claude Code) ou skill `desenvolvimento` (Codex).

1. Execute somente a tarefa explicitamente atribuída (ex.: "T-021 de `specs/004-.../tasks.md`"). Avance para outra tarefa apenas se o usuário autorizar explicitamente um lote, nomeando as tarefas.
2. Leia a seção atual da tarefa, suas dependências, as specs/contratos citados e o código existente relacionado.
3. Ambiguidade, contradição ou dependência ausente que impeça a tarefa: pare e reporte antes de implementar (regra 11).
4. Implemente a menor solução correta. Se a tarefa for test-first, escreva os testes, confirme que falham e só então implemente.
5. Rode os testes focados e a validação relevante (seção Validação).
6. Revise `git status` e `git diff`. Corrija defeitos confirmados com no máximo um ciclo automático de correção; o que restar vai para o relatório.
7. Pare e reporte: arquivos alterados, testes e resultados reais, desvios da tarefa, bloqueios e decisões pendentes para o usuário.

Restrições:

- Nunca execute `git commit`, `git push` ou crie pull requests. Não altere histórico, refs ou remotes (`rebase`, `reset`, `merge`, `cherry-pick`, `revert`, `am`, `remote add/remove/set-url`). Inspeção (`git status`, `diff`, `log`, `show`) é permitida.
- Sem APIs pagas, chaves de API, novas dependências, novas specs ou frameworks.
- Não amplie o escopo nem inicie ciclos de melhoria além da tarefa.
