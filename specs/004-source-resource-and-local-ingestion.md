# SPEC-004 — Source Resource and Minimal Local Ingestion Contract

## Status

Draft v2 — revisada conforme parecer técnico e decisões aprovadas pelo responsável pelo produto.

**READY_FOR_IMPLEMENTATION.** Esta revisão define o primeiro incremento; não implementa código, migrations ou pipeline.

# 1. Objetivo e separação de responsabilidades

A ingestão deve responder: quais bytes recebemos, por qual origem foram observados, quando esta execução os recebeu, como sua integridade foi verificada e qual operação os utilizou?

A separação obrigatória é:

| Conceito | Responsabilidade |
| --- | --- |
| `SourceResource` | Identidade do conteúdo binário preservado. |
| `ResourceAcquisition` | Contexto/origem pela qual esse conteúdo foi observado. |
| `IngestionRun` | Execução que realizou a operação. |

SPEC-001 define produto e simplicidade; SPEC-002 define política de fontes, raw/interim/processed e proveniência; SPEC-003 define o domínio de questões. Esta spec define aquisição local, integridade, deduplicação exata, armazenamento e contratos simples de localização/evidência.

Preservar uma fonte não equivale a interpretar seu conteúdo. Aquisição simples não gera automaticamente evidências `CONTENT`, `ANSWER_KEY` ou `OFFICIAL_ASSOCIATION`. As camadas futuras que interpretarem a fonte associarão fatos às evidências apropriadas.

# 2. Escopo aprovado do primeiro incremento

Deve suportar:

1. Arquivo local → run → cópia segura → hash/tamanho → deduplicação exata → raw → recurso → aquisição → relatório.
2. ZIP local → preservação do ZIP → listagem segura → seleção explícita de **um** membro → materialização segura → hash/tamanho próprios → raw → aquisição vinculada ao ZIP.
3. Reingestão, verificação de integridade, falhas explícitas e recuperação de publicação incompleta.
4. Contratos serializáveis de localizador e evidência, sem tabelas ou interpretação semântica obrigatórias.

Materialização selecionada de membro ZIP entra no primeiro incremento. Não é extração em massa: a invocação recebe no máximo um arquivo local e, se ZIP, no máximo um membro selecionado explicitamente. Listagem sem seleção também deve funcionar.

Somente execução sequencial e **single writer**. Não oferecer processamento paralelo, múltiplos writers, seleção automática ou extração recursiva. Uma execução que liste/ingira o ZIP e materialize seu membro continua sendo uma única invocação/run, com etapas internas.

O corpus prioritário permanece ENEM 2017–2025, aplicação regular, representação impressa padrão. Essa prioridade não limita o domínio nem exige adquirir esse corpus nesta implementação. Todos os testes usam fixtures pequenas, sem datasets completos.

# 3. Convenções de campos e catálogo

| Categoria | Significado |
| --- | --- |
| Obrigatório | Campo presente com valor válido. Referências devem existir. |
| Nullable | Campo previsto, com `null` permitido quando ausente/desconhecido. |
| Condicional | Obrigatório na condição descrita. |
| Opcional | Pode ser omitido; se fornecido, não pode contradizer o contrato. |

Não fabricar URL, provider, catálogo, data, título ou media type. Não usar string vazia indiscriminadamente. Datas seguem ISO 8601; instantes são armazenados em UTC. Data documental sem horário não recebe horário inventado.

`SourceDefinition` é apenas a entrada de catálogo como DS-003, definida na SPEC-002. Não identifica arquivo nem exige tabela/serviço próprio. Pode ser configuração estática. Pertencimento conhecido ao catálogo é contexto da aquisição, não identidade do conteúdo.

# 4. SourceResource: conteúdo binário

Dois conteúdos binários diferentes correspondem a dois `SourceResource`. Dois arquivos, nomes ou origens diferentes com bytes idênticos reutilizam o mesmo recurso.

| Campo | Categoria e semântica |
| --- | --- |
| `id` | Obrigatório; referência interna estável. |
| `sha256` | Obrigatório; SHA-256 dos bytes efetivamente preservados. |
| `byte_size` | Obrigatório; quantidade de bytes preservados, inclusive zero quando o arquivo for vazio. |
| `media_type` | Nullable; tipo básico identificado com confiança. |
| `storage_locator` | Obrigatório; endereço controlado, relativo ao data root ou reconstruível deterministicamente. |
| `registered_at` | Obrigatório; instante de registro do conteúdo no catálogo operacional. |

Não pertencem ao recurso: nome recebido, catálogo de origem, URL, provider, parent/member, data de publicação ou título declarado pela fonte. Esses fatos dependem de contexto/origem. Se forem coletados metadados de publicação, devem ser observações contextualizadas com evidência; sua extração automática está fora deste incremento.

SHA-256 significa **identidade operacional do conteúdo binário para deduplicação exata**. Não comprova autenticidade institucional, validade pedagógica, correção factual, identidade de `Question` ou equivalência semântica.

A identidade interna pode ser opaca ou derivada do hash; a escolha física deve ser documentada sem alterar essa semântica. O conteúdo é deduplicado por SHA-256, nunca por caminho, URL ou nome. Tamanho/hash divergentes no destino constituem falha, não autorização para sobrescrever.

`registered_at` e demais metadados operacionais não integram a identidade binária. Reutilização não redefine a data do registro original. Media type é descrição técnica, não atributo de oficialidade.

# 5. ResourceAcquisition: origem observada

Cada aquisição aponta para exatamente um `SourceResource` e uma execução. Um recurso pode possuir **zero ou mais aquisições** no modelo; a ingestão bem-sucedida descrita nesta spec sempre registra a aquisição correspondente. Falhas sem recurso são issues, não aquisições órfãs.

| Campo | Categoria |
| --- | --- |
| `id` | Obrigatório |
| `resource_id` | Obrigatório |
| `ingestion_run_id` | Obrigatório |
| `acquisition_method` | Obrigatório |
| `observed_at` | Obrigatório |
| `source_definition_id` | Nullable |
| `source_url` | Nullable |
| `provider` | Nullable |
| `received_filename` | Nullable |
| `parent_resource_id` | Nullable; obrigatório para `CONTAINER_MEMBER` |
| `container_locator` | Nullable; obrigatório para `CONTAINER_MEMBER` |
| `source_retrieved_at` | Nullable |
| `fixture_kind` | Nullable; obrigatório quando a entrada for identificada como fixture |

Métodos do primeiro incremento: `LOCAL_FILE`, `CONTAINER_MEMBER` e `FIXTURE`. Registrar URL conhecida como metadado de um arquivo local não transforma o método em download. Outros métodos poderão ser definidos depois; não implementar download HTTP agora.

Para `CONTAINER_MEMBER`, `parent_resource_id` identifica o ZIP preservado e `container_locator` guarda o **nome exato** do membro selecionado. Não é caminho de destino. Para arquivo fornecido diretamente, ambos ficam `null`; não inferir um contêiner anterior pelo nome.

Uma nova origem nunca apaga aquisição anterior. Para tornar a auditoria do MVP previsível, cada observação bem-sucedida de um arquivo/membro nesta execução registra aquisição, mesmo quando reutiliza conteúdo. Não registrar aquisições extras por etapa interna da mesma observação.

# 6. Timestamps, ausência de origem e fixtures

`observed_at` é o instante em que **esta execução** recebeu/observou o input. Não é necessariamente o instante em que alguém baixou o arquivo da Internet.

`source_retrieved_at` pode registrar aquisição remota anterior somente se conhecida de maneira confiável, preservando a informação fornecida. Sua ausência não é preenchida com `observed_at`. Nenhuma dessas datas substitui uma data de publicação.

## Especialização explícita da SPEC-002 §9

Para ingestão local, o manifesto equivalente é composto pelos metadados de recurso e aquisições. `source_url`, `provider` e `source_definition_id` podem ser `null` quando desconhecidos. A observação local é registrada em `observed_at`; uma coleta remota anterior, se conhecida, fica em `source_retrieved_at`.

Esta é a especialização aprovada da obrigatoriedade genérica de origem na SPEC-002: documentar a ausência é válido; fabricar dados para preencher campos não é. SHA-256 do bruto materializado e rastreabilidade das informações conhecidas continuam obrigatórios. Um recurso sem origem oficial comprovada não adquire oficialidade por ter sido ingerido com sucesso.

## Fixtures

`fixture_kind = SYNTHETIC` identifica fixture criada exclusivamente para testes. Usar `acquisition_method = FIXTURE` para sua entrada direta. Não inventar provider, URL ou catálogo oficiais. Para um membro extraído de fixture ZIP, o método é `CONTAINER_MEMBER` e a natureza da fixture deve continuar identificada na aquisição do membro.

Fixture baseada em material real pode usar `fixture_kind = DERIVED_FROM_REAL` e deve preservar a origem conhecida, eventuais transformações e limitações documentadas. O fixture não passa a ser original oficial por derivar dele. Fora de fixtures, `fixture_kind = null`.

# 7. Caminhos de entrada e armazenamento

**Input path** localiza o arquivo fornecido, inclusive fora do projeto, como `/home/user/Downloads/file.pdf`. É informação operacional, pode não ser persistida e nunca constitui identidade. Se necessário para uma issue, deve ser tratado como diagnóstico de entrada, não como endereço futuro do raw.

**Storage locator** localiza o payload sob controle da aplicação, relativo ao data root ou reconstruível. Nunca usar caminho absoluto da máquina como identidade permanente.

Uma direção simples para implementação é `raw/resources/<sha256>/payload` sob o data root configurado. Esse layout especializa a organização por provider exemplificada na SPEC-002; não remove diretórios existentes e não muda a semântica raw/interim/processed. Layout final deve ser documentado.

Nomes recebidos e nomes de membros não controlam diretamente o caminho final. Entradas locais são somente leitura; não modificar o arquivo fornecido. A cópia preservada é um arquivo regular independente, não hard link ou symlink para a origem mutável.

A operação deve rejeitar entrada não regular ou links incompatíveis com a política de cópia segura e verificar que os destinos controlados não escapem por links no filesystem. Não executar conteúdo ou comandos embutidos nos arquivos.

# 8. ZIP e cardinalidade de contêineres

| Situação | Tratamento |
| --- | --- |
| ZIP recebido | Recurso raw do ZIP inteiro, com aquisição própria. |
| Membro apenas listado | Localizador dentro do ZIP; não cria recurso nem aquisição de membro. |
| Membro explicitamente materializado | Cria ou reutiliza recurso raw dos bytes descomprimidos, com hash/tamanho próprios e aquisição `CONTAINER_MEMBER`. |
| Conteúdo parseado, convertido, reserializado ou normalizado | Derivado em interim, quando houver parser futuro. |

Materialização de conteúdo ainda não registrado cria recurso; conteúdo já preservado é reutilizado por deduplicação exata. Não interpretar a palavra materialização como obrigação de duplicar identidade.

A aquisição do membro preserva ZIP pai, nome exato e run responsável. SHA-256 do ZIP não substitui SHA-256 dos bytes descomprimidos. Cada parte pode ser validada independentemente.

Mesmo conteúdo como membro do ZIP A, membro do ZIP B e arquivo local direto resulta em **um recurso do conteúdo e três aquisições**. Os recursos dos ZIPs são contabilizados separadamente. `parent_resource_id` nunca é campo de `SourceResource`.

Não criar automaticamente cópia interim do membro. ZIP dentro de ZIP pode ser preservado como bytes de um membro selecionado, mas não é aberto recursivamente; uma operação posterior exigiria nova solicitação explícita.

# 9. Raw, interim e processed

- **Raw:** bytes preservados, incluindo ZIP inteiro e membro selecionado descomprimido sem transformação. Uma vez registrados, são imutáveis.
- **Interim:** interpretações técnicas ou transformações source-native, como registros parseados e texto extraído; podem ser regeneradas a partir das fontes e lineage.
- **Processed:** resultados normalizados/mapeados ao domínio, definidos por specs posteriores.

Descompressão fiel não é reserialização. Não colocar um membro raw apenas em diretório descartável e continuar anunciando-o como materializado válido.

Este incremento não exige gerar interim nem processed. Etapas posteriores nunca substituem o original. Não reconstruir raw a partir de interim/processed como se fosse o original; extrair novamente a partir do ZIP raw íntegro é uma operação diferente, sujeita às regras de reuso e preservação.

# 10. SourceLocator: contrato simples

Estrutura obrigatória: `resource_id`, `locator_type`, `locator_value`. Cada localizador possui **exatamente um recurso de referência**. Sem tabela obrigatória nem linguagem genérica de query.

| Tipo | Valor e convenção |
| --- | --- |
| `DOCUMENT` | Objeto vazio `{}`: recurso inteiro. Não significa que uma localização mais precisa tenha sido determinada. |
| `PDF_PAGE` | `{page_index: n}`: índice físico zero-based, inteiro não negativo. Página impressa é metadado separado. |
| `CSV_ROW` | `{record_index: n, parser_config: ...}`: registro lógico de dados zero-based após tratamento explícito do cabeçalho. A configuração recuperável identifica encoding, delimitador, regras de aspas/escape, cabeçalho e tratamento de linhas vazias relevantes. Não é linha física. |
| `ZIP_MEMBER` | `{member_name: "nome exato"}`. Nomes duplicados tornam a seleção/materialização ambígua e são rejeitados no MVP. |
| `SHEET_RANGE` | `{sheet_name, row_start, row_end, column_start, column_end}`: coordenadas zero-based, início inclusivo e fim exclusivo, com intervalos não vazios. |
| `JSON_POINTER` | `{pointer: "..."}`: semântica RFC 6901; string vazia aponta para o documento inteiro. Não interpretar como JSONPath. |

`parser_config` deve estar embutida ou referenciar configuração imutável recuperável do run; não exige cadastro de perfis. A semântica lógica de CSV só pode ser resolvida com essa configuração. Não inventar regras de leitura desconhecidas para produzir localizador aparentemente preciso.

Referência normativa de JSON Pointer: RFC 6901. Implementações específicas de resolução podem vir depois. O primeiro incremento valida/serializa os contratos e opera sobre `DOCUMENT` e `ZIP_MEMBER`; não exige resolver PDF, CSV, planilha ou JSON. Round-trip não equivale a validar existência da página/célula/registro no arquivo.

`TABLE_ROW`, `TEXT_RANGE` e `OTHER` não são localizadores executáveis do núcleo inicial. Extensões futuras exigem semântica e necessidade concretas.

# 11. EvidenceReference: contrato para camadas futuras

Representação escolhida:

```text
EvidenceReference
  locator: SourceLocator
  evidence_role
  notes: nullable
```

O recurso é identificado somente por `locator.resource_id`. Não duplicar `resource_id` na raiz da referência. Papéis conceituais incluem `CONTENT`, `PLACEMENT`, `ANSWER_KEY`, `EXTERNAL_IDENTIFIER`, `OFFICIAL_ASSOCIATION` e `PUBLICATION_METADATA`.

A referência fica anexada à observação/fato que a camada interpretadora produzir. Não criar esquema genérico de `entity_type`, `entity_id`, `field_name` ou `fact_id`. Um fato pode ter várias evidências e um recurso pode apoiar vários fatos; o proprietário da referência define qual fato está sendo apoiado.

Preservar recurso de origem oficial não implica que toda interpretação seja oficial. Em particular, não implica `QuestionSkill.relationship_type = OFFICIAL`. O papel `OFFICIAL_ASSOCIATION` não é prova por si só: a evidência deve sustentar especificamente a associação, conforme SPEC-003.

Aquisição registra bytes e origem; **não gera automaticamente essas referências semânticas**. O contrato suporta referências futuras de conteúdo, placement, gabarito, identificadores e associações sem criar tais entidades agora. Quando só o recurso for conhecido, usar referência documental sem fingir precisão de página/linha.

Divergências devem ser preservadas pelas camadas que as identificarem. Não implementar descoberta ou resolução de conflito semântico na ingestão. Evidências fornecidas explicitamente como contexto não podem ser perdidas ou conciliadas silenciosamente.

# 12. IngestionRun e unidades solicitadas

Toda invocação cria exatamente um `IngestionRun`, inclusive reingestão ou tentativa com input inexistente. Criar a identidade da execução antes de validar o input; etapas internas não criam runs adicionais.

| Campo | Categoria e semântica |
| --- | --- |
| `id` | Obrigatório |
| `pipeline_name`, `pipeline_version` | Obrigatórios; identificam código/comportamento executado. |
| `started_at` | Obrigatório |
| `status` | Obrigatório |
| `parameters` | Obrigatório; inclui opções e limites efetivos, pode ser objeto vazio quando não houver parâmetros aplicáveis. |
| `finished_at` | Nullable enquanto `RUNNING`; obrigatório ao finalizar normalmente. |
| `code_revision` | Nullable quando indisponível; não dispensa versão do pipeline. |
| Inputs/outputs e resultados por unidade | Obrigatórios quando necessários ao lineage; representação simples, sem tabela/grafo obrigatório. |

Para uma entrada local, a unidade principal é preservá-la/registrar aquisição. Em operação ZIP, listagem e materialização solicitadas têm resultados identificáveis no mesmo run. Um ZIP preservado com sucesso e um membro solicitado que falhe podem produzir `PARTIAL`. Falha do pré-requisito que impeça todas as saídas solicitadas confiáveis produz `FAILED`.

Unidades não solicitadas não contam como falha: listar sem materializar não é execução parcial. Reutilizar payload íntegro satisfaz a unidade, mesmo sem criar novo conteúdo. A identificação de unidades não implica API de lote ou múltiplos membros no primeiro incremento.

Se o armazenamento operacional estiver indisponível a ponto de impedir registrar o próprio run, abortar com `FATAL` e relatório de diagnóstico com a identidade alocada na saída do comando; não declarar que a persistência ocorreu. Não publicar payload novo nessa condição. Não criar um segundo banco/log autoritativo para contornar a falha.

# 13. Status e severidade

| Status | Semântica |
| --- | --- |
| `RUNNING` | Execução iniciada e não finalizada. |
| `SUCCESS` | Todas as operações solicitadas concluídas com sucesso. |
| `PARTIAL` | Pelo menos uma unidade solicitada concluída e pelo menos uma falhou, sem falha estrutural que inviabilize a execução inteira. |
| `FAILED` | Nenhuma saída solicitada confiável produzida, ou falha que inviabilize a execução como um todo. |

`PARTIAL` não depende de registros CSV. Pode futuramente abranger lotes ou parsing, mas isso não amplia o primeiro incremento. Uma falha estrutural prevalece na classificação final do run; conteúdos já registrados com integridade não são apagados por causa dela.

| Severidade | Semântica |
| --- | --- |
| `INFO` | Informação operacional. |
| `WARNING` | Problema não bloqueante. |
| `ERROR` | Falha de uma unidade processável; pode ser possível continuar. |
| `FATAL` | Falha que compromete a execução inteira. |

Não existe “FATAL para aquele recurso”. Hash divergente de payload específico gera `ERROR` e impede seu reuso. Problema estrutural do armazenamento/execução pode justificar `FATAL`. O status decorre dos resultados solicitados, não apenas da existência de um warning ou de um recurso raw previamente preservado.

# 14. IngestionIssue e relatório

| Campo de issue | Categoria |
| --- | --- |
| `id`, `run_id`, `stage`, `severity`, `message` | Obrigatórios |
| `resource_id`, `input_reference`, `locator`, `exception_type` | Nullable |

Falha de leitura, caminho ou validação inicial deve admitir `resource_id = null`, identificando a entrada em `input_reference` quando possível. Se um locator estiver presente e também houver `resource_id`, ambos devem concordar. Issues podem ser estruturas dentro do run; tabela separada é opcional.

Toda execução deve emitir relatório serializável com:

- `run_id`, status e resultados das unidades solicitadas;
- `resources_seen`, `resources_created`, `resources_reused`, `resources_failed`;
- warnings/errors e issues com stage e causa;
- referências aos recursos e hashes conhecidos, aquisições e lineage;
- limitações/metadados ausentes quando relevantes à operação.

Os contadores de recursos representam tentativas de preservação de arquivo/membro, não quantidade de entradas apenas listadas. Ao encerrar, `resources_seen = resources_created + resources_reused + resources_failed`; uma tentativa iniciada mas não concluída por interrupção deve ser reportada como falha ao reconciliar o run. Falhas de listagem não são recursos novos: aparecem nas unidades/issues.

Sem parsing neste incremento, `records_read`, `records_accepted` e `records_rejected`, se expostos, são `null` (não aplicável), não zero para simular um parser executado. Quantidade de entradas ZIP listadas é informação distinta. Parsers futuros definirão seus contadores, motivos de rejeição e recuperação por locator conforme SPEC-002.

Relatório final deve refletir SQLite. Se houver falha de persistência, informar isso explicitamente na saída de diagnóstico. Retorno de execução parcial/falha não pode parecer sucesso completo; convenções de saída do comando serão documentadas na implementação.

# 15. Lineage, determinismo e idempotência

Todo output produzido deve permitir recuperar input(s), pipeline, versão e parâmetros relevantes. Referências podem ficar no run/acquisition, sem lineage graph.

Para cópia de arquivo local, aquisição registra contexto recebido; hash/tamanho representam o snapshot preservado, e o run registra a operação. O caminho externo não é dependência necessária para recuperar o conteúdo após ingestão.

Para membro, o input é o ZIP raw identificado, mais o nome exato selecionado; o output é o recurso dos bytes descomprimidos. Registrar limites/opções efetivos e versão da extração. Não classificar referências necessárias a essa relação como meramente recomendadas.

Determinismo significa: mesmos inputs, versão e parâmetros produzem o mesmo output lógico da operação. IDs de run, timestamps e outros metadados operacionais não fazem parte desse output determinístico. Para cópia/materialização raw, a propriedade é direta: mesmos bytes preservados → mesmo SHA-256 e tamanho.

Uma reingestão íntegra mantém um recurso e acrescenta o run e aquisição da nova observação. Não confundir idempotência de conteúdo com ausência de histórico operacional. Deduplicação é somente **exact content deduplication**, sem fuzzy matching, similaridade textual, fingerprint normalizado ou fusão de `Question`.

# 16. Protocolo mínimo de publicação

SQLite é a autoridade dos metadados; bytes raw ficam no filesystem. Um recurso só é considerado registrado e válido quando payload completo e metadados correspondentes estiverem publicados e íntegros.

Fluxo obrigatório para novo conteúdo:

1. Criar run e validar parâmetros/acesso ao armazenamento sob a limitação single writer.
2. Abrir input regular em leitura; copiar em streaming para arquivo temporário controlado, no mesmo filesystem do destino final.
3. Calcular SHA-256 e contar bytes **durante a própria cópia**, aplicando limites efetivos. Não fazer hash de uma leitura e copiar o input em outra leitura posterior.
4. Fazer flush/close, conferir tamanho e validar o hash do temporário antes da publicação. A conferência pode reler o temporário controlado; não reler a origem como prova dos bytes copiados.
5. Consultar identidade/destino. Se existir, aplicar §17. Caso contrário, publicar o temporário completo no destino final sem sobrescrita.
6. Registrar recurso, aquisição e vínculos/resultados necessários em transação SQLite. Só após commit a unidade é anunciada como concluída.
7. Finalizar status/relatório do run após as operações solicitadas.

A operação de publicação deve usar destino controlado e impedir substituição de payload existente. Limitar suporte ao filesystem local em que a publicação segura no mesmo filesystem seja possível; erro nessa condição é explícito, não fallback para cópia parcial anunciada como válida.

Se a origem mudar durante a leitura, o hash anunciado deve sempre corresponder aos bytes efetivamente copiados/validados. Não prometer snapshot atômico do arquivo externo: mudança detectada pode causar falha explícita; jamais usar hash de conteúdo anterior para o payload final.

A transação SQLite não torna filesystem e banco uma transação única. A janela entre publicação do payload e commit é tratada pelo procedimento simples de recuperação (§18), sem transação distribuída.

# 17. Reuso e integridade divergente

Destino correspondente ao hash já existente **não é sobrescrito**. No primeiro incremento, verificar tamanho e recalcular SHA-256 do payload existente antes de reutilizar. Assim, corrupção do mesmo tamanho também é detectada; não confiar apenas no registro do banco.

Se payload ou metadados mínimos divergem, falhar explicitamente, não registrar aquisição bem-sucedida e não “corrigir” automaticamente o hash esperado. Preservar diagnóstico e originais existentes. Recuperação de corrupção não se confunde com reconciliação de payload íntegro ainda sem metadados.

Registro com payload ausente ou parcial não pode ser devolvido como íntegro. Ter linha em SQLite é necessário para registro, mas não prova sozinho integridade física.

# 18. Recuperação e single writer

Estratégia escolhida para o primeiro incremento:

- Temporários nunca são recursos válidos. Com exclusividade de escrita confirmada, uma nova execução pode limpar temporários abandonados, registrando a ação.
- Run abandonado em `RUNNING` deve ser identificável. Ao reconciliá-lo, registrar interrupção e finalizar como `FAILED`, com horário de recuperação e causa; não inventar horário exato da interrupção. Preservar as unidades já confirmadas e recursos íntegros.
- Payload final sem linha correspondente em SQLite é órfão **não registrado**. Não usá-lo silenciosamente como recurso válido nem fabricar aquisição histórica.
- Reconciliação mínima: uma reingestão explícita do mesmo conteúdo verifica tamanho/hash do órfão. Se íntegro, pode registrar recurso e aquisição da execução atual em transação, indicando recuperação. Não inventar origem ou data do run anterior. Se divergente, falhar sem sobrescrever.
- Órfãos não reencontrados permanecem detectáveis pela comparação entre destinos controlados e registros SQLite, sem remoção automática de payload final. Não é necessário serviço de varredura contínua.

A implementação deve impedir sobreposição de writers por mecanismo local simples de exclusividade/falha imediata e documentar essa limitação. Não criar filas, scheduler ou coordenação distribuída. Não limpar temporários pertencentes a execução ativa.

Se uma unidade já estiver confirmada no banco antes da interrupção do relatório, a recuperação não repete nem desfaz aquela aquisição; registra o run interrompido. Uma nova invocação de ingestão é outro run/observação, conforme §15.

# 19. Segurança e limites de ZIP

Listar a partir do ZIP raw preservado, sem executar conteúdo e sem criar recursos para cada entrada. Seleção utiliza nome exato, nunca glob ou seleção automática.

Rejeitar seleção/materialização quando:

- nome contém componente de traversal (`..`), caminho absoluto, raiz/unidade ou separadores que escapariam ao destino controlado;
- resolução atravessaria link ou escreveria fora do espaço controlado;
- entrada é symlink/link especial ou não é arquivo regular compatível com a política;
- nome exato selecionado aparece mais de uma vez;
- limites, integridade do ZIP ou método de leitura necessário não puderem ser respeitados.

Listagem pode apresentar entradas inseguras ou duplicadas como não selecionáveis, com aviso explícito, sem escrevê-las. Não sanitizar nomes distintos para o mesmo destino nem escolher silenciosamente uma ocorrência duplicada. Materialização solicitada de entrada proibida gera `ERROR`.

Não reproduzir a árvore de paths do ZIP no raw: o destino final deriva da identidade de conteúdo. Mesmo assim, nomes perigosos devem ser rejeitados conforme contrato. ZIP aninhado permanece bytes; não realizar extração recursiva implícita. Conteúdo nunca é executado, importado como código ou aberto para executar macros.

Limites obrigatórios, finitos e configuráveis:

| Parâmetro | Alcance |
| --- | --- |
| `max_input_bytes` | Bytes lidos do arquivo local/ZIP de entrada. |
| `max_zip_members` | Entradas admitidas na listagem/inspeção do ZIP. |
| `max_member_uncompressed_bytes` | Bytes efetivamente descomprimidos do membro selecionado. |
| `max_total_uncompressed_bytes` | Total descomprimido pela execução; mesmo com um membro, o limite permanece explícito. |

Defaults finitos devem ser centralizados, documentados e registrados entre parâmetros efetivos do run. A spec não fixa números universais. Testes usam limites pequenos. Não desabilitar limites implicitamente.

Verificar limites durante leitura/escrita quando aplicável, não apenas nos tamanhos anunciados pelo ZIP. Interromper ao exceder, limpar temporário de membro não publicado e registrar issue. O ZIP íntegro já preservado permanece. Hashing/cópia devem operar em streaming; não carregar payload inteiro na memória por conveniência.

# 20. Manifesto e modelo físico mínimo

**SQLite é a única fonte de verdade dos metadados operacionais.** Payloads ficam no filesystem. Metadados persistidos constituem o manifesto auditável equivalente exigido pela SPEC-002.

Um `manifest.json`, se produzido, é export/view serializável derivado de SQLite, identificável como snapshot. Não é segunda autoridade nem pode atualizar o banco automaticamente. Reexportar a partir da autoridade evita duas lógicas de atualização divergentes. Não é obrigatório gravar sidecar JSON dentro de raw.

Modelo físico esperado:

| Tabela | Conteúdo |
| --- | --- |
| `source_resource` | Conteúdo, hash/tamanho, media type nullable, endereço e registro. |
| `resource_acquisition` | Origens, timestamps de observação, nomes recebidos, catálogo/provider conhecidos, parent/member e run. |
| `ingestion_run` | Execução, parâmetros, resultados, lineage e relatório/issues estruturados. |
| `ingestion_issue` | Opcional, somente se separar issues melhorar a clareza operacional. |

Exigir integridade das referências, unicidade operacional de SHA-256 e coerência de hash/tamanho/payload. O recurso tem zero ou mais aquisições; cada aquisição tem exatamente um recurso e um run. Os detalhes de IDs e colunas físicas podem ser definidos na implementação sem mudar essa semântica.

Não criar tabelas obrigatórias para `EvidenceReference`, `SourceLocator`, catálogo, fatos, supersessão genérica ou lineage graph. Runs/acquisitions e estruturas embutidas bastam. Nenhuma nova tecnologia é necessária: filesystem local, SQLite e Python da stack existente.

# 21. Retificações e supersessão

Nova versão com bytes diferentes cria ou referencia outro recurso e preserva o anterior. Uma mesma URL pode aparecer em aquisições de vários recursos; várias URLs podem aparecer em aquisições do mesmo recurso.

Supersessão exige declaração/evidência explícita da fonte e contexto pertinente. `observed_at` ou `source_retrieved_at` mais recentes não provam substituição. Não criar relação de supersessão consigo mesmo quando os bytes forem iguais.

Manter esta semântica, mas adiar mecanismo genérico e resolução automática. Uma declaração explícita pode permanecer documentada junto ao contexto fornecido, sem exigir tabela ou parser. Nenhuma substituição de recurso propaga automaticamente anulação, gabarito ou estado de `Question`.

Conflitos interpretados posteriormente preservam as observações e evidências conforme SPEC-003. Aquisição não decide qual alternativa está correta nem detecta identidade semântica.

# 22. Media type, Git e fontes incompletas

Media type básico é nullable. Extensão do nome recebido é somente evidência auxiliar; não implementar detector universal. Conteúdo desconhecido pode ser preservado com sucesso como bytes sem interpretação de formato. Operação ZIP exige que seja possível tratar o conteúdo como ZIP válido, independentemente da extensão.

Fixtures pequenas, contratos, testes e manifestos de teste podem ser versionados. Payloads reais e SQLite operacional não devem entrar no Git. Exports operacionais não são automaticamente material versionável; preservar a política de dados e não incluir secrets, URLs com credenciais ou diagnóstico sensível em manifestos públicos.

Fonte sem bytes pode existir futuramente como catálogo/pendência, não como recurso materializado válido com hash fabricado. No primeiro incremento, input inexistente gera run/issue e falha, sem cadastrar recurso de conteúdo imaginário.

# 23. Invariantes consolidados

A numeração desta versão consolida os invariantes do Draft v1; a tabela abaixo é a referência completa vigente.

| ID | Invariante |
| --- | --- |
| INV-004-001 | `SourceResource` representa conteúdo binário, não contexto de origem. SHA-256 não prova oficialidade, semântica ou identidade de questão. |
| INV-004-002 | SHA-256 e tamanho correspondem aos bytes finais efetivamente preservados; metadados operacionais não integram identidade binária. |
| INV-004-003 | Raw registrado é imutável: reexecução, falha e retificação não sobrescrevem bytes nem recriam raw a partir de dados normalizados. |
| INV-004-004 | Deduplicação exata reutiliza conteúdo, preservando origens distintas e todas as aquisições anteriores. |
| INV-004-005 | Toda aquisição bem-sucedida referencia um recurso íntegro e exatamente um run identificável. |
| INV-004-006 | Um recurso admite zero ou mais aquisições; mesmo membro pode ter aquisições via contêineres distintos ou arquivo direto. |
| INV-004-007 | URL/provider/catálogo desconhecidos permanecem nullable; observação local não fabrica data de coleta remota. Fixtures sintéticas são identificadas e não recebem origem oficial inventada. |
| INV-004-008 | Toda invocação gera um run; reuso de conteúdo não elimina histórico operacional. |
| INV-004-009 | Todo output produzido possui inputs, pipeline/versão e parâmetros relevantes recuperáveis. |
| INV-004-010 | Status reflete operações solicitadas; falha de unidade não se confunde com falha estrutural da execução. |
| INV-004-011 | Issue pode existir antes do recurso, com `resource_id = null`. |
| INV-004-012 | Um recurso anunciado como registrado/válido não aponta para payload parcial ou ausente. Órfãos não registrados não são consumidos silenciosamente. |
| INV-004-013 | Reutilização exige validar payload existente; divergência de hash/tamanho falha sem sobrescrever ou corrigir automaticamente metadados esperados. |
| INV-004-014 | Membro apenas listado não cria recurso; membro materializado possui hash/tamanho próprios dos bytes descomprimidos e aquisição parent/member. |
| INV-004-015 | Entrada externa nunca controla diretamente path final; não pode escapar do armazenamento controlado. |
| INV-004-016 | Membro perigoso, link incompatível ou seleção por nome duplicado é rejeitado; conteúdo externo nunca é executado. |
| INV-004-017 | Limites de input, membros e descompressão são finitos/configuráveis e verificados durante leitura quando aplicável. |
| INV-004-018 | ZIP não é extraído em massa, selecionado automaticamente ou processado recursivamente de forma implícita. |
| INV-004-019 | Locator possui exatamente um recurso de referência e semântica de coordenadas explícita; evidência não duplica essa referência. |
| INV-004-020 | Preservar fonte ou rotular evidência não transforma inferência em fato oficial; aquisição não gera associação semântica automaticamente. |
| INV-004-021 | Conteúdo mais recente não supersede anterior sem evidência explícita; conflitos não são conciliados silenciosamente. |
| INV-004-022 | SQLite é a autoridade dos metadados; JSON de manifesto é somente export/view. |
| INV-004-023 | Primeiro incremento é sequencial/single writer e não depende de LLM, OCR ou interpretação de questões. |

# 24. Casos conceituais e testes de aceite

Hashes como AAA/BBB abaixo são rótulos ilustrativos. Testes de implementação devem calcular SHA-256 real de fixtures e comparar com valores esperados independentes do código testado. Nenhum teste exige download HTTP ou datasets reais.

## Caso A — Arquivo novo

Arquivo local legível → um run `SUCCESS`, um recurso, uma aquisição e payload independente preservado. SQLite contém o manifesto equivalente; relatório mostra `resources_created = 1`. Hash/tamanho conferem com os bytes finais. URL/provider podem ser nulos.

## Caso B — Reexecução

Ingerir duas vezes os mesmos bytes → um recurso, dois runs e duas aquisições nesta política do MVP. Segundo run valida payload e reporta reuso. Nenhum raw é sobrescrito; timestamps/IDs dos runs diferem sem quebrar determinismo do conteúdo.

## Caso C — Mesmo caminho/URL, conteúdo diferente

Fornecer dois arquivos locais sucessivos, ou alterar a origem local entre invocações, mantendo a mesma URL informativa → conteúdos AAA e BBB preservados em dois recursos. Aquisições registram `observed_at` de cada execução; não inventar data de download nem supersessão.

## Caso D — Mesmos bytes, nomes e origens diferentes

Nome A e nome B, URLs e `source_definition_id` diferentes fornecidos como contexto → um recurso e N aquisições preservando nomes, origens e catálogos conhecidos. Uma segunda origem não muda os metadados intrínsecos nem apaga a primeira.

## Caso E — ZIP listado e membro selecionado

ZIP local é preservado e listado. Só a listagem não cria recursos de membros. Ao solicitar `dados.csv`, registrar bytes descomprimidos em raw, SHA-256/tamanho próprios e aquisição com `acquisition_method = CONTAINER_MEMBER`, parent = recurso ZIP e `container_locator = dados.csv`. Nenhuma cópia interim automática.

## Caso F — ZIP traversal

Selecionar `../../evil.txt` → rejeição, issue `ERROR`, nenhum arquivo fora do destino controlado e nenhum payload parcial registrado. O ZIP já preservado permanece. Nomes inseguros podem ser listados somente como não selecionáveis.

## Caso G — Payload raw corrompido

SQLite registra AAA, mas payload foi corrompido, inclusive variante com o mesmo tamanho → reingestão falha explicitamente na validação, não reutiliza silenciosamente, não publica nova aquisição bem-sucedida e não corrige manifesto ou sobrescreve payload.

## Caso H — Evidência em PDF como contrato

Uma observação fornecida pelo teste contém locator `{resource_id: R, locator_type: PDF_PAGE, locator_value: {page_index: 1}}` e papel `ANSWER_KEY`. Significa segunda página física, não página impressa 1. Não há `resource_id` duplicado na raiz. O teste valida estrutura/serialização, sem parser de PDF nem criação automática de evidência pela aquisição.

## Caso I — Evidências conflitantes fornecidas

Duas declarações de teste apontam a recursos diferentes para valores C e D. As estruturas preservam ambas e o contexto de divergência, sem escolher uma. Ingestão dos arquivos não detecta semanticamente essa divergência nem resolve gabarito; essa responsabilidade é posterior.

## Caso J — Execução parcial por unidades solicitadas

Em um run, preservação/listagem de ZIP concluem, mas materialização do membro explicitamente solicitado falha → `PARTIAL`, unidades bem-sucedidas/falhas identificadas e issue recuperável. Se nenhuma unidade solicitada for concluída, `FAILED`. Sem membro solicitado, apenas listar com sucesso é `SUCCESS`, não `PARTIAL`. Falha estrutural da execução inteira leva a `FAILED` mesmo havendo recursos anteriores preservados.

## Caso K — Fixture e origem desconhecida

Fixture sintética direta → método `FIXTURE`, `fixture_kind = SYNTHETIC`, URL/provider/catalogo oficiais não fabricados. Membro de fixture ZIP conserva natureza sintética na aquisição. Fixture derivada de material real preserva origem conhecida e limitações. Não confundir sucesso técnico com origem oficial.

## Caso L — Versão posterior e supersessão

V1 e V2 são preservados separadamente quando os bytes diferem. Sem declaração explícita, V2 mais recente **não** supersede V1. Havendo evidência fornecida, ela pode permanecer documentada sem resolução automática/tabela genérica. Nenhuma alteração é propagada ao domínio de questões.

## Caso M — Mesmo membro em dois ZIPs

ZIP A e ZIP B têm bytes diferentes, mas contêm membro binário idêntico → um recurso do membro e duas aquisições `CONTAINER_MEMBER`, cada qual com seu parent e nome exato. Recursos dos ZIPs são distintos; nenhum parent é armazenado no recurso do membro.

## Caso N — Arquivo direto e membro

Mesmo conteúdo fornecido diretamente e como membro de ZIP → um recurso do conteúdo, duas aquisições: `LOCAL_FILE` e `CONTAINER_MEMBER`. Para a direta, parent/member são nulos. A aquisição via contêiner não substitui a direta.

## Caso O — Input inexistente ou inacessível

Run é criado antes da validação. Input inexistente, ilegível ou não regular → issue com `resource_id = null`, entrada identificável e run `FAILED`; nenhum recurso/acquisition bem-sucedida fabricados. Falha do próprio SQLite deve produzir diagnóstico `FATAL` sem fingir persistência ou publicar payload novo.

## Caso P — Media type desconhecido

Arquivo regular cujo tipo não pode ser determinado com confiança → ingestão pode terminar `SUCCESS`, com `media_type = null`, hash/tamanho e origem disponíveis preservados. Extensão não autoriza inventar tipo.

## Caso Q — Input alterado durante cópia

Simular alteração da origem durante leitura. Operação pode falhar explicitamente se detectar mudança; se publicar, SHA-256/tamanho devem corresponder aos bytes do payload final, nunca a leitura anterior independente da origem. Verificar também que alterar a origem depois não modifica raw.

## Caso R — Escrita interrompida e recuperação

Injetar falha durante cópia → temporário não aparece como recurso válido. Injetar falha após publicação final e antes do commit → payload órfão detectável, não registrado. Reingestão explícita com mesmos bytes valida órfão e reconcilia na execução atual, sem inventar aquisição passada. Órfão divergente falha sem sobrescrita. Testar também registro existente com payload ausente e run abandonado em `RUNNING`.

## Caso S — Caminho absoluto e links

ZIP com path absoluto ou link perigoso, bem como escape por link no destino → rejeição; nenhum arquivo fora do diretório controlado. Nomes recebidos não determinam destino final e a cópia não pode ser link para origem mutável. Nenhum conteúdo é executado.

## Caso T — Nomes duplicados em ZIP

Duas entradas com o mesmo nome exato selecionado → materialização rejeitada como ambígua. Não escolher primeira/última ocorrência nem sobrescrever uma com outra. Listagem informa a ambiguidade, sem criar recursos de membro.

## Caso U — Limites finitos

Testar separadamente `max_input_bytes`, `max_zip_members`, `max_member_uncompressed_bytes` e `max_total_uncompressed_bytes` com defaults/overrides pequenos. Exceder limite durante leitura/descompressão interrompe a unidade, registra issue e não publica parcial. Não confiar apenas em metadados anunciados pelo ZIP. Incluir fronteira exatamente no limite e tentativa acima dele.

## Caso V — Locator round-trip

Serializar/desserializar exemplos dos seis tipos preserva recurso, índices, nome exato, range e configuração de parser. CSV multiline mantém significado de registro lógico; PDF usa zero-based físico; planilha usa intervalo explícito; JSON Pointer preserva tokens sem executar query própria. Esse teste não exige resolvers dos formatos adiados.

## Caso W — Manifesto, lineage e single writer

Recurso e aquisições exportados refletem SQLite; não há segundo estado autoritativo. Para membro, recuperar ZIP de input, nome selecionado, output, pipeline/versão, limites e parâmetros efetivos. Impedir segundo writer simultâneo. Testar que listagem não gera aquisições de membros nem evidências semânticas.

## Caso X — Sem extração recursiva

Selecionar membro que também seja ZIP preserva seus bytes e aquisição, sem extrair seu conteúdo. Sem seleção explícita, nenhum membro é materializado. Nenhuma operação de lote/seleção automática é acionada.

# 25. Critérios de conclusão e consistência

A implementação estará adequada quando os casos A–X forem cobertos conforme sua natureza: comportamento operacional testado com fixtures e contratos futuros validados estruturalmente. Não executar parsers fora de escopo para satisfazer exemplos conceituais.

Os testes devem verificar integridade, contagens/status, fontes múltiplas, issues antes do recurso, publicação incompleta/reuso, segurança/limites e recuperação de lineage. Erros não podem ser silenciosos. Testes de contratos de evidência não equivalem a validar fatos de domínio.

## Bloqueios resolvidos

| Parecer | Correção nesta revisão |
| --- | --- |
| B1 — conteúdo versus origem | Contratos separados e parent/member em aquisição (§§4–5, 8). |
| B2 — nulabilidade e timestamps | Campos explícitos, especialização da SPEC-002, fixtures e input/storage separados (§§3–7). |
| B3 — membro raw versus interim | Membro selecionado é raw com hash próprio; transformado é interim (§§8–9). |
| B4 — localizadores/evidência | Seis tipos com convenções claras, recurso somente no locator e evidência como contrato (§§10–11). |
| B5 — runs/lineage/issues | Um run por invocação, lineage obrigatório, estados por unidade e erro sem recurso (§§12–15). |
| B6 — atomicidade/segurança | Cópia com hashing, validação/reuso, recuperação e limites ZIP (§§16–19). |

## Consistency Check

- **SPEC-001:** mantém aplicação pessoal, simplicidade, stack existente, cálculos determinísticos e ausência de LLM no fluxo mínimo. Não implementa features pedagógicas.
- **SPEC-002:** mantém raw imutável, SHA-256, lineage, fontes distinguíveis e proteção de secrets. §6 registra explicitamente a especialização aprovada de metadados desconhecidos em aquisição local; §7 especializa layout sem alterar stages; §15 separa output determinístico de metadados operacionais; §20 mantém manifesto equivalente em SQLite.
- **SPEC-003:** oferece recursos/evidências para revisões, placements, gabaritos e associações sem criá-los. Não confunde identidade binária com identidade de questão, nem retificação de arquivo com supersessão automática de observação de domínio. Representações do caderno podem usar recursos distintos ou compartilhados conforme bytes, com contexto de origem preservado.

## Fora de escopo e próximo passo

Não implementar HTTP download automático, scraping, browser automation, parsing de prova ou microdados, OCR, criação de Question/QuestionPlacement/AnswerKeyObservation, resolução de alternativas, classificação, analytics, mastery, recomendação, RAG ou autenticação.

Também ficam fora: extração em massa/recursiva, processamento paralelo, múltiplos writers, resolvers de todos os formatos, tabelas genéricas de fatos/evidências/supersessão, workflow engine, serviços de provenance, grafos, cloud e object storage remoto.

Não há decisão bloqueante remanescente. Defaults finitos, detalhes de CLI, IDs e armazenamento de issues são escolhas de implementação a documentar dentro deste contrato, não novas decisões de produto.

**Próximo passo: implementar a SPEC-004.** Não é necessário escrever outra spec antes; esta revisão documental não executa essa implementação.
