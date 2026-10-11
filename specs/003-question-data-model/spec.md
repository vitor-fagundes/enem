# Feature Specification: Question Data Model

**Feature Branch**: `N/A (retrospective migration; no branch created)`

**Created**: 2026-09-18

**Status**: Draft

**Input**: User description: "Migrar retrospectivamente `specs/003-question-data-model.md` para o formato nativo do GitHub Spec Kit, preservando integralmente seu significado, sem implementar código, sem alterar as demais specs e sem apagar o legado."

## Migration Provenance

Este artefato foi reconstruído retrospectivamente durante a migração para o GitHub Spec Kit. Ele expressa no formato atual o modelo de domínio de questões originalmente registrado em `specs/003-question-data-model.md`; não representa uma nova feature, não declara requisitos como já implementados e não autoriza implementação neste incremento. Esta especificação é uma definição de domínio foundational: estabelece o modelo canônico que a ingestão e demais camadas devem respeitar. O documento legado permanece preservado como fonte histórica da migração.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Representar questões do ENEM com estrutura contextualizada (Priority: P1)

Como modelo de domínio, preciso representar questões históricas do ENEM com edição, aplicação, caderno lógico, placement, revisões de conteúdo, alternativas e gabarito para que a ingestão e o produto possam trabalhar com dados contextualizados e rastreáveis.

**Why this priority**: Sem representação estruturada de questões e seus contextos, nenhum ciclo de estudo, correção ou diagnóstico pode funcionar.

**Independent Test**: Pode ser testada representando uma questão que aparece em dois cadernos com placements distintos, uma alternativa visual sem texto, e contextos de numeração inglês e espanhol no mesmo caderno.

**Acceptance Scenarios**:

1. **Given** evidência suficiente de identidade de Q1 em dois cadernos, **When** os placements são registrados, **Then** existe 1 Question e 2 QuestionPlacements, cada um com seu caderno, contexto de numeração e evidência preservados. Sem prova de identidade, os registros permanecem separados.
2. **Given** um caderno lógico B1 com opções inglesa e espanhola, **When** os placements são registrados, **Then** coexistem `(B1, ENGLISH, 1)` e `(B1, SPANISH, 1)` sem colisão, sem duplicar o caderno lógico por idioma.
3. **Given** uma alternativa da revisão R1 contendo apenas gráfico e nenhum texto, **When** ela é registrada, **Then** possui `text = null`, índice canônico único em R1 e asset vinculado, com referência na fonte. A alternativa continua válida.

---

### User Story 2 - Preservar gabarito e anulação com contexto e evidência (Priority: P1)

Como modelo de domínio, preciso representar observações de gabarito oficiais, anulações contextualizadas, retificações e resolução de alternativas para que a correção respeite a situação oficial de cada placement.

**Why this priority**: A correção depende diretamente da observação de gabarito; sem contexto, anulação e retificação, o produto não pode corrigir tentativas de forma confiável.

**Independent Test**: Pode ser testada registrando um gabarito sem alternativa resolvida, uma questão anulada e uma retificação que preserva o histórico.

**Acceptance Scenarios**:

1. **Given** uma fonte que informa questão 42 → C para o placement P42 sem alternativas extraídas, **When** a observação é registrada, **Then** possui `published_value = C`, `status = VALID`, `resolved_alternative_id = null` e `source_resource_id` da fonte do gabarito. `VALID` não significa que a correção automática já seja possível.
2. **Given** uma fonte oficial que informa anulação para o placement P1, **When** a observação é registrada, **Then** possui `status = ANNULLED`, valor publicado quando disponível e fonte. A questão permanece armazenada; outros placements não são automaticamente anulados; P1 não pode ser tratado como erro do usuário.
3. **Given** V1 ingerido para P42 e V2 publicado como retificação oficial, **When** V2 é registrado, **Then** V1 permanece; V2 registra o mesmo placement, sua fonte e `supersedes_id = V1`. Sem evidência de retificação, a divergência é preservada sem concluir supersessão pela ordem de coleta.

---

### User Story 3 - Classificar questões por habilidades e tópicos rastreáveis (Priority: P2)

Como modelo de domínio, preciso representar associações entre questões e habilidades oficiais ou tópicos analíticos, com execuções de classificação rastreáveis, para que inferências permaneçam distinguíveis de fatos oficiais.

**Why this priority**: A priorização de estudo depende de classificação temática; a rastreabilidade garante que inferências não sejam apresentadas como fatos.

**Independent Test**: Pode ser testada classificando uma questão por LLM, verificando que a associação permanece inferida após revisão humana, e representando uma questão sem habilidades conhecidas.

**Acceptance Scenarios**:

1. **Given** LLM classifica Q1 com tópico principal porcentagem e confiança 0.91, **When** a classificação é registrada, **Then** a associação é `INFERRED`, com conjunto versionado e referência a ClassificationRun com metadados LLM. Pode alimentar analytics antes de revisão humana, preservando origem e run.
2. **Given** uma questão sem habilidade oficial conhecida, **When** sua representação é consultada, **Then** `QuestionSkill` é vazio; isso não é erro estrutural. A ausência de tópicos também é permitida sem conjunto temático completo.
3. **Given** LLM produz associação INFERRED ligada ao run C1 e um humano aprova, **When** a revisão é registrada, **Then** permanece `INFERRED` com `review_status = REVIEWED`. Preservar run, confiança original e rastreabilidade. Aprovação não inventa evidência oficial nem confiança 1.

---

### User Story 4 - Preservar dados parciais e proveniência sem fabricação (Priority: P2)

Como modelo de domínio, preciso representar dados parciais, múltiplos identificadores externos e evidências de fontes distintas para que registros incompletos sejam preservados sem fabricação de valores.

**Why this priority**: Dados parciais são inevitáveis durante ingestão; descartá-los ou inventar valores compromete a integridade do modelo.

**Independent Test**: Pode ser testada registrando uma questão com texto e gabarito de fontes diferentes, dados parciais sem valores fabricados e identificadores externos com namespace.

**Acceptance Scenarios**:

1. **Given** texto de Q1 extraído do recurso R-TEXTO e gabarito de R-GABARITO, **When** ambos são registrados, **Then** `QuestionContentRevision.source_resource_id = R-TEXTO` e `AnswerKeyObservation.source_resource_id = R-GABARITO`. Cada fato preserva sua fonte e localizador separadamente.
2. **Given** uma questão com `statement = null` porque o conteúdo não foi extraído, **When** ela é registrada, **Then** o registro permanece com referência ao recurso original e limitações de extração explícitas. OCR incorreto MUST NOT ser apresentado como texto oficial.
3. **Given** uma questão com dois identificadores externos em namespaces diferentes, **When** eles são registrados, **Then** cada um preserva namespace/escopo, valor e evidência. Valores iguais em namespaces distintos não provam equivalência.

### Edge Cases

- Contexto de numeração desconhecido (`UNKNOWN`) não autoriza fundir observações potencialmente pertencentes a opções diferentes; a colisão deve preservar evidências até desambiguação.
- Uma revisão de conteúdo já referenciada é imutável; correções geram nova revisão preservando a anterior e suas alternativas/assets.
- Observações de gabarito conflitantes não são conciliadas silenciosamente; ambas permanecem registradas com suas fontes.
- Classificações inferidas podem alimentar analytics antes de revisão humana, preservando `INFERRED`, confiança e run. Não misturar propostas concorrentes silenciosamente.
- Uma coleção vazia de assets pode significar que não foram extraídos, não que a questão não tem imagens.
- Falta de referência estrutural MUST NOT gerar entidades órfãs; preservar a observação na ingestão até resolução.
- Desempenho elevado em items difíceis classificados automaticamente não autoriza tratar a classificação como oficial.
- Representação normal, ampliada ou de acessibilidade é recurso associado ao caderno lógico, não outro caderno.

## Requirements *(mandatory)*

### Scope Boundaries

Esta especificação define o modelo canônico de domínio para representar questões históricas do ENEM, independentemente de formato de dataset. Ela cobre edições, aplicações, áreas, cadernos lógicos, questões, placements, revisões de conteúdo, alternativas, observações de gabarito, recursos visuais, competências, habilidades, taxonomia analítica, classificações e proveniência.

O primeiro corpus normalizado deve priorizar **ENEM 2017–2025, aplicação regular, representação impressa padrão**. Essa é uma prioridade de implementação, não uma limitação permanente do domínio.

A presente migração produz somente documentação: não implementa migrations, ETL, UI, schema físico final ou stack nova. A governança de dados pertence à SPEC-002. O contrato de aquisição e ingestão pertence à SPEC-004. Esta especificação define o modelo de domínio que ambas devem respeitar.

As categorias de campos aplicáveis a todas as entidades são:

| Categoria | Contrato |
|-----------|----------|
| Estrutural obrigatório | Deve existir com valor válido; referências não podem ser órfãs ou fabricadas |
| Existente, nullable | O campo faz parte do contrato, mas aceita `null` quando desconhecido |
| Opcional | Pode ser omitido; ausência não autoriza inferir um valor |
| Obrigatório condicional | Torna-se obrigatório na condição explicitada |

Registros parciais não precisam fingir completude. Quando faltarem referências estruturais, a observação original MUST ser preservada para resolução posterior, sem inventar identidades ou descartar dados. Não usar string vazia como substituto indiscriminado de ausência. Datas usam ISO 8601; horários relevantes em UTC; não inventar horário para data documental.

Estão fora do escopo desta especificação: tentativas do usuário, recorreção de histórico, mastery, revisão de estudo, priority score, sessões, redação, recomendação, embeddings, RAG, autenticação, LLM integrations, ingestão concreta, migrations, UI, schema físico final, AST genérica, CMS, thresholds de classificação e vocabulário temático completo.

### Functional Requirements

#### Exam Structure

- **FR-001**: ExamEdition MUST representar a edição anual nominal do ENEM. Campos estruturais: `id`, `year`. Campo nullable: `name`. O ano nominal é independente das datas concretas de realização; a identidade da edição MUST NOT ser derivada de datas de aplicação.
- **FR-002**: ExamApplication MUST representar um agrupamento de aplicação dentro de uma edição, podendo abranger múltiplos dias. Campos estruturais: `id`, `edition_id`. Campos nullable: `application_type`, `official_name`. O tipo é classificação canônica (regular, reaplicação, PPL como exemplos conceituais), não identidade; uma categoria não identificada MUST NOT receber tipo inventado. Cada aplicação pertence a exatamente uma edição. Datas concretas devem poder ser associadas ao dia/caderno correspondente sem entidade de calendário obrigatória.
- **FR-003**: KnowledgeArea MUST usar os identificadores canônicos `LC`, `CH`, `CN`, `MT` e `RED`. Nomes livres MUST NOT substituir esses identificadores. `RED` existe para consistência e não obriga redação a usar o modelo de questão objetiva.
- **FR-004**: ExamBooklet MUST representar o caderno lógico de uma aplicação. Campos estruturais: `id`, `application_id`. Campos nullable: `booklet_code`, `official_name`, `color`, `day`, `administration_date`. `day` identifica o dia dentro da aplicação, não data de calendário; `administration_date` registra a data concreta quando conhecida, com evidência. Representações normal, ampliada, superampliada e de acessibilidade são recursos associados ao caderno lógico, sem entidade obrigatória de representação. Uma representação física não cria automaticamente outro caderno nem prova equivalência de conteúdo. O caderno não tem idioma obrigatório único; opções inglesa e espanhola MAY coexistir.

#### Question Identity and Content

- **FR-005**: Question MUST representar o item avaliativo canônico. Campos estruturais: `id`. Campo nullable: `area_id`. A identidade interna é independente de posição, página, cor e existência de código externo. Não há `Question.status` genérico obrigatório. Uma questão MAY possuir zero ou mais identificadores externos, cada um com namespace/escopo, valor e evidência de fonte; identificadores MUST NOT ser fabricados. Valores iguais em namespaces diferentes não provam equivalência automaticamente.
- **FR-006**: QuestionContentRevision MUST representar uma revisão imutável do conteúdo extraído. Campos estruturais: `id`, `question_id`, `source_resource_id`, `extraction_method`, `created_at`. Campos nullable: `statement`, `normalized_statement`, `source_locator`. Idioma(s) do conteúdo MAY ser registrado quando conhecido. `extraction_method` MUST identificar método e versão. `normalized_statement` MUST NOT sobrescrever `statement`. Texto MAY ser `null` quando não extraível; o recurso original continua referenciado. Correções geram nova revisão preservando a anterior; revisão já referenciada MUST NOT ser alterada silenciosamente; o conjunto de alternativas e os vínculos de assets associados ao conteúdo também MUST permanecer recuperáveis nessa revisão. A conexão entre revisão e ocorrência/representação MUST preservar o placement e o recurso de origem aplicáveis, sem presumir que toda revisão sirva para todos os placements. Uma questão MAY ter zero revisões (somente metadados/gabarito conhecidos) ou várias de fontes/extrações diferentes. Futuras tentativas MUST poder referenciar qual revisão foi apresentada, a alternativa correspondente e a observação de gabarito utilizada; esta spec preserva essa possibilidade, sem definir nem implementar `Attempt` ou sua política de recorreção.
- **FR-007**: A política de deduplicação de identidade MUST ser conservadora: fundir registros somente com evidência suficiente; na dúvida, manter separados. Similaridade textual sozinha MUST NOT autorizar fusão. SHA-256 de arquivo bruto verifica o recurso, não a identidade da questão. Fingerprint de texto normalizado é dado derivado com método/versão, não prova de identidade do item. Fusão MUST preservar todos os identificadores, fontes, placements, revisões e referências históricas. Identificadores previamente referenciados MUST continuar resolvíveis.

#### Placement and Alternatives

- **FR-008**: QuestionPlacement MUST representar a ocorrência de uma questão em um caderno lógico. Campos estruturais: `id`, `question_id`, `booklet_id`, `numbering_context`. Campos nullable: `question_number`, `position`. Campo opcional: `display_label`. `numbering_context` MUST distinguir, no mínimo, os conceitos `COMMON`, `ENGLISH`, `SPANISH` e `UNKNOWN` (sem impor enum físico fechado). Invariante: `(booklet_id, numbering_context, question_number)` MUST ser único. `UNKNOWN` MUST NOT autorizar fusão de observações potencialmente distintas. Um placement pertence exatamente a um caderno e a uma questão. Páginas e localizadores pertencem à evidência sobre recurso concreto, não ao placement abstrato.
- **FR-009**: Alternative MUST representar uma alternativa identificável dentro de uma revisão de conteúdo. Campos estruturais: `id`, `content_revision_id`, `canonical_index`. Campo nullable: `text`. Campos opcionais: `normalized_text` com método/versão, `metadata` rastreável. `canonical_index` é único dentro da revisão e estável; índices 0–4 não equivalem automaticamente a A–E. Uma alternativa MAY ter `text = null` (conteúdo visual). Alternativas MUST NOT ser inventadas para completar quantidade esperada. Letra publicada só pode ser resolvida por correspondência explícita compatível com placement, revisão e evidência.
- **FR-010**: O contrato MUST permitir registrar correspondência entre rótulo publicado e alternativa canônica (AlternativePlacement). A entidade MUST NOT ser obrigatória agora. Quando registrada: `question_placement_id`, `alternative_id`, `display_label` e evidência são estruturais; `display_position` é nullable. A revisão MUST ser recuperável pela alternativa e compatível com a questão do placement. Em um mesmo contexto de apresentação e revisão, um rótulo MUST NOT resolver ambiguamente para alternativas distintas; divergências entre recursos MUST permanecer explícitas. Posição interna MUST NOT ser convertida em letra por premissa não documentada. A correspondência MUST NOT ser exigida para preservar gabarito não resolvido.

#### Answer Keys

- **FR-011**: AnswerKeyObservation MUST representar observação publicada por fonte oficial, vinculada a um QuestionPlacement. Campos estruturais: `id`, `question_placement_id`, `source_resource_id`, `status`. Campos nullable: `published_value`, `resolved_alternative_id`, `supersedes_id`, `source_locator`, `published_at`. `status` inclui `VALID`, `ANNULLED`, `UNKNOWN`; `VALID` significa situação oficial de resposta válida, não que a alternativa esteja resolvida ou que a correção automática seja possível. `published_value` preserva letra/marcador publicado; aceita `null` somente quando não conhecido/extraível; a fonte e a limitação de extração MUST permanecer rastreáveis. `published_at` MUST NOT receber a data de coleta como substituta; a coleta pertence à proveniência do recurso. MAY ter `published_value` sem `resolved_alternative_id`. Resolução MUST corresponder à questão/revisão e contexto, com evidência; MUST NOT resolver apenas por índice canônico. Múltiplas observações por placement são permitidas. Retificação gera nova observação; `supersedes_id` referencia observação anterior do mesmo placement, sem ciclos ou autorreferência. Se a resolução interna for obtida ou corrigida depois, MUST preservar a evidência publicada e o histórico de resolução, especialmente quando já referenciados. Enriquecimento interno MUST NOT ser apresentado como retificação oficial nem reutilizar `supersedes_id` para simular uma publicação inexistente. Anulação MUST NOT propagar automaticamente a todos os placements da questão. Observações conflitantes MUST NOT ser conciliadas silenciosamente. Situações desconhecidas, conflitantes ou não resolvidas também MUST NOT autorizar correção automática como erro.

#### Assets

- **FR-012**: QuestionAsset MUST vincular-se a exatamente um alvo (conteúdo da revisão OU alternativa) e a `source_resource_id`. Campos nullable: `order`, `asset_type`, `source_locator`. Campos opcionais: `local_path`, checksum do recorte quando materializado. Ordem relativa ao alvo MUST ser preservada quando conhecida; tipo e localizador desconhecidos MUST NOT ser inventados. Coleção vazia MAY significar não extraídos, não ausentes. Não é obrigatório extrair assets no primeiro pipeline. `local_path` e checksum de recorte MUST NOT ser exigidos antes de materialização; SHA-256 do arquivo bruto ingerido continua exigido pela SPEC-002.

#### Official Taxonomy

- **FR-013**: OfficialCompetency MUST representar uma competência da Matriz de Referência oficial. Campos estruturais: `id`, `area_id`, `official_code`, `matrix_version`, `source_resource_id`. Campos nullable: `name`, `description`. O código MUST ser interpretado no contexto da área e versão da matriz; sem esses vínculos, preservar a observação sem fabricar competência normalizada.
- **FR-014**: OfficialSkill MUST representar uma habilidade da matriz oficial vinculada à competência. Campos estruturais: `id`, `competency_id`, `official_code`, `source_resource_id`. Campo nullable: `description`. Área e versão da matriz são determinadas pela competência. Se `matrix_version` for materializado na habilidade, MUST coincidir com o da competência. Definições históricas MUST NOT ser sobrescritas quando a matriz mudar. Uma habilidade oficial não prova que a associação questão–habilidade também seja oficial.

#### Classification

- **FR-015**: ClassificationRun MUST representar uma execução de classificação. Campos estruturais: `id`, `method`, `method_version`, `input_hash`, `timestamp`, configuração relevante. Campos condicionais para LLM: `provider`, `model`, `prompt_version`. Metadados completos de LLM são registrados nesta execução e referenciados pelas associações, não repetidos em cada associação. `input_hash` MUST identificar inputs efetivamente usados; referências aos inputs e revisões necessárias ao lineage MUST ser preservadas. Se a execução processar várias questões, o hash e as referências MUST permitir identificar esse conjunto, não fingir um input individual. A identidade da execução não é a versão do algoritmo; mesmo método/versão MAY ter várias execuções. `classification_version` nas associações identifica a versão do procedimento/classificação, não substitui `classification_run_id` nem a identidade do conjunto de resultados. Classificação humana MAY registrar sem metadados LLM. Associação oficial extraída de fonte MUST NOT requerer execução LLM.
- **FR-016**: QuestionSkill MUST representar relação muitos-para-muitos entre questão e habilidade. Campos estruturais: `question_id`, `skill_id`, `relationship_type`, `classified_by`, `classification_version`, `review_status`, `created_at`. Campos nullable: `confidence`, `classification_run_id`. Campos condicionais obrigatórios: evidência oficial específica quando `relationship_type = OFFICIAL`; referência ao run para classificação automática. `relationship_type` distingue `OFFICIAL` (exige fonte que comprove a associação, não apenas que a habilidade exista na matriz; a evidência pode ser diferente da fonte do conteúdo da questão) e `INFERRED`. Inferência revisada permanece `INFERRED`; aprovação humana MAY produzir `INFERRED + REVIEWED`. `review_status` registra revisão da associação, nunca oficialidade ou estado do parser. `confidence`, quando disponível, entre 0 e 1; `null` não significa zero; origem oficial MUST NOT inventar confiança 1. Propostas, execuções e revisões anteriores MUST continuar rastreáveis. Associação inferida MUST NOT sobrescrever evidência oficial nem outra proposta silenciosamente. Mudanças na associação MUST preservar a classificação e o run que as originaram.
- **FR-017**: Topic MUST representar a taxonomia analítica do projeto, distinta de competências e habilidades oficiais. Campos estruturais: `id`, `name`, `taxonomy_version`. Campos nullable: `parent_id`, `area_id`. Hierarquia MUST ser acíclica e coerente com versão. Área utiliza catálogo canônico. Tópico fictício MUST NOT ser criado para preencher classificação ausente.
- **FR-018**: QuestionTopic MUST representar relação entre questão e taxonomia analítica. Campos estruturais: `question_id`, `topic_id`, `classification_set_id`, `role`, `relationship_type`, `classified_by`, `classification_version`, `review_status`. Campos nullable: `confidence`, `classification_run_id`. Campos condicionais obrigatórios: referência ao run para classificação automática; evidência oficial específica se uma associação for declarada `OFFICIAL`. `role` distingue `PRIMARY` e `SECONDARY`. Origem, confiança, evidência e revisão seguem FR-016. A taxonomia continua analítica mesmo que exista evidência oficial para uma associação específica; usar um documento oficial como input de inferência não torna seu resultado oficial. `classification_set_id` identifica conjunto de resultados por questão, com indicação explícita de completude. MUST NOT confundir conjunto, execução, versão do procedimento e versão da taxonomia: uma execução pode classificar várias questões, e propostas concorrentes MUST coexistir em conjuntos distintos. Cardinalidade aprovada:

  | Situação | Tópicos |
  |----------|---------|
  | Questão não classificada | Zero tópicos permitidos |
  | Conjunto candidato/parcial | Zero ou um PRIMARY, zero ou mais SECONDARY |
  | Conjunto declarado completo | Exatamente um PRIMARY, zero ou mais SECONDARY |

  Mesmo tópico MUST NOT ocupar PRIMARY e SECONDARY no mesmo conjunto. Completude não significa revisão humana nem origem oficial. Inferências MAY alimentar analytics antes de revisão, preservando `INFERRED`, confiança e run. A análise MUST explicitar os conjuntos e versões utilizados, sem misturar propostas concorrentes silenciosamente. Esta cardinalidade é a reconciliação aprovada da SPEC-002 §13 com ingestão parcial.

#### Auxiliary Concepts

- **FR-019**: Dificuldade MUST NOT ser tratada como propriedade factual simples de Question. Distinguir dificuldade oficial, derivada e percebida pelo usuário. Sem informação oficial, MUST NOT atribuir nomenclatura oficial à estimativa. Observação derivada exige método, versão, inputs, valor e data. Não criar entidade obrigatória nesta etapa. A SPEC-001 proíbe apresentar aproximação como TRI real.
- **FR-020**: Metadados adicionais de questão são opcionais e MUST NOT substituir campos de domínio definidos. Características inferidas (cálculo, gráfico, fórmula) MUST possuir origem e classificação. Ausência de metadado MUST NOT equivaler a `false`. Conteúdo de IA MUST permanecer identificado.

#### Cross-cutting Domain Rules

- **FR-021**: Conteúdo textual MUST preservar separadamente: recurso original imutável em raw, conteúdo extraído em revisão e normalização derivada com método/versão. Extração pode conter erros; origem oficial não valida automaticamente OCR. Correção de extração produz nova revisão. MUST NOT sobrescrever original, extração anterior ou normalização já referenciada.
- **FR-022**: O mesmo caderno lógico MAY conter questões de opções distintas com a mesma numeração; `numbering_context` no placement distingue essas ocorrências. Opção inglesa e espanhola são questões distintas salvo evidência suficiente de identidade; compartilhar número não é evidência. Idioma do conteúdo, opção do participante e contexto de numeração são conceitos distintos.
- **FR-023**: Questão anulada permanece armazenada com conteúdo, fontes e histórico. Anulação em `AnswerKeyObservation.status`, no placement correspondente. MUST NOT excluir a questão, propagar automaticamente a outros placements nem tratar como erro do usuário. Métricas e recorreção estão fora desta spec.
- **FR-024**: `statement = null` e `Alternative.text = null` são permitidos. OCR incorreto MUST NOT ser apresentado como texto oficial validado. Área, número, data, tipo, ordem e localizador desconhecidos seguem a nulabilidade das respectivas seções. MUST NOT fabricar valores nem usar ausência de extração como prova de ausência do conteúdo. Falta de referência estrutural MUST NOT gerar entidades órfãs; preservar a observação para resolução posterior. Existência canônica, completude de conteúdo e aptidão para apresentação/correção são conceitos diferentes.
- **FR-025**: Cada fato externo relevante MUST possuir evidência apropriada. A fonte que originou Question não comprova automaticamente todos os atributos. MUST preservar separadamente evidências de: conteúdo e extração; placement e contexto de numeração; gabarito e retificação; associação oficial questão–habilidade; identificador externo; edição, aplicação, caderno e datas. Um fato MAY ter várias evidências; fontes diferentes MAY apoiar fatos diferentes da mesma questão. `SourceResource` identifica recurso concreto versionado, não sinônimo do catálogo `source_id`. Evidências divergentes MUST NOT ser sobrescritas silenciosamente.
- **FR-026**: MUST NOT existir estado genérico obrigatório de Question. Distinguir: estado de ETL, qualidade/completude da extração, revisão humana da classificação, situação oficial do gabarito e elegibilidade pedagógica. São dimensões diferentes. Dados de ETL MUST NOT determinar identidade, oficialidade ou validade pedagógica.
- **FR-027**: MUST NOT descartar dados por ausência de tópico/habilidade, presença de assets, anulação, incompletude ou falha de classificação. Preferir registro parcial com limitação explícita à perda silenciosa. Fusão, correção e supersessão MUST preservar fontes e referências anteriores. Imutabilidade de conteúdo e raw MUST NOT exigir event sourcing ou arquitetura distribuída.

#### Conceptual Model

- **FR-028**: O modelo conceitual e as cardinalidades MUST ser respeitados conforme o diagrama abaixo. O caderno lógico MAY estar associado a vários SourceResources sem entidade obrigatória de representação. Revisões e correspondências de alternativas MUST preservar vínculo com placement/recurso aplicável. O diagrama não determina tabelas nem obriga registro parcial a possuir filhos ainda não extraídos.

```text
ExamEdition 1 ── N ExamApplication 1 ── N ExamBooklet
ExamBooklet 1 ── N QuestionPlacement N ── 1 Question
QuestionPlacement 1 ── 0..N AnswerKeyObservation
Question 1 ── 0..N QuestionContentRevision
QuestionContentRevision 1 ── 0..N Alternative
QuestionContentRevision ou Alternative ── 0..N QuestionAsset
Question N ── N OfficialSkill (via QuestionSkill)
OfficialSkill N ── 1 OfficialCompetency
Question N ── N Topic (via QuestionTopic, por conjunto)
QuestionSkill / QuestionTopic ── ClassificationRun quando automático
```

- **FR-029**: Cada conceito MUST NOT exigir tabela independente. Coleções de identificadores, alternativas, assets, conjuntos de classificação e runs MAY ter representação física simplificada desde que mantenham integridade, proveniência e referências históricas. UUID vs hash, schema final, formato de alternativas/assets e representação física permanecem adiados. MUST NOT introduzir AST genérica, CMS, RAG, autenticação, recomendação ou novas tecnologias. A stack da SPEC-001 (ADR-0001) permanece inalterada.

### Domain Invariants

| ID | Invariante |
|----|------------|
| INV-001 | Número da questão não identifica globalmente uma questão. |
| INV-002 | Uma questão pode aparecer em mais de um caderno/aplicação quando a identidade for comprovada; similaridade não basta para fusão. |
| INV-003 | Um placement pertence exatamente a um caderno e a uma questão, com referências válidas. |
| INV-004 | `(booklet_id, numbering_context, question_number)` deve ser único. Dados parciais e contexto desconhecido seguem FR-008, sem inventar números ou fundir colisões não resolvidas. |
| INV-005 | Inferência revisada continua `INFERRED`; revisão humana não a transforma em `OFFICIAL`. |
| INV-006 | Normalização não sobrescreve extração, inclusive de alternativas, nem o recurso original. |
| INV-007 | Anulação contextualizada permanece armazenada e não é propagada automaticamente a todos os placements da questão. |
| INV-008 | Ausência de classificação não invalida a existência da questão. |
| INV-009 | Dados derivados preservam método/versão, inputs e parâmetros relevantes. Execuções LLM registram os metadados da SPEC-002 §20 em ClassificationRun. |
| INV-010 | Identificadores externos não são fabricados; cada um possui namespace/escopo e evidência. Igualdade entre namespaces diferentes não prova equivalência. |
| INV-011 | Aplicação pode possuir múltiplos dias. Datas concretas do dia/caderno não redefinem o ano nominal da edição. |
| INV-012 | Representação física não redefine automaticamente identidade do caderno lógico nem prova identidade de questões adaptadas. |
| INV-013 | Observação de gabarito pode existir com valor publicado e sem alternativa canônica resolvida. Resolução existente deve corresponder à questão/revisão e contexto aplicáveis. |
| INV-014 | Retificação preserva observações anteriores. Supersessão oficial é evidenciada, restrita ao mesmo placement e sem ciclos; coleta posterior não basta. |
| INV-015 | Revisão de conteúdo referenciada é imutável; correções preservam a versão anterior e suas alternativas/assets recuperáveis. |
| INV-016 | Dados de ETL não determinam identidade, oficialidade ou validade pedagógica. |
| INV-017 | Confiança ausente não significa zero. Quando disponível, fica entre 0 e 1. |
| INV-018 | Associação oficial exige evidência oficial específica da associação, não apenas da existência de uma habilidade ou do documento usado como input. |
| INV-019 | Conjunto temático completo possui exatamente um PRIMARY; candidato/parcial possui zero ou um. Mesmo tópico não pode ser PRIMARY e SECONDARY no mesmo conjunto da questão. |
| INV-020 | Índice canônico de alternativa é único na revisão e não equivale automaticamente a A–E. Alternativa visual sem texto continua representável. |
| INV-021 | Asset pertence ao conteúdo de uma revisão ou a uma alternativa, com origem e ordem quando conhecida. Não exigir materialização para preservar sua referência. |
| INV-022 | Fatos distintos podem possuir fontes distintas. Fusão não perde evidências, revisões, placements ou resolução de referências históricas. |
| INV-023 | Habilidade pertence à competência da mesma matriz/área; códigos oficiais são interpretados em seu escopo versionado. Hierarquia de tópicos é acíclica e coerente com versão. |
| INV-024 | Inferências podem alimentar analytics antes de revisão, mas preservam origem, classificação/run e confiança disponível. Métricas continuam determinísticas e identificam conjuntos/versões usados; esta spec não fixa thresholds. |

### Requirement Acceptance Traceability

| Requirement | Acceptance evidence |
|-------------|---------------------|
| FR-001–FR-004 | User Story 1 scenarios 1–2; edition/application/booklet structure, multi-day, English/Spanish coexistence |
| FR-005–FR-007 | User Story 4 scenarios 2–3; identity, external identifiers, conservative deduplication |
| FR-008–FR-010 | User Story 1 scenarios 1–3; placement uniqueness, numbering context, visual alternatives, label correspondence |
| FR-011 | User Story 2 scenarios 1–3; answer key observation, annulment, retification, published value without resolution |
| FR-012 | User Story 1 scenario 3; assets linked to revision or alternative, optional materialization |
| FR-013–FR-014 | User Story 3 scenario 2; versioned competency/skill, official code in context |
| FR-015–FR-018 | User Story 3 scenarios 1–3; classification run, inferred vs official, topic cardinality, review status |
| FR-019–FR-020 | Difficulty distinction and optional metadata; no fabrication of absence |
| FR-021–FR-027 | User Stories 2 and 4; content preservation, foreign language, annulment, partial data, provenance, state separation, preservation |
| FR-028–FR-029 | Conceptual model and cardinalalities; domain/storage separation |
| INV-001–INV-024 | All acceptance scenarios; cross-cutting invariant verification |

### Key Entities *(include if feature involves data)*

- **ExamEdition**: Edição anual nominal do ENEM (e.g., ENEM 2024), com ano independente das datas de aplicação.
- **ExamApplication**: Agrupamento de aplicação (regular, reaplicação, PPL) dentro de uma edição, podendo abranger múltiplos dias.
- **KnowledgeArea**: Área canônica: LC, CH, CN, MT, RED.
- **ExamBooklet**: Caderno lógico de uma aplicação, com representações concretas como recursos associados.
- **Question**: Item avaliativo canônico com identidade interna independente de posição, página ou cor.
- **QuestionContentRevision**: Revisão imutável de conteúdo extraído, com método, fonte e localizador.
- **Alternative**: Alternativa identificável dentro de revisão, com índice canônico estável; pode ser apenas visual.
- **AlternativePlacement**: Correspondência entre rótulo publicado e alternativa canônica (entidade não obrigatória agora).
- **QuestionPlacement**: Ocorrência de questão em caderno lógico com contexto de numeração (COMMON, ENGLISH, SPANISH, UNKNOWN).
- **AnswerKeyObservation**: Observação de gabarito publicado por fonte oficial, vinculada a placement; suporta VALID, ANNULLED, UNKNOWN, retificação e resolução parcial.
- **QuestionAsset**: Recurso visual (figura, tabela, gráfico, mapa, fórmula) vinculado a revisão ou alternativa.
- **OfficialCompetency**: Competência da Matriz de Referência oficial, com código, área e versão da matriz.
- **OfficialSkill**: Habilidade da matriz oficial, vinculada à competência correspondente.
- **ClassificationRun**: Execução de classificação com método, versão, inputs e metadados LLM quando aplicável.
- **QuestionSkill**: Relação questão–habilidade (OFFICIAL ou INFERRED), com confiança, run e revisão.
- **Topic**: Taxonomia analítica hierárquica do projeto (tema/subtema), distinta de competências/habilidades oficiais.
- **QuestionTopic**: Relação questão–tópico por conjunto de classificação, com role PRIMARY/SECONDARY e cardinalidade controlada.

## Success Criteria *(mandatory)*

### Measurable Outcomes

Os critérios abaixo são conceituais: sua satisfação valida o modelo, não a implementação.

- **SC-001**: O modelo representa edição nominal independente das datas e aplicações com múltiplos dias.
- **SC-002**: O modelo representa caderno lógico com várias representações concretas como recursos.
- **SC-003**: O modelo representa a mesma questão em placements distintos, com equivalência evidenciada.
- **SC-004**: O modelo representa o mesmo número no mesmo caderno em contextos inglês e espanhol sem colisão.
- **SC-005**: O modelo representa identificadores externos múltiplos, com namespace e evidência.
- **SC-006**: O modelo representa revisões imutáveis de conteúdo, extração e normalização separadas.
- **SC-007**: O modelo representa alternativas sem texto, índices canônicos e correspondência de rótulos.
- **SC-008**: O modelo representa assets de enunciado ou alternativa com ordem/origem, mesmo sem recorte local.
- **SC-009**: O modelo representa gabarito publicado sem alternativa resolvida.
- **SC-010**: O modelo representa anulação contextual e retificação preservando histórico.
- **SC-011**: O modelo representa competência/habilidade versionada e associação oficial evidenciada.
- **SC-012**: O modelo representa associação inferida e run rastreável, inclusive após revisão humana.
- **SC-013**: O modelo representa questão sem tópicos e conjuntos temáticos parciais/completos distintos.
- **SC-014**: O modelo representa dados parciais sem valores fabricados, sem status genérico de ETL no item.
- **SC-015**: O modelo representa evidências diferentes para conteúdo, placement e gabarito.
- **SC-016**: O modelo preserva recuperação futura da revisão apresentada e da observação de correção referenciada.

### Migration Acceptance

- **MA-001**: Uma auditoria de escopo encontra zero requisitos novos não presentes no documento legado `specs/003-question-data-model.md`.
- **MA-002**: Todos os 24 invariantes do legado (INV-001 a INV-024) estão preservados integralmente.
- **MA-003**: Todos os 16 critérios de aceite conceituais do legado (§32) estão mapeados a success criteria (SC-001 a SC-016).

## Assumptions

- Esta especificação define o modelo canônico de domínio; o README continua sendo a referência para o estado efetivamente implementado.
- O primeiro corpus normalizado prioriza ENEM 2017–2025, aplicação regular, representação impressa padrão; esta é uma prioridade de implementação, não uma limitação permanente do domínio.
- UUID versus hash, schema físico final, formato de alternativas/assets, necessidade real de AlternativePlacement, taxonomia detalhada, algoritmo de deduplicação e thresholds de elegibilidade permanecem adiados conforme o legado.
- Listas de valores canônicos (application_type, numbering_context) são exemplos conceituais, não enums físicos fechados.
- A SPEC-002 governa proveniência e dados. A SPEC-004 governa aquisição e ingestão. Esta especificação não redefine entidades ou contratos desses escopos.
- A stack vigente (ADR-0001) permanece inalterada.

## Dependencies

- `specs/003-question-data-model.md`: fonte histórica integral desta reconstrução retrospectiva e mantida sem alteração.
- `.specify/memory/constitution.md`: princípios I (Specification Is the Source of Truth), IV (Deterministic and Tested Domain Rules) e V (Data Integrity, Provenance, and Security) governam diretamente este modelo.
- `specs/001-product-foundation/spec.md`: FR-012–FR-016 da SPEC-001 dependem da representação de questões, tentativas e correção definida neste modelo.
- `specs/002-data-sources/spec.md`: FR-014–FR-015 (taxonomia/classificação), FR-009–FR-012 (proveniência/lineage) e FR-019 (null semantics) fornecem as regras de dados que este modelo respeita.
- `specs/004-source-resource-and-local-ingestion.md`: implementa SourceResource, ResourceAcquisition e EvidenceReference, que este modelo referencia para proveniência e localizadores.
- `docs/adr/0001-initial-architecture.md`: define a stack e decisões arquiteturais vigentes.
