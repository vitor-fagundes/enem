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

Somente fundação técnica. Não implementar ingestão completa, parser de microdados, login/autenticação, RAG/OpenAI, recommendation engine, mastery, redação, scraping ou dashboard completo nesta etapa.
Não remover arquivos existentes. Não baixar grandes datasets nem versionar dados reais.
Sem microsserviços, Swarm, Kubernetes, Kafka, Spark, Redis, Elasticsearch, banco vetorial, filas distribuídas, event sourcing ou CQRS nesta etapa.

## Validação

Na raiz: `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm test`, `npm run build`, `npm run test:e2e`.
Python: `uv run --frozen ruff check .`, `uv run --frozen ruff format --check .`, `uv run --frozen pytest`.
Use os lockfiles; atualizações de dependências devem ser intencionais.
