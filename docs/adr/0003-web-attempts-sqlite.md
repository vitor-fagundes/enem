# ADR-0003 — SQLite operacional de tentativas e correção no servidor

Status: aceito em 2026-10-14 para o M4 (`docs/m4-registro-tentativas.md`). A implementação depende do gate de segurança descrito em Consequences.

## Context

A SPEC-001 exige registrar tentativas com questão, resposta, horário e duração (FR-012), corrigir com gabarito oficial válido sem contar anuladas ou não resolvidas como erro (FR-013), atualizar histórico e desempenho por área após cada tentativa (FR-016), usar identificadores canônicos de área (FR-017) e apresentar questões realizadas, taxa de acerto e desempenho por área (FR-025), para um único usuário (FR-008). M2 e M3 não persistem respostas, por exceção explícita registrada em seus documentos.

Até o M3, a única base SQLite usada pela web é o `ingestion.db`, aberto somente leitura (ADR-0002) porque é a autoridade dos metadados de recurso (SPEC-004 FR-019). No M3, a correção ocorre no navegador e o gabarito verificado é enviado ao cliente, risco aceito para uso local. O ADR-0001 já prevê um SQLite operacional acessado por Drizzle ORM com better-sqlite3, sem schema de negócio antecipado, e o `data/README.md` o coloca fora de `data/raw` (em `apps/web/.local/`).

A versão instalada do `next` (16.3.5) tem vulnerabilidade crítica registrada em `docs/m3-catalogo-questoes.md` (seção Segurança), com correção em 16.4.0.

## Decision

1. Tentativas ficam em um SQLite operacional próprio, separado do `ingestion.db`, cujo caminho vem de `ENEM_ATTEMPTS_DB`. Sem essa variável o registro falha explicitamente, sem escrever em outro banco; o caminho é recusado quando coincide com um `ingestion.db` configurado ou fica dentro de `raw` de um data root ou de `data/raw`. O `ingestion.db` continua somente leitura e a decisão do ADR-0002 não muda.
2. O esquema é uma tabela `attempt` append-only (gatilhos abortam `UPDATE` e `DELETE`), uma linha imutável por tentativa, com `CHECK` que impedem acerto/erro sem gabarito `VALID` resolvido. O banco de tentativas guarda só referências (IDs e SHA-256) aos recursos da ingestão e ao arquivo curado da questão, sem copiar metadados de recurso.
3. O esquema é definido em código: DDL idempotente aplicada com better-sqlite3 e versionada por `PRAGMA user_version`, com consultas tipadas por drizzle-orm. Sem drizzle-kit, ferramenta de migração ou nova dependência. Versão desconhecida, ou banco não vazio sem versão, é recusada sem escrita.
4. A gravação ocorre por Server Action do Next.js. A correção do catálogo passa a ocorrer exclusivamente no servidor, com `evaluateAnswer` e o gabarito verificado pela proveniência do M3, refeita a cada envio. O gabarito deixa de ir ao navegador nas páginas do catálogo; volta apenas na resposta do registro, para informar a alternativa correta (FR-013).
5. Envios são idempotentes por `submission_id` único gerado no navegador; reenvio idêntico devolve a tentativa gravada e reenvio divergente é rejeitado.
6. `/questao` (M2) não muda: correção no cliente, sem persistência.
7. Indicadores de `/desempenho` são calculados na leitura por funções puras do domínio, sem tabelas agregadas.

### Atendimento parcial e adiamentos da SPEC-001

Exceção específica do M4, compatível com a constituição (Governance: exceções de feature ou arquiteturais documentadas e aprovadas em spec e/ou ADR). A SPEC-001 não é alterada.

- FR-012: atendido para `/questoes/[id]` (questão, resposta, horário UTC do servidor, duração estimada pelo navegador). Confiança, opcional, não é registrada. `/questao` segue sem persistência (exceção do M2 mantida).
- FR-013: atendido; `NOT_VERIFIED` e `ANNULLED` são preservados e não contam como acerto nem erro.
- FR-014: adiado integralmente. Não há diagnóstico de causa de erro no M4; o modelo não antecipa colunas para isso.
- FR-016: parcial. Histórico e desempenho por área refletem cada tentativa (calculados na leitura). Desempenho por tópico, domínio estimado, prioridade dos tópicos e fila de revisão ficam adiados para marcos com spec própria.
- FR-017: atendido para `LC`, `CH`, `CN`, `MT` por mapeamento exato do nome oficial da área; texto não reconhecido fica identificado como não mapeado, sem nome livre substituindo o código.
- FR-018: não implementado; a taxa de acerto do M4 é apresentada como indicador simples, não como domínio.
- FR-025: parcial. Questões realizadas, taxa de acerto e desempenho por área; meta, dias restantes, tópicos prioritários, revisões pendentes e "Iniciar sessão" ficam adiados.

## Consequences

- Duas bases SQLite com papéis distintos: ingestão (autoridade de recursos, somente leitura pela web) e tentativas (dados operacionais do usuário, escrita apenas pelo registro do M4). Nenhuma é segunda autoridade da outra.
- O histórico é imutável: correções futuras de gabarito ou de transcrição não reescrevem tentativas; recorreção, se vier, exigirá spec própria e nova representação.
- A web passa a escrever em disco; o arquivo de tentativas fica fora do Git (`.local/`, `*.sqlite*` já ignorados) e não tem backup automático.
- Sem `ENEM_ATTEMPTS_DB` válido, o catálogo deixa de mostrar correção, pois correção e registro são a mesma operação no servidor; exibição e navegação continuam.
- Server Actions expõem um endpoint de escrita. **Gate:** a implementação só começa depois de avaliar e corrigir a vulnerabilidade crítica conhecida do `next` 16.3.5 (atualização intencional para 16.4.0 ou superior, em tarefa separada, com lockfile e validações). O servidor continua restrito a `127.0.0.1`.
- `duration_ms` vem do navegador e é estimativa não auditável.
- Mudanças no esquema exigem incrementar `user_version`, revisar este ADR e o documento do M4.

## Alternativas consideradas

- Gravar tentativas no `ingestion.db`: rejeitado; contraria o ADR-0002 (web somente leitura) e mistura dados operacionais do usuário com a autoridade de recursos da SPEC-004 (FR-019).
- Persistir no navegador (`localStorage`/IndexedDB): rejeitado; não é auditável pelo servidor, exige gabarito no cliente para corrigir e não atende à correção exclusivamente no servidor.
- Route Handler (API HTTP própria) em vez de Server Action: rejeitado por exigir contrato HTTP e proteção de origem implementados à mão; a Server Action reaproveita a proteção do framework, condicionada ao gate de segurança.
- drizzle-kit e migrações geradas: rejeitado no M4; acrescenta dependência e etapa de build para uma única tabela. Reavaliar se o esquema crescer.
- Tabelas agregadas atualizadas a cada tentativa: rejeitado; duplicaria a informação derivável das linhas e criaria risco de divergência. Para volume de usuário único, o cálculo na leitura é suficiente.
- Correção no cliente com envio do resultado: rejeitado; o servidor não poderia confiar no resultado e o gabarito continuaria no navegador.

## Relação com ADR-0001 e ADR-0002

- ADR-0001: concretiza o SQLite operacional previsto (better-sqlite3 + drizzle-orm, runtime Node no servidor, cliente aberto e fechado explicitamente pelo chamador), com o primeiro schema de negócio, restrito à tabela `attempt`.
- ADR-0002: permanece integralmente válido. A web continua lendo o `ingestion.db` e os payloads somente leitura, agora também a cada envio de tentativa; o banco de tentativas apenas referencia recursos por ID e SHA-256.
