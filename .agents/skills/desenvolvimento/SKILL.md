---
name: desenvolvimento
description: Implementa uma única tarefa explicitamente atribuída de specs/*/tasks.md (ex.: "T-021 de SPEC-004"), com testes, validação e revisão do diff, e para ao final com um relatório. Use quando o usuário pedir para implementar uma tarefa específica. Nunca faz commit, push ou pull request.
---

Siga integralmente `AGENTS.md`, em especial a seção "Fluxo de desenvolvimento por tarefa" e suas restrições. Leia também `.specify/memory/constitution.md` e as specs citadas pela tarefa antes de alterar código.

Execute somente a tarefa recebida. Ao terminar, ou ao encontrar um bloqueio, pare e devolva este relatório:

- Tarefa e arquivos criados ou alterados.
- Testes adicionados e resultado test-first, quando aplicável.
- Comandos de validação executados e resultados reais.
- `git status` final.
- Desvios da tarefa, bloqueios e decisões pendentes para o usuário.
