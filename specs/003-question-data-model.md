# SPEC-003 — Question Data Model

## Status

Draft v2 — revisada conforme parecer técnico e decisões aprovadas pelo responsável pelo produto.

Estado da revisão: READY_FOR_NEXT_SPEC. O modelo conceitual está pronto para orientar a SPEC-004 — Source Resource and Minimal Local Ingestion Contract. Isso não significa que contratos físicos ou de ingestão estejam implementados ou aprovados por esta spec.

# 1. Objetivo e cobertura inicial

Definir o modelo canônico para representar questões históricas do ENEM, independentemente do formato de um único dataset do Inep.

O modelo cobre edições, aplicações, áreas, cadernos lógicos, questões, placements, revisões de conteúdo, alternativas, observações de gabarito, recursos visuais, competências, habilidades, taxonomia analítica, classificações e proveniência.

O primeiro corpus normalizado deve priorizar **ENEM 2017–2025, aplicação regular, representação impressa padrão**. Essa é uma prioridade de implementação, não uma limitação permanente do domínio nem uma afirmação sobre disponibilidade de todos os arquivos. Outras aplicações e representações devem poder ser catalogadas como `SourceResource`, sem normalização completa no primeiro incremento.

Esta spec deve anteceder a implementação de ingestão. Não define migrations, ETL, UI ou uma nova stack.

# 2. Princípios e convenções de campos

A identidade de `Question` não depende exclusivamente de ano, número, cor ou página. `QuestionPlacement` representa a ocorrência contextual; `QuestionContentRevision` preserva o conteúdo efetivamente extraído de uma fonte.

As listas de campos são conceituais, não schemas físicos. As categorias abaixo valem para todas as seções:

| Categoria | Contrato |
| --- | --- |
| Estrutural obrigatório | Deve existir com valor válido para constituir aquela entidade ou relação; referências não podem ser órfãs ou fabricadas. |
| Existente, nullable | O campo faz parte do contrato, mas aceita `null` quando desconhecido ou não disponível. |
| Opcional | A informação pode ser omitida; sua ausência não autoriza inferir um valor. Se fornecida, deve respeitar a semântica descrita. |
| Obrigatório condicional | Torna-se obrigatório na condição explicitada, como metadados de uma execução LLM. |

Coleções podem estar vazias onde indicado. Um registro parcial não precisa fingir completude. Quando faltarem referências estruturais para constituir uma relação canônica, a observação original deve ser preservada para resolução posterior pela ingestão, sem inventar identidades ou descartar dados.

Não usar string vazia como substituto indiscriminado de ausência. `null` e categoria explicitamente desconhecida têm significados distintos, conforme SPEC-002 §18. Datas usam ISO 8601; horários relevantes são armazenados em UTC. Não inventar horário para uma data documental.

# 3. ExamEdition

Representa a edição anual nominal, como ENEM 2024 ou ENEM 2025.

| Categoria | Campos |
| --- | --- |
| Estrutural obrigatório | `id`, `year` — ano nominal da edição |
| Existente, nullable | `name` — nome conhecido, sem preencher por inferência como se fosse oficial |

O ano nominal é independente das datas concretas de realização. Não derivar identidade de edição a partir do ano de uma data de aplicação. Evidências dos atributos externos devem ser preservadas conforme §25.

# 4. ExamApplication

Representa um **agrupamento de aplicação dentro de uma edição**. Pode abranger múltiplos dias; não há premissa de uma única data de aplicação.

| Categoria | Campos |
| --- | --- |
| Estrutural obrigatório | `id`, `edition_id` |
| Existente, nullable | `application_type`, `official_name` |

O tipo é uma classificação canônica, não identidade da aplicação. Exemplos conceituais incluem regular, reaplicação e PPL; não constituem enum físico fechado nem pressupõem categorias oficiais sempre mutuamente exclusivas. Preservar designações oficiais compostas e não forçar sua divisão sem evidência.

Uma categoria não identificada não deve receber uma categoria inventada. A lista canônica poderá evoluir com evidência. Cada aplicação pertence exatamente a uma edição.

As datas concretas devem poder ser associadas ao dia/caderno correspondente (§6), sem exigir nova entidade para calendário. O contrato de evidência da designação e das datas será detalhado na SPEC-004.

# 5. KnowledgeArea

Identificadores canônicos:

| Identificador | Área |
| --- | --- |
| LC | Linguagens, Códigos e suas Tecnologias |
| CH | Ciências Humanas e suas Tecnologias |
| CN | Ciências da Natureza e suas Tecnologias |
| MT | Matemática e suas Tecnologias |
| RED | Redação |

`id` é estrutural obrigatório no catálogo; a denominação corresponde ao identificador. Não usar nomes livres no lugar desses identificadores. `RED` existe para consistência geral e não obriga redação a usar o modelo de questão objetiva.

# 6. ExamBooklet

Representa inicialmente o **caderno lógico** de uma aplicação.

| Categoria | Campos |
| --- | --- |
| Estrutural obrigatório | `id`, `application_id` |
| Existente, nullable | `booklet_code`, `official_name`, `color`, `day`, `administration_date` |

`day` identifica o dia dentro da aplicação, não uma data de calendário. `administration_date` registra a data concreta correspondente quando conhecida, com evidência. As datas dos diferentes dias não precisam coincidir nem pertencer ao ano nominal da edição.

`booklet_code` preserva o identificador oficial quando existir, com seu escopo; cor e código isolados não são identidade global.

Representações normal, ampliada, superampliada e recursos de acessibilidade são inicialmente recursos/fontes concretas associados ao caderno lógico. Um caderno pode se associar a vários recursos; um recurso também pode documentar mais de um contexto. A relação e sua evidência serão detalhadas pela SPEC-004.

Não criar uma entidade obrigatória de representação nesta spec. Uma representação física não cria automaticamente outro caderno nem prova equivalência de conteúdo entre questões. Se evidência futura demonstrar diferença semântica relevante, o modelo poderá evoluir. Preservar o recurso e a diferença observada, sem fusão forçada.

Não há um único idioma obrigatório do caderno: opções inglesa e espanhola podem coexistir nele. O contexto de numeração pertence ao placement (§9).

# 7. Question e QuestionContentRevision

## 7.1 Question

Representa o item avaliativo canônico.

| Categoria | Campos |
| --- | --- |
| Estrutural obrigatório | `id` — identidade interna estável |
| Existente, nullable | `area_id` — identificador canônico quando conhecido |
| Coleção, zero ou mais | Identificadores externos com escopo e evidência |
| Opcional | `metadata` com semântica e proveniência explícitas (§20) |

A identidade interna independe de posição, página, cor e existência de código externo. A estratégia concreta de IDs permanece adiada; não se decide UUID versus hash nesta revisão.

Não há `Question.status` genérico obrigatório. Conteúdo textual pertence às revisões, e situação de gabarito pertence às observações contextualizadas.

## 7.2 Identificadores externos

Uma questão pode possuir **zero ou mais** identificadores externos. Cada identificador registrado exige:

| Categoria | Informação |
| --- | --- |
| Estrutural obrigatório | Namespace/escopo, valor e referência à fonte/evidência |

Nunca fabricar identificadores externos. Valores iguais em namespaces diferentes não são automaticamente equivalentes. O escopo deve explicitar o que a fonte garante, sem presumir unicidade global ou estabilidade entre datasets.

A estrutura física não é definida aqui. Não impor um campo escalar único como condição de existência de `Question`. Uma fusão deve preservar todos os identificadores e evidências pertinentes.

## 7.3 QuestionContentRevision

Representa uma revisão imutável do conteúdo extraído de uma questão, sem introduzir AST genérica ou CMS.

| Categoria | Campos |
| --- | --- |
| Estrutural obrigatório | `id`, `question_id`, `source_resource_id`, `extraction_method`, `created_at` |
| Existente, nullable | `statement`, `normalized_statement`, `source_locator` |
| Opcional | Idioma(s) do conteúdo quando conhecidos; referência à revisão anterior, se houver correção |

`extraction_method` deve identificar o método e sua versão, diretamente ou por referência ao processamento rastreável. Normalização, quando realizada, deve preservar método/versão e inputs conforme SPEC-002. Esses metadados não substituem a fonte original.

`statement` é texto extraído, não garantia de extração validada. `normalized_statement` nunca sobrescreve `statement`. Texto pode ser `null` quando não extraível ou não processado; o recurso original continua referenciado. Não apresentar reconstrução inferida como transcrição oficial.

Correções posteriores geram nova revisão, preservando a anterior. Uma revisão já referenciada não deve ser alterada silenciosamente. O conjunto de alternativas e os vínculos de assets associados ao conteúdo também devem permanecer recuperáveis nessa revisão.

Uma questão pode possuir zero revisões de conteúdo enquanto somente metadados ou gabarito forem conhecidos, ou várias revisões de fontes/extrações diferentes. A conexão entre revisão e ocorrência/representação deve preservar o placement e o recurso de origem aplicáveis, sem presumir que toda revisão sirva para todos os placements.

Futuras tentativas devem poder referenciar qual revisão foi apresentada, a alternativa correspondente e a observação de gabarito utilizada. Esta spec preserva essa possibilidade; não define nem implementa `Attempt` ou sua política de recorreção.

# 8. Identidade e deduplicação

Distinguir identidade confirmada de similaridade provável. A política de equivalência entre adaptações é conservadora: só fundir registros quando houver evidência suficiente de identidade; na dúvida, manter separados.

Identificadores oficiais com escopo, hashes, metadados, comparação textual e análise humana podem contribuir como evidência. Similaridade textual sozinha não autoriza fusão, inclusive entre representações associadas ao mesmo caderno lógico.

SHA-256 de arquivo bruto verifica o recurso. Fingerprint de texto normalizado é dado derivado com método/versão e não prova, sozinho, identidade do item. Não confundir esses hashes com a estratégia de ID interno.

A fusão deve possuir justificativa rastreável e preservar identificadores externos, fontes, placements, revisões e referências históricas. Identificadores previamente referenciados devem continuar resolvíveis. Não se exige mecanismo físico específico para isso nesta spec.

# 9. QuestionPlacement

Representa a ocorrência de uma questão em um caderno lógico.

| Categoria | Campos |
| --- | --- |
| Estrutural obrigatório | `id`, `question_id`, `booklet_id`, `numbering_context` |
| Existente, nullable | `question_number`, `position` |
| Opcional | `display_label` |

`question_number` é o número publicado. `position` é a ordem de ocorrência no contexto de numeração, quando conhecida. `display_label` preserva um rótulo publicado quando necessário; não substitui identidade.

`numbering_context` deve distinguir, no mínimo, os conceitos:

| Exemplo de identificador conceitual | Significado |
| --- | --- |
| COMMON | Bloco comum |
| ENGLISH | Opção de língua inglesa |
| SPANISH | Opção de língua espanhola |
| UNKNOWN | Contexto explicitamente desconhecido |

Esses exemplos não impõem enum físico fechado. Idioma do conteúdo **não** é sinônimo de `numbering_context`.

Invariante conceitual:

```text
(booklet_id, numbering_context, question_number) deve ser único.
```

Quando o número ainda é desconhecido, o registro parcial não autoriza atribuir um número artificial nem afirmar que duas ocorrências são iguais. `UNKNOWN` não autoriza fundir observações potencialmente pertencentes a opções diferentes. Uma colisão ainda não resolvida deve preservar as evidências na ingestão até desambiguação, sem violar a identidade canônica ou descartar informação. O tratamento físico de nulidade será definido posteriormente.

Um placement pertence exatamente a um caderno e a uma questão. Uma questão pode possuir vários placements, inclusive em aplicações distintas quando sua identidade estiver comprovada.

Páginas e outros localizadores pertencem à evidência sobre um **recurso concreto**, não ao placement abstrato. Distinguir página impressa de índice do PDF quando necessário na SPEC-004. Não manter `page_number` e `source_page` como campos globais ambíguos. A mesma ocorrência lógica pode ter localizações diferentes nas representações associadas ao caderno.

# 10. Alternative

Representa uma alternativa identificável dentro da revisão de conteúdo correspondente.

| Categoria | Campos |
| --- | --- |
| Estrutural obrigatório | `id`, `content_revision_id`, `canonical_index` |
| Existente, nullable | `text` |
| Opcional | `normalized_text`, com método/versão de normalização; `metadata` rastreável |

A questão é determinada pela revisão; não é necessário duplicar uma referência independente que possa divergir. Caso a implementação mantenha ambas, elas devem concordar.

`canonical_index` é único dentro da revisão da questão e estável nessa revisão. Índices como 0–4 são exemplos, não equivalem automaticamente a A–E. Não renumerar silenciosamente alternativas já referenciadas.

Uma alternativa pode conter apenas recurso visual e `text = null`. Extração parcial pode produzir um conjunto incompleto; não inventar alternativas para completar uma quantidade esperada.

A letra publicada só pode ser resolvida para uma alternativa por correspondência explícita, compatível com o placement, a revisão e sua evidência (§11). Correções de conteúdo preservam as alternativas da revisão anterior.

# 11. Correspondência de alternativas e AlternativePlacement

O contrato deve permitir registrar correspondência entre rótulo publicado e alternativa canônica. A entidade/tabela `AlternativePlacement` **não é obrigatória agora**; sua necessidade será avaliada nas fontes.

Quando uma correspondência for registrada, exige conceitualmente:

| Categoria | Informação |
| --- | --- |
| Estrutural obrigatório | `question_placement_id`, `alternative_id`, `display_label` e evidência da correspondência no recurso/revisão aplicável |
| Existente, nullable | `display_position` |

A revisão é recuperável pela alternativa. Deve ser compatível com a questão do placement. Em um mesmo contexto de apresentação e revisão, um rótulo não pode resolver ambiguamente para alternativas distintas; divergências entre recursos devem permanecer explícitas.

Mesmo que a ordem coincida entre os primeiros cadernos analisados, não converter posição interna em letra por premissa não documentada. Não exigir essa correspondência para preservar um gabarito ainda não resolvido.

# 12. AnswerKeyObservation

Representa **uma observação publicada por fonte oficial**, vinculada inequivocamente a um `QuestionPlacement`. Não é propriedade mutável global de `Question`.

| Categoria | Campos |
| --- | --- |
| Estrutural obrigatório | `id`, `question_placement_id`, `source_resource_id`, `status` |
| Existente, nullable | `published_value`, `resolved_alternative_id`, `supersedes_id`, `source_locator`, `published_at` |

`published_value` preserva a letra ou marcador publicado; aceita `null` somente quando não conhecido/extraível, sem inventar o valor. A fonte e a limitação de extração devem permanecer rastreáveis. `published_at` não deve receber a data de coleta como substituta; a coleta pertence à proveniência do recurso.

Situações conceituais de `status` incluem `VALID`, `ANNULLED` e `UNKNOWN`. Aqui `VALID` significa que a situação oficial é de resposta válida, **não** que a alternativa já esteja resolvida internamente, que o texto esteja validado ou que o item esteja pronto para correção automática.

Uma observação pode registrar `published_value = C` e `resolved_alternative_id = null`. Se houver resolução, a alternativa deve pertencer a revisão compatível com a questão e o contexto do placement, com evidência da correspondência. Não resolver usando apenas o índice canônico.

Um placement pode ter várias observações históricas. Retificação oficial gera nova observação; `supersedes_id`, quando usado, referencia observação anterior do mesmo placement, sem ciclos ou autorreferência. Preservar V1 e sua fonte ao registrar V2. A supersessão exige evidência; ser coletado depois não prova precedência oficial. Observações conflitantes não são conciliadas silenciosamente.

Se a resolução interna for obtida ou corrigida depois, preservar a evidência publicada e o histórico de resolução, especialmente quando já referenciados. Enriquecimento interno não deve ser apresentado como retificação oficial nem reutilizar `supersedes_id` para simular uma publicação inexistente. O mecanismo físico de histórico fica para implementação posterior.

A anulação vale para a observação/contexto correspondente. Não transformar automaticamente todos os placements da mesma questão em anulados. Uma ocorrência anulada não pode ser tratada como erro do usuário; situações desconhecidas, conflitantes ou não resolvidas também não autorizam correção automática como erro.

# 13. QuestionAsset

Representa recursos como figuras, tabelas, gráficos, mapas, fórmulas e imagens associados ao conteúdo.

| Categoria | Campos |
| --- | --- |
| Estrutural obrigatório | `id`, vínculo a exatamente um alvo (conteúdo da revisão OU alternativa), `source_resource_id` |
| Existente, nullable | `order`, `asset_type`, `source_locator` |
| Opcional | `local_path`, checksum do artefato/recorte quando materializado |

Se o alvo for alternativa, sua revisão é determinada por ela. A ordem é relativa ao alvo e deve ser preservada quando conhecida; tipo e localizador desconhecidos não são inventados. O localizador na fonte deve ser recuperável quando disponível, conforme SPEC-004.

`local_path` e checksum de recorte não são obrigatórios antes da materialização. Isso não dispensa SHA-256 do arquivo bruto ingerido, exigido pela SPEC-002. A origem pode continuar sendo apenas uma referência ao recurso original.

Não é obrigatório extrair assets no primeiro pipeline. Uma coleção vazia pode significar que ainda não foram extraídos, não que a questão não tem imagens. `has_assets` não é fonte de verdade independente; eventual indicador deve respeitar essa distinção.

Não é necessário um CMS ou uma estrutura genérica de documento para registrar alvo, ordem e origem.

# 14. OfficialCompetency

Representa uma competência da Matriz de Referência oficial.

| Categoria | Campos |
| --- | --- |
| Estrutural obrigatório | `id`, `area_id`, `official_code`, `matrix_version`, `source_resource_id` |
| Existente, nullable | `name`, `description` |

O código deve ser interpretado no contexto da área e da versão da matriz. Se não for possível identificar esses vínculos, preservar a observação de origem sem fabricar uma competência normalizada.

# 15. OfficialSkill

Representa uma habilidade da matriz oficial, vinculada à competência correspondente.

| Categoria | Campos |
| --- | --- |
| Estrutural obrigatório | `id`, `competency_id`, `official_code`, `source_resource_id` |
| Existente, nullable | `description` |

Área e versão da matriz são determinadas pela competência. Se `matrix_version` também for materializado na habilidade, deve coincidir com o da competência; não são versões independentes.

Identificar a habilidade pelo código em seu contexto de área/matriz; não pressupor que o código sozinho seja global. Definições históricas não são sobrescritas quando a matriz mudar. Uma habilidade oficial não prova que a associação daquela habilidade a uma questão também seja oficial.

# 16. QuestionSkill e ClassificationRun

## 16.1 ClassificationRun

Representa uma execução de classificação, sem exigir tabela física própria. Metadados completos de LLM são registrados nesta execução e referenciados pelas associações, não repetidos em cada associação.

| Categoria | Campos |
| --- | --- |
| Estrutural obrigatório | `id`, `method`, `method_version`, `input_hash`, `timestamp`, configuração relevante da execução (pode ser vazia quando não houver parâmetros) |
| Obrigatório condicional | `provider`, `model`, `prompt_version` para execução LLM |

`input_hash` deve identificar os inputs efetivamente usados; referências aos inputs e revisões necessárias ao lineage devem ser preservadas. Se a execução processar várias questões, o hash e as referências devem permitir identificar esse conjunto, não fingir um input individual.

A identidade da execução não é a versão do algoritmo. O mesmo método/versão pode ter várias execuções. `classification_version` nas associações identifica a versão do procedimento/classificação, não substitui `classification_run_id` nem a identidade do conjunto de resultados.

Uma classificação humana independente pode registrar sua autoria e procedimento sem inventar metadados LLM. Uma associação oficial extraída da fonte não exige execução LLM.

## 16.2 QuestionSkill

Relaciona questão e habilidade; a cardinalidade é muitos-para-muitos.

| Categoria | Campos |
| --- | --- |
| Estrutural obrigatório | `question_id`, `skill_id`, `relationship_type`, `classified_by`, `classification_version`, `review_status`, `created_at` |
| Existente, nullable | `confidence`, `classification_run_id` |
| Obrigatório condicional | Evidência oficial específica quando `relationship_type = OFFICIAL`; referência ao run para classificação automática |

`relationship_type` distingue `OFFICIAL` e `INFERRED`. Uma associação `OFFICIAL` exige fonte que comprove **a associação**, não apenas que a habilidade exista na matriz. A evidência pode ser diferente da fonte do conteúdo da questão.

Inferência humana ou LLM permanece `INFERRED`. Aprovação humana pode produzir `INFERRED + REVIEWED`, sem alterar sua origem. `review_status` registra revisão da associação, nunca oficialidade ou estado do parser.

`confidence`, quando disponível, está entre 0 e 1. `null` não significa zero; origem oficial não obriga inventar confiança 1.

Propostas, execuções e revisões anteriores devem continuar rastreáveis. Associação inferida não sobrescreve evidência oficial nem outra proposta silenciosamente. Mudanças na associação preservam a classificação e o run que as originaram.

# 17. Topic

Representa a taxonomia analítica do projeto, distinta de competência e habilidade oficiais.

Exemplo conceitual: Matemática → Proporcionalidade → Porcentagem.

| Categoria | Campos |
| --- | --- |
| Estrutural obrigatório | `id`, `name`, `taxonomy_version` |
| Existente, nullable | `parent_id`, `area_id` |

`parent_id = null` permite raiz. Relações entre pai e filho devem ser acíclicas e coerentes com a versão da taxonomia. Área, quando conhecida, utiliza o catálogo canônico. Não criar tópico fictício apenas para preencher uma classificação ausente.

Não é obrigatório criar entidade `Subtopic`; a hierarquia representa tema/subtema. Um estado de ciclo de vida da taxonomia, se necessário, será definido na spec temática, sem misturá-lo com revisão de classificação ou ETL. O vocabulário temático detalhado fica para spec própria.

# 18. QuestionTopic e conjuntos de classificação

Relaciona questões à taxonomia analítica.

| Categoria | Campos |
| --- | --- |
| Estrutural obrigatório | `question_id`, `topic_id`, `classification_set_id`, `role`, `relationship_type`, `classified_by`, `classification_version`, `review_status` |
| Existente, nullable | `confidence`, `classification_run_id` |
| Obrigatório condicional | Referência ao run para classificação automática; evidência oficial específica se uma associação for declarada `OFFICIAL` |

`role` distingue `PRIMARY` e `SECONDARY`. Origem, confiança, evidência e revisão seguem §16.2. A taxonomia continua analítica mesmo que exista evidência oficial para uma associação específica; usar um documento oficial como input de inferência não torna seu resultado oficial.

`classification_set_id` identifica um conjunto de resultados para a questão, com indicação explícita de completude. Não obriga nova entidade/tabela física. Não confundir conjunto, execução, versão do procedimento e versão da taxonomia: uma execução pode classificar várias questões, e propostas concorrentes devem coexistir em conjuntos distintos.

Reconciliação explícita, aprovada, da SPEC-002 §13 com ingestão parcial:

| Situação | Cardinalidade de tópicos |
| --- | --- |
| Questão não classificada | Pode possuir zero tópicos. |
| Conjunto candidato/parcial | Pode possuir zero ou um `PRIMARY`, com zero ou mais `SECONDARY`. |
| Conjunto declarado completo | Deve possuir exatamente um `PRIMARY`, com zero ou mais `SECONDARY`. |

A exigência de um tópico principal na SPEC-002 refere-se ao **conjunto temático declarado completo**, não à existência de qualquer registro de questão. Esta especialização foi aprovada pelo responsável pelo produto e é registrada aqui explicitamente; não autoriza descartar questões sem classificação.

A restrição vale por `(question_id, classification_set_id)`. O mesmo tópico não pode ocupar simultaneamente os papéis `PRIMARY` e `SECONDARY` nesse conjunto, nem ser duplicado como associação idêntica. Completude não significa revisão humana nem origem oficial.

Classificações inferidas **podem alimentar analytics antes de revisão humana**, preservando `INFERRED`, confiança quando disponível e classificação/run responsável. Continuam identificadas como inferências/candidatas, não fatos oficiais. A análise deve explicitar os conjuntos e versões utilizados, sem misturar propostas concorrentes silenciosamente. A elegibilidade poderá adotar thresholds configuráveis em spec futura; nenhum threshold é fixado aqui.

# 19. Difficulty

Dificuldade não é inicialmente uma propriedade factual simples de `Question`. Distinguir dificuldade oficial, derivada e percebida pelo usuário.

Caso não exista informação oficial, não atribuir essa nomenclatura à estimativa. Uma observação derivada, se produzida futuramente, exige método, versão, inputs/dataset, parâmetros relevantes, valor e data de geração. A percepção do usuário não é propriedade oficial do item.

Não criar entidade/tabela obrigatória de dificuldade nesta etapa nem implementar cálculo. A SPEC-001 continua exigindo analytics determinístico e proíbe apresentar aproximação como TRI real.

# 20. QuestionMetadata

Metadados adicionais são opcionais e não substituem campos de domínio definidos. Características futuras como necessidade de cálculo, interpretação de gráfico ou presença de fórmula devem possuir origem e classificação quando inferidas.

Não tornar essas possibilidades campos obrigatórios. Ausência de metadado não equivale a `false`. Conteúdo de IA deve continuar identificado e não sobrescrever informação oficial.

# 21. Conteúdo textual e normalização

Preservar separadamente:

1. recurso original imutável em raw;
2. conteúdo extraído em `QuestionContentRevision` e suas alternativas;
3. normalização derivada com método/versão e inputs rastreáveis.

A extração também pode conter erros; origem em fonte oficial não valida automaticamente OCR ou parsing. Correção de extração produz nova revisão. Não sobrescrever o original, a extração anterior ou uma normalização já referenciada como parte da revisão.

# 22. Questões de língua estrangeira

O mesmo caderno lógico pode conter questões de opções distintas com a mesma numeração. `numbering_context` no placement distingue essas ocorrências.

Não assumir que todos os participantes responderam exatamente ao mesmo conjunto de itens de Linguagens. Uma opção inglesa e uma espanhola são questões distintas salvo evidência suficiente de identidade; compartilhar número não é evidência.

Idioma(s) do conteúdo, opção escolhida pelo participante e contexto de numeração são conceitos distintos. Esta spec não define seleção de idioma ou respostas do usuário.

# 23. Questões anuladas

Uma ocorrência anulada permanece armazenada com conteúdo, fontes e histórico. A anulação é registrada em `AnswerKeyObservation.status`, no placement correspondente.

Não excluir a questão nem marcar automaticamente outras ocorrências como anuladas. A ocorrência não alimenta métricas normais de acerto sem tratamento específico e não pode ser tratada como erro do usuário. A definição de métricas e políticas de recorreção permanece fora desta spec.

# 24. Dados incompletos e conteúdo não extraível

`statement = null` e `Alternative.text = null` são permitidos. Não apresentar OCR incorreto como texto oficial validado. O registro pode continuar com referência ao original e limitações explícitas de extração.

Área, número, data, tipo, ordem e localizador desconhecidos seguem a nulabilidade definida nas respectivas seções. Não fabricar valores nem usar ausência de extração como prova de ausência do conteúdo.

Falta de referência estrutural não deve gerar entidades órfãs: preservar a observação na ingestão até resolução, conforme contrato da SPEC-004. Existência canônica, completude de conteúdo e aptidão para apresentação/correção são conceitos diferentes.

# 25. Proveniência e SourceResource

Cada fato externo relevante deve possuir evidência apropriada. A fonte que originou inicialmente `Question` não comprova automaticamente todos os seus atributos.

Preservar separadamente evidências de:

- conteúdo e extração;
- placement e contexto de numeração;
- gabarito e retificação;
- associação oficial questão–habilidade ou outra associação declarada oficial;
- identificador externo e seu escopo;
- edição, aplicação, caderno e datas.

Um fato pode ter várias evidências, e fontes diferentes podem apoiar fatos diferentes da mesma questão. Campos singulares como `source_resource_id` nas observações identificam sua fonte direta; não proíbem evidências adicionais ou observações separadas de outras fontes.

`SourceResource` identifica recurso concreto versionado; não é sinônimo do identificador de catálogo `source_id`, como DS-003. Localizadores devem estar ligados ao recurso a que se referem. Recursos e evidências divergentes não são sobrescritos silenciosamente.

A SPEC-004 — Source Resource and Minimal Local Ingestion Contract definirá a estrutura concreta de recursos, evidências, localizadores, manifestos e lineage. Deve respeitar a SPEC-002: raw imutável, SHA-256 do bruto, versões, precedência oficial, identificação de derivados/IA e ausência de secrets. Esta spec não implementa esse contrato.

# 26. Estados separados do domínio

Não há estado genérico obrigatório de `Question`. Distinguir:

- estado de execução do ETL;
- qualidade/completude da extração;
- revisão humana da classificação;
- situação oficial do gabarito;
- validade/eligibilidade pedagógica para determinada atividade.

São dimensões diferentes. Uma classificação pode estar revisada enquanto um asset aguarda extração. Rejeição pelo parser não muda identidade da questão nem torna o dado não oficial. Os estados de processamento serão definidos pelo pipeline quando necessários, sem enum obrigatório nesta spec.

# 27. Regras de preservação

Não descartar dados por ausência de tópico ou habilidade, por conterem assets, por anulação, incompletude ou falha de classificação automática.

Preferir registro parcial e limitação explícita à perda silenciosa. Fusão, correção e supersessão devem preservar fontes e referências anteriores. Imutabilidade de conteúdo e de raw não exige event sourcing ou arquitetura distribuída.

# 28. Modelo conceitual e cardinalidades

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

O caderno lógico pode estar associado a vários `SourceResource`, sem nova entidade obrigatória de representação. Revisões e correspondências de alternativas devem preservar o vínculo com o placement/recurso aplicável. O diagrama não determina tabelas nem obriga um registro parcial a possuir filhos ainda não extraídos.

# 29. Separação entre domínio e storage

Cada conceito não exige tabela independente. Coleções de identificadores, alternativas, assets, conjuntos de classificação e runs podem ter representação física simplificada desde que mantenham integridade, proveniência e referências históricas.

Não decidir ainda UUID versus hash, schema final ou representação física de alternativas. Não introduzir AST genérica, CMS, RAG, autenticação, recomendação ou novas tecnologias. A stack da SPEC-001 permanece inalterada.

# 30. Invariantes

## INV-001

Número da questão não identifica globalmente uma questão.

## INV-002

Uma questão pode aparecer em mais de um caderno/aplicação quando a identidade for comprovada; similaridade não basta para fusão.

## INV-003

Um placement pertence exatamente a um caderno e a uma questão, com referências válidas.

## INV-004

`(booklet_id, numbering_context, question_number)` deve ser único. Dados parciais e contexto desconhecido seguem §9, sem inventar números ou fundir colisões não resolvidas.

## INV-005

Inferência revisada continua `INFERRED`; revisão humana não a transforma em `OFFICIAL`.

## INV-006

Normalização não sobrescreve extração, inclusive de alternativas, nem o recurso original.

## INV-007

Anulação contextualizada permanece armazenada e não é propagada automaticamente a todos os placements da questão.

## INV-008

Ausência de classificação não invalida a existência da questão.

## INV-009

Dados derivados preservam método/versão, inputs e parâmetros relevantes. Execuções LLM registram os metadados da SPEC-002 §20 em `ClassificationRun`.

## INV-010

Identificadores externos não são fabricados; cada um possui namespace/escopo e evidência. Igualdade entre namespaces diferentes não prova equivalência.

## INV-011

Aplicação pode possuir múltiplos dias. Datas concretas do dia/caderno não redefinem o ano nominal da edição.

## INV-012

Representação física não redefine automaticamente identidade do caderno lógico nem prova identidade de questões adaptadas.

## INV-013

Observação de gabarito pode existir com valor publicado e sem alternativa canônica resolvida. Resolução existente deve corresponder à questão/revisão e contexto aplicáveis.

## INV-014

Retificação preserva observações anteriores. Supersessão oficial é evidenciada, restrita ao mesmo placement e sem ciclos; coleta posterior não basta.

## INV-015

Revisão de conteúdo referenciada é imutável; correções preservam a versão anterior e suas alternativas/assets recuperáveis.

## INV-016

Dados de ETL não determinam identidade, oficialidade ou validade pedagógica.

## INV-017

Confiança ausente não significa zero. Quando disponível, fica entre 0 e 1.

## INV-018

Associação oficial exige evidência oficial específica da associação, não apenas da existência de uma habilidade ou do documento usado como input.

## INV-019

Conjunto temático completo possui exatamente um `PRIMARY`; candidato/parcial possui zero ou um. O mesmo tópico não pode ser `PRIMARY` e `SECONDARY` no mesmo conjunto da questão.

## INV-020

Índice canônico de alternativa é único na revisão e não equivale automaticamente a A–E. Alternativa visual sem texto continua representável.

## INV-021

Asset pertence ao conteúdo de uma revisão ou a uma alternativa, com origem e ordem quando conhecida. Não exigir materialização para preservar sua referência.

## INV-022

Fatos distintos podem possuir fontes distintas. Fusão não perde evidências, revisões, placements ou resolução de referências históricas.

## INV-023

Habilidade pertence à competência da mesma matriz/área; códigos oficiais são interpretados em seu escopo versionado. A hierarquia de tópicos é acíclica e coerente com sua versão.

## INV-024

Inferências podem alimentar analytics antes de revisão, mas preservam origem, classificação/run e confiança disponível. Métricas continuam determinísticas e identificam conjuntos/versões usados; esta spec não fixa thresholds.

# 31. Fora de escopo

Não definir ou implementar nesta spec:

- tentativas do usuário ou recorreção de histórico;
- mastery, revisão de estudo, priority score e geração de sessões;
- redação ou algoritmos de recomendação;
- embeddings, RAG, autenticação ou integrações LLM;
- ingestão concreta de microdados, ETL ou download automático;
- migrations, UI, schema físico final, AST genérica ou CMS;
- thresholds de classificação ou vocabulário temático completo.

Referências futuras a conteúdo, alternativas e observações são preservadas sem antecipar essas funcionalidades.

# 32. Critérios de aceite conceituais

A revisão é adequada para orientar a próxima spec quando o modelo consegue representar, sem perda de semântica:

1. edição nominal independente das datas e aplicações com múltiplos dias;
2. caderno lógico com várias representações concretas como recursos;
3. mesma questão em placements distintos, com equivalência evidenciada;
4. mesmo número no mesmo caderno em contextos inglês e espanhol;
5. identificadores externos múltiplos, com namespace e evidência;
6. revisões imutáveis de conteúdo, extração e normalização separadas;
7. alternativas sem texto, índices canônicos e correspondência de rótulos;
8. assets de enunciado ou alternativa com ordem/origem, mesmo sem recorte local;
9. gabarito publicado sem alternativa resolvida;
10. anulação contextual e retificação preservando histórico;
11. competência/habilidade versionada e associação oficial evidenciada;
12. associação inferida e run rastreável, inclusive após revisão humana;
13. questão sem tópicos e conjuntos temáticos parciais/completos distintos;
14. dados parciais sem valores fabricados, sem status genérico de ETL no item;
15. evidências diferentes para conteúdo, placement e gabarito;
16. recuperação futura da revisão apresentada e da observação de correção referenciada.

Os casos A–J abaixo fazem parte destes critérios. Sua satisfação conceitual não substitui o contrato de ingestão da SPEC-004 nem testes de implementação futura.

# 33. Casos de teste conceituais

## Caso A — Mesma questão em dois cadernos

Há evidência suficiente de identidade de Q1. No caderno BLUE aparece como 137/COMMON; no YELLOW como 142/COMMON.

Resultado: `1 Question` e `2 QuestionPlacements`. Cada ocorrência preserva sua evidência. Sem prova de identidade, manter registros separados em vez de forçar o resultado por similaridade.

## Caso B — Classificação automática

LLM classifica Q1 com tópico principal porcentagem e confiança 0.91.

Resultado: associação `INFERRED`, conjunto versionado e referência a `ClassificationRun` com os metadados LLM. Não alterar conteúdo oficial. Pode alimentar analytics antes da revisão humana, preservando origem e run. Se o conjunto for declarado completo, contém exatamente um `PRIMARY`.

## Caso C — Questão anulada

Fonte oficial informa anulação para placement P1.

Resultado: `AnswerKeyObservation.status = ANNULLED` ligada a P1, com valor publicado quando disponível e sua fonte. Questão e observações permanecem no dataset. Outros placements não são automaticamente anulados. P1 não pode ser corrigido como erro do usuário por essa anulação.

## Caso D — Questão sem habilidade oficial conhecida

Resultado: a questão permanece representável com `QuestionSkill = []`. Isso não é erro estrutural. A ausência de tópicos também é permitida enquanto não houver conjunto temático completo.

## Caso E — Língua estrangeira

Mesmo caderno B1:

```text
P1: booklet_id = B1, numbering_context = ENGLISH, question_number = 1
P2: booklet_id = B1, numbering_context = SPANISH, question_number = 1
```

Resultado: placements coexistem sem colisão. O idioma dos trechos de conteúdo não redefine esses contextos. Não duplicar automaticamente o caderno lógico por idioma.

## Caso F — Gabarito sem alternativas extraídas

A fonte informa questão 42 → C. O placement P42 está identificado, mas as alternativas ainda não foram normalizadas.

```text
question_placement_id = P42
published_value = C
status = VALID
resolved_alternative_id = null
source_resource_id = recurso do gabarito
```

Resultado: observação armazenável, sem inventar alternativa. `VALID` não significa que a correção automática já seja possível.

## Caso G — Retificação

V1 é ingerido para P42. Posteriormente uma fonte oficial publica V2 que retifica V1.

Resultado: V1 permanece; V2 registra o mesmo placement, sua própria fonte e `supersedes_id = id de V1`. Não substituir conteúdo de V1. Sem evidência de retificação, preservar divergência em vez de concluir supersessão apenas pela ordem de coleta.

## Caso H — Alternativa visual

Uma alternativa da revisão R1 contém gráfico e nenhum texto extraível.

Resultado: alternativa com `text = null`, índice canônico único em R1 e asset vinculado à alternativa, com ordem quando conhecida e referência/localizador na fonte. A alternativa continua válida como representação de conteúdo. Ausência de recorte local não exige `local_path` ou checksum de recorte artificial.

## Caso I — Classificação humana

LLM produz associação `INFERRED`, ligada ao run C1. Humano aprova.

Resultado: permanece `INFERRED`, agora com `review_status = REVIEWED`. Preservar run, confiança originalmente disponível e rastreabilidade da revisão. Aprovação não inventa evidência oficial nem confiança 1.

## Caso J — Duas fontes

Texto de Q1 é extraído do recurso R-TEXTO; gabarito do placement vem de R-GABARITO.

Resultado: `QuestionContentRevision.source_resource_id = R-TEXTO` e `AnswerKeyObservation.source_resource_id = R-GABARITO`. Preservar separadamente localizadores, versões e evidências. Uma fonte de criação genérica não substitui essas referências.

# 34. Decisões posteriores e consistência

## 34.1 Decisões aprovadas nesta revisão

Cobertura prioritária 2017–2025/regular/impressa padrão; caderno lógico com representações como recursos; equivalência conservadora; inferências elegíveis para analytics antes de revisão, sempre identificadas e sem threshold fixo.

Os bloqueios B1–B8 do parecer foram tratados: contexto de numeração (§9), aplicação/caderno (§§4–6), observações de gabarito (§12), identidade/proveniência (§§7.2, 8, 25), conteúdo/alternativas/assets (§§7.3, 10–13), classificação/run (§§16–18), nulabilidade/estados (§§2, 24, 26) e cardinalidade temática (§18).

## 34.2 Consistência com as specs anteriores

- SPEC-001: preserva apoio à decisão, áreas canônicas, simplicidade, regras determinísticas, ausência de dependência obrigatória de LLM e redação fora deste incremento. Especializa o conceito amplo de Exam em edição/aplicação/caderno sem implementar funcionalidades futuras.
- SPEC-002: preserva precedência oficial, raw imutável, SHA-256, lineage, dados ausentes explícitos e inferências identificadas. Metadados LLM são referenciados via run; revisão humana não altera origem.
- A regra de um tópico principal da SPEC-002 §13 é explicitamente refinada pela decisão aprovada: exatamente um no conjunto completo, zero ou um no parcial, zero permitido para questão não classificada (§18).
- Cobertura prioritária do corpus não elimina outras fontes/edições do catálogo nem transforma prioridade de normalização em limitação do domínio.

## 34.3 Próxima spec

Não há questão de produto remanescente que bloqueie a escrita da **SPEC-004 — Source Resource and Minimal Local Ingestion Contract**.

A SPEC-004 deverá definir recursos, evidências, localizadores, manifestos, ingestão local mínima, duplicação de recursos, retificações, lineage e qualidade com fixtures pequenas. Esses contratos pendentes constituem o trabalho da próxima spec, não autorização para o pipeline decidir semântica de domínio.

Continuam adiados para as specs/implementações pertinentes: IDs físicos, formato de alternativas/assets, necessidade real de `AlternativePlacement`, taxonomia detalhada, algoritmo de deduplicação e thresholds de elegibilidade. Nenhum impede a definição da SPEC-004. Não escrevê-la ou implementá-la como parte desta revisão.
