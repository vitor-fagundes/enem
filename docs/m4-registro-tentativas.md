# M4 — Registro de Tentativas e Desempenho

Documento curto de escopo e aceitação do marco M4. Não é uma spec Spec Kit; estende o M3 (`docs/m3-catalogo-questoes.md`) e implementa, de forma parcial e explícita, a SPEC-001 FR-012, FR-013, FR-016, FR-017 e FR-025, sem alterar a SPEC-001, a SPEC-003 nem a SPEC-004. A persistência em SQLite operacional separado, a correção no servidor e os adiamentos de requisitos estão registrados em `docs/adr/0003-web-attempts-sqlite.md`.

## Objetivo

Registrar de forma durável cada resposta confirmada no catálogo do M3 (`/questoes/[id]`), corrigida exclusivamente no servidor com o gabarito oficial verificado, e apresentar em `/desempenho` as tentativas registradas e indicadores simples de desempenho, mantendo `/questao` do M2 sem persistência.

## Escopo

1. Registro de tentativa ao confirmar uma resposta em `/questoes/[id]`, por Server Action, em SQLite operacional próprio (`ENEM_ATTEMPTS_DB`), separado do banco de ingestão.
2. Correção no servidor com `evaluateAnswer` e o gabarito verificado pela proveniência do M3; o gabarito deixa de ser enviado ao navegador nas páginas do catálogo.
3. Uma linha imutável por tentativa, com proveniência; múltiplas tentativas da mesma questão; reenvio do mesmo envio sem duplicação (idempotência).
4. Mapeamento da área curada para `LC`, `CH`, `CN`, `MT`, com identificação de áreas não reconhecidas.
5. Rota `/desempenho`: lista das tentativas registradas e indicadores (total, acertos, erros, não corrigidas, taxa de acerto e divisão por área).
6. Testes proporcionais: unitários para validação de envio, idempotência, mapeamento de área, indicadores, configuração e armazenamento; e2e com fixtures sintéticas e banco de tentativas isolado.

## Fora de escopo

- Diagnóstico de causa de erro (SPEC-001 FR-014) e remediação (FR-015).
- Desempenho por tópico, domínio estimado/mastery (FR-018, FR-019), prioridade (FR-020 a FR-023), fila de revisão e recomendação; a parte correspondente de FR-016 fica adiada.
- Na visão de FR-025: meta, dias restantes, tópicos prioritários, revisões pendentes e "Iniciar sessão". Dashboard completo.
- Confiança da resposta (FR-012 a define como opcional; não é registrada no M4).
- Persistência em `/questao` (M2), edição ou exclusão de tentativas, recorreção de histórico, exportação.
- Escrita no banco de ingestão ou em `data/raw`; cópia de metadados de recurso para o banco de tentativas além das referências de proveniência descritas abaixo.
- Login, múltiplos usuários (FR-008: usuário único; não há coluna de usuário), APIs pagas, LLM em tempo de execução.
- drizzle-kit, ferramenta de migração, ORM adicional ou qualquer nova dependência; infraestrutura genérica de persistência.
- Novas questões, ingestão, cadernos ou edições.

## Decisões

- Banco: SQLite operacional separado, cujo caminho é informado por `ENEM_ATTEMPTS_DB` (sugestão local: `apps/web/.local/attempts.sqlite`, ignorado pelo Git, conforme `data/README.md`). O `ingestion.db` permanece somente leitura (ADR-0002).
- Configuração obrigatória: sem `ENEM_ATTEMPTS_DB`, o registro falha explicitamente ("registro de tentativas não configurado") e nada é gravado em outro banco. O servidor recusa o caminho quando, após resolução (`path.resolve` e `realpath` do diretório pai), ele é igual ao `ingestion.db` de `ENEM_DATA_ROOT` ou de `ENEM_M2_DATA_ROOT`, ou fica dentro de `<ENEM_DATA_ROOT>/raw`, `<ENEM_M2_DATA_ROOT>/raw` ou `data/raw` do repositório. O arquivo é criado se não existir; o diretório pai deve existir.
- Consequência: como a correção do catálogo passa a ocorrer só no servidor, junto do registro, sem `ENEM_ATTEMPTS_DB` válido a confirmação em `/questoes/[id]` mostra o erro de configuração e nenhum resultado. Exibição, navegação e bloco de fonte do M3 continuam funcionando.
- Uma linha imutável (append-only) por tentativa: questão, alternativa, resultado, horário UTC do servidor, duração aproximada e proveniência. Múltiplas tentativas da mesma questão são permitidas; cada confirmação após recarregar ou navegar é uma nova tentativa.
- Idempotência: cada envio carrega `submission_id` (UUID v4 minúsculo gerado no navegador com `crypto.randomUUID()`, um por formulário montado), único no banco. Reenvio com o mesmo `submission_id` e o mesmo payload (`question_id`, `question_file_sha256`, `selected_label`, `duration_ms`) não cria nova linha e devolve a tentativa já gravada, sem recorrigir. Mesmo `submission_id` com payload diferente é rejeitado (conflito) e nada é gravado.
- Correção exclusivamente no servidor: `evaluateAnswer(selected, verifiedAnswerKey)` com o gabarito verificado pela mesma carga e verificação de proveniência do M3 (`loadCatalog`), refeitas a cada envio, sem cache entre requisições. O navegador nunca envia resultado, gabarito, área nem horário; o servidor ignora esses dados se chegarem.
- Gabarito fora do navegador no catálogo: o payload de `/questoes/[id]` (HTML e dados do React Server Components) não contém o gabarito; a página recebe apenas se há gabarito verificado. A alternativa do gabarito só volta ao navegador na resposta do registro, e só para `CORRECT`/`INCORRECT` (FR-013 exige informar a alternativa correta).
- `/questao` (M2) permanece como está: correção no cliente, sem persistência e sem `ENEM_ATTEMPTS_DB`.
- `NOT_VERIFIED` e `ANNULLED` são registrados (FR-013: a tentativa é preservada) e nunca contam como acerto nem erro.
- Rejeições (nada é gravado, a resposta informa o motivo e não mostra resultado): configuração ausente ou recusada; envio malformado; questão inexistente ou fora do catálogo utilizável; questão bloqueada por proveniência (`BLOCKED`); `question_file_sha256` diferente do SHA-256 atual do arquivo da questão (versão divergente); alternativa fora de A–E; `duration_ms` inválido; conflito de idempotência; catálogo não configurado ou ilegível.
- Versão da questão: `question_file_sha256` é o SHA-256 dos bytes do arquivo JSON curado lido pelo servidor. A página o envia junto com a resposta; o servidor recalcula no envio e rejeita divergência.
- Recursos de proveniência registrados: o recurso citado pelas evidências `CONTENT`/`PLACEMENT` e, quando o gabarito foi verificado, o recurso citado pela evidência `ANSWER_KEY`. Se a questão citar mais de um recurso distinto para conteúdo/posição ou para gabarito, o registro é rejeitado (as questões do M3 citam um de cada); ampliar isso exige decisão posterior.
- `duration_ms`: diferença de `performance.now()` entre a montagem do formulário no navegador e a confirmação, arredondada para inteiro. É estimativa informada pelo navegador, sujeita a imprecisão (aba em segundo plano, suspensão, relógio monotônico do cliente, tempo de leitura incluído) e não é auditável pelo servidor. Válido: inteiro seguro com `0 ≤ duration_ms ≤ 86 400 000` (24 h). Valor ausente, não inteiro, negativo ou acima do limite rejeita o envio; não há ajuste silencioso.
- `answered_at`: horário UTC do servidor no momento da gravação, ISO 8601 com milissegundos (`YYYY-MM-DDTHH:MM:SS.sssZ`); o horário do navegador não é usado.
- Áreas: a área curada (texto livre) é preservada como observada e mapeada para o código canônico (FR-017) por igualdade exata após `trim` e normalização Unicode NFC:
  - "Linguagens, Códigos e suas Tecnologias" → `LC`;
  - "Ciências Humanas e suas Tecnologias" → `CH`;
  - "Ciências da Natureza e suas Tecnologias" → `CN`;
  - "Matemática e suas Tecnologias" → `MT`.

  Qualquer outro texto (inclusive as áreas fictícias das fixtures do M3) fica com `area_code = NULL` e aparece como "área não mapeada". `RED` não se aplica a questões objetivas.

- Indicadores de `/desempenho`, calculados de forma determinística sobre todas as tentativas registradas, inclusive repetições da mesma questão:
  - total = número de tentativas;
  - acertos = `CORRECT`; erros = `INCORRECT`; não corrigidas = `NOT_VERIFIED` + `ANNULLED`;
  - taxa de acerto = acertos / (acertos + erros); com denominador 0, "sem dados".

  A taxa não representa domínio/mastery (FR-018) e a página diz isso. A divisão por área usa a ordem fixa `LC`, `CH`, `CN`, `MT` (áreas sem tentativa aparecem com "sem dados") e depois uma linha por texto de área não mapeada. A taxa é exibida em porcentagem com uma casa decimal, acompanhada da fração `acertos/(acertos + erros)`.

- Lista de tentativas em `/desempenho`: todas, da mais recente para a mais antiga (`answered_at` e `id` decrescentes), com questão, alternativa, resultado, horário UTC e duração. `/desempenho` apenas lê o banco de tentativas (somente leitura); sem `ENEM_ATTEMPTS_DB` informa "não configurado"; com arquivo ainda inexistente, mostra que não há tentativas, sem criá-lo.
- Esquema em código: DDL idempotente aplicada com better-sqlite3 e versionada por `PRAGMA user_version` (sem drizzle-kit); consultas tipadas com drizzle-orm, já instalado (ADR-0001). `user_version = 0` em banco vazio cria o esquema e define `1`; `user_version = 0` com objetos existentes, ou versão diferente de `1`, é recusado sem escrita.
- Regra de correção versionada: `evaluation_rule_version = "evaluateAnswer/v1"`, constante no domínio, gravada em cada linha.

## Modelo de dados

```sql
CREATE TABLE IF NOT EXISTS attempt (
  id                          INTEGER PRIMARY KEY AUTOINCREMENT,
  submission_id               TEXT    NOT NULL UNIQUE
    CHECK (length(submission_id) = 36 AND submission_id NOT GLOB '*[^0-9a-f-]*'),
  question_id                 TEXT    NOT NULL CHECK (length(question_id) > 0),   -- placementId do M3
  question_file_sha256        TEXT    NOT NULL
    CHECK (length(question_file_sha256) = 64 AND question_file_sha256 NOT GLOB '*[^0-9a-f]*'),
  question_format             TEXT    NOT NULL,                                   -- ex.: enem-rei/m2-question/v1
  area                        TEXT    NOT NULL,                                   -- texto curado, como observado
  area_code                   TEXT    CHECK (area_code IN ('LC', 'CH', 'CN', 'MT')),
  selected_label              TEXT    NOT NULL CHECK (selected_label IN ('A', 'B', 'C', 'D', 'E')),
  evaluation                  TEXT    NOT NULL
    CHECK (evaluation IN ('CORRECT', 'INCORRECT', 'NOT_VERIFIED', 'ANNULLED')),
  answer_key_status           TEXT    CHECK (answer_key_status IN ('VALID', 'ANNULLED', 'UNKNOWN')),
  answer_key_value            TEXT    CHECK (answer_key_value IN ('A', 'B', 'C', 'D', 'E')),
  answer_key_resource_id      TEXT,
  answer_key_resource_sha256  TEXT
    CHECK (answer_key_resource_sha256 IS NULL OR
           (length(answer_key_resource_sha256) = 64 AND answer_key_resource_sha256 NOT GLOB '*[^0-9a-f]*')),
  content_resource_sha256     TEXT    NOT NULL
    CHECK (length(content_resource_sha256) = 64 AND content_resource_sha256 NOT GLOB '*[^0-9a-f]*'),
  evaluation_rule_version     TEXT    NOT NULL,
  answered_at                 TEXT    NOT NULL CHECK (answered_at GLOB
    '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-9][0-9][0-9]Z'),
  duration_ms                 INTEGER NOT NULL CHECK (duration_ms BETWEEN 0 AND 86400000),

  -- Gabarito verificado: status, recurso e hash presentes juntos ou ausentes juntos.
  CHECK ((answer_key_status IS NULL) = (answer_key_resource_id IS NULL)),
  CHECK ((answer_key_resource_id IS NULL) = (answer_key_resource_sha256 IS NULL)),
  CHECK (answer_key_status IS NOT NULL OR answer_key_value IS NULL),
  -- Acerto/erro só com gabarito VALID resolvido, coerente com a alternativa.
  CHECK (evaluation NOT IN ('CORRECT', 'INCORRECT')
         OR (answer_key_status = 'VALID' AND answer_key_value IS NOT NULL)),
  CHECK (evaluation <> 'CORRECT' OR selected_label = answer_key_value),
  CHECK (evaluation <> 'INCORRECT' OR selected_label <> answer_key_value),
  CHECK (evaluation <> 'ANNULLED' OR answer_key_status = 'ANNULLED'),
  CHECK (evaluation <> 'NOT_VERIFIED'
         OR answer_key_status IS NULL
         OR answer_key_status = 'UNKNOWN'
         OR (answer_key_status = 'VALID' AND answer_key_value IS NULL))
) STRICT;

CREATE INDEX IF NOT EXISTS attempt_question_answered_at
  ON attempt (question_id, answered_at);

CREATE TRIGGER IF NOT EXISTS attempt_no_update BEFORE UPDATE ON attempt
BEGIN SELECT RAISE(ABORT, 'attempt é append-only'); END;

CREATE TRIGGER IF NOT EXISTS attempt_no_delete BEFORE DELETE ON attempt
BEGIN SELECT RAISE(ABORT, 'attempt é append-only'); END;

PRAGMA user_version = 1;
```

Notas:

- `answer_key_*` descrevem o gabarito efetivamente usado na correção, isto é, o verificado pela proveniência; ficam `NULL` quando a questão não tem gabarito verificado (`KEY_UNVERIFIED` ou `answer_key = null`). Isso atende à SPEC-003 FR-006 (a tentativa referencia o conteúdo apresentado, a alternativa e a observação de gabarito usada).
- O banco de tentativas guarda apenas referências (IDs e SHA-256) aos recursos da ingestão; o `ingestion.db` continua a autoridade dos metadados de recurso (SPEC-004 FR-019).
- A DDL é aplicada em uma transação; os gatilhos e os `CHECK` são a última barreira, e o domínio valida antes de gravar.

## Fluxo de envio

1. A página `/questoes/[id]` (servidor) carrega o catálogo e entrega ao formulário: alternativas, `question_id`, `question_file_sha256` e se há gabarito verificado. Não entrega o gabarito.
2. O formulário (cliente) gera `submission_id` e marca `performance.now()` ao montar. Confirmar fica indisponível até haver alternativa selecionada e durante o envio.
3. Ao confirmar, o cliente chama a Server Action com `submission_id`, `question_id`, `question_file_sha256`, `selected_label` e `duration_ms`.
4. O servidor valida o formato do envio (domínio puro).
5. Resolve e valida `ENEM_ATTEMPTS_DB`; abre o banco de tentativas (leitura e escrita) e garante o esquema.
6. Se `submission_id` já existe: payload igual devolve a tentativa gravada; payload diferente é rejeitado.
7. Carrega o catálogo com `loadCatalog` (verificação de proveniência somente leitura, ADR-0002) e localiza a entrada; inexistente, excluída ou `BLOCKED` é rejeitada.
8. Recalcula o SHA-256 do arquivo da questão e rejeita divergência.
9. Corrige com `evaluateAnswer` e o gabarito verificado; mapeia a área.
10. Grava a linha com `answered_at` do servidor, em transação; violação de unicidade de `submission_id` concorrente é tratada como no passo 6.
11. Devolve ao cliente: resultado, alternativa escolhida e, só para `CORRECT`/`INCORRECT`, a alternativa do gabarito. O formulário fica bloqueado; nova tentativa exige recarregar ou navegar.

## Arquivos previstos

Novos (nomes indicativos; a implementação pode ajustar sem mudar responsabilidades):

- `apps/web/src/domain/attempt.ts`: validação do envio, comparação de payload para idempotência, `evaluation_rule_version`, montagem do registro.
- `apps/web/src/domain/area.ts`: mapeamento de área para `LC`/`CH`/`CN`/`MT`.
- `apps/web/src/domain/performance.ts`: indicadores e divisão por área.
- `apps/web/src/lib/attempts/config.ts`: resolução e recusa de `ENEM_ATTEMPTS_DB`.
- `apps/web/src/lib/attempts/store.ts`: DDL, `user_version`, inserção idempotente e leitura.
- `apps/web/src/app/questoes/[id]/actions.ts`: Server Action de registro.
- `apps/web/src/app/questoes/[id]/attempt-form.tsx`: formulário do catálogo sem gabarito.
- `apps/web/src/app/desempenho/page.tsx`.
- `apps/web/tests/unit/` (attempt, area, performance, attempts-config, attempts-store) e `apps/web/tests/e2e/desempenho.spec.ts`.

Alterados:

- `apps/web/src/lib/m3/catalog.ts` (e, se necessário, `apps/web/src/domain/catalog.ts`): expor o SHA-256 dos bytes de cada arquivo.
- `apps/web/src/app/questoes/[id]/page.tsx` e `apps/web/src/app/questao/question-view.tsx`: usar o novo formulário no catálogo, mantendo `AnswerForm` do M2 em `/questao`.
- `apps/web/src/app/page.tsx`: link para `/desempenho`.
- `apps/web/playwright.config.ts` e `apps/web/tests/e2e/support/build_m2_fixture.py`: `ENEM_ATTEMPTS_DB` temporário por servidor (3100/3101) e servidor isolado para o M4 (ex.: 3102), com fixture e banco de tentativas próprios, recriados ao iniciar; a fixture do M4 inclui ao menos uma área oficial e uma não mapeada.
- `apps/web/tests/e2e/questoes.spec.ts`: ajustes estritamente necessários à correção no servidor, preservando as asserções do M3.
- `README.md` e `docs/validation.md`: documentação de uso e validação, na implementação.

## Critérios de aceitação

1. Critério principal: o usuário responde uma questão em `/questoes/[id]`, recarrega a aplicação e consulta em `/desempenho` a tentativa registrada (questão, alternativa, resultado, horário UTC, duração) e os indicadores atualizados.
2. Confirmar uma resposta grava exatamente uma linha com todos os campos do modelo; responder de novo a mesma questão após recarregar grava outra linha.
3. Reenviar o mesmo `submission_id` com o mesmo payload não cria linha e devolve a tentativa gravada; com payload diferente, é rejeitado sem gravar.
4. Com gabarito `VALID` verificado, o resultado é `CORRECT` ou `INCORRECT` e mostra a alternativa do gabarito; sem gabarito verificado, grava `NOT_VERIFIED`; anulada grava `ANNULLED`; nesses dois casos não há acerto nem erro.
5. O HTML e o payload RSC de `/questoes/[id]` antes da confirmação não contêm o gabarito (nem o objeto `answer_key` nem o campo `published_value`).
6. São rejeitados sem gravar: questão inexistente ou excluída, questão `BLOCKED`, `question_file_sha256` divergente, alternativa fora de A–E, `duration_ms` inválido (não inteiro, negativo, acima de 86 400 000 ou ausente) e `submission_id` malformado.
7. Sem `ENEM_ATTEMPTS_DB`, a confirmação mostra erro de configuração e nenhum banco é criado ou escrito; caminho igual ao `ingestion.db` ou dentro de `raw` é recusado.
8. `UPDATE` e `DELETE` em `attempt` falham; os `CHECK` impedem `CORRECT`/`INCORRECT` sem gabarito `VALID` resolvido.
9. Banco com `user_version` desconhecido, ou não vazio com `user_version = 0`, é recusado sem escrita; abrir duas vezes um banco já criado não altera o esquema.
10. `/desempenho` mostra total, acertos, erros, não corrigidas e taxa = acertos/(acertos + erros), com "sem dados" quando o denominador é 0, além da divisão por área (`LC`, `CH`, `CN`, `MT` e não mapeadas), e informa que a taxa não é domínio.
11. Testes unitários cobrem: mapeamento de área (quatro nomes oficiais, espaços extras, texto não reconhecido), indicadores (vazio, só não corrigidas, repetições, mistura de áreas), validação do envio e dos limites de `duration_ms`, idempotência e recusa de configuração.
12. `/questao` continua sem persistência: responder nela não cria tentativa, e seus e2e permanecem inalterados e passando.
13. Os demais critérios do M3 continuam válidos. O critério 5 do M3 passa a valer só para o formulário: navegar ou recarregar não restaura a resposta, mas a tentativa confirmada fica registrada.
14. Testes unitários e e2e usam somente dados sintéticos; o e2e do M4 usa servidor, fixture e banco de tentativas isolados.
15. Verificação manual com dados reais: responder uma das três questões do M3, recarregar e conferir a tentativa e os indicadores em `/desempenho`.
16. Validações do `AGENTS.md` passam; `git status` não mostra banco de tentativas, banco de ingestão, PDF nem transcrição real.

## Riscos

- `duration_ms` é informado pelo cliente: impreciso e manipulável; serve só como estimativa.
- Gabarito no servidor reduz, mas não elimina, a exposição: após a confirmação a alternativa correta é exibida (FR-013).
- Acoplamento ao catálogo do M3: editar o arquivo de uma questão muda seu SHA-256 e rejeita envios de páginas abertas antes da edição; as tentativas antigas mantêm o hash antigo.
- `question_id` identifica a ocorrência no caderno, não a Question canônica da SPEC-003; agregações futuras entre cores exigirão mapeamento.
- Texto de área fora dos quatro nomes oficiais fica não mapeado; não há correspondência aproximada.
- SQLite local: um único processo de escrita, sem backup automático; perda do arquivo perde o histórico.
- Server Actions são endpoints HTTP: dependem da proteção de origem do Next.js e do servidor somente em `127.0.0.1`.

## Pré-requisitos

- Gate de segurança: antes de implementar a escrita por Server Action, avaliar e corrigir a vulnerabilidade crítica conhecida do `next` 16.3.5 (registrada em `docs/m3-catalogo-questoes.md`, seção Segurança; correção em 16.4.0 ou superior), como tarefa separada e intencional de atualização de dependências, com lockfile e validações. Sem essa correção, a implementação do M4 não começa.
- Ambiente e dados do M3 funcionando (três questões reais verificadas, `ENEM_CATALOG_DIR`, `ENEM_DATA_ROOT`).
- `AGENTS.md` autorizando o M4 conforme este documento e o ADR-0003.
