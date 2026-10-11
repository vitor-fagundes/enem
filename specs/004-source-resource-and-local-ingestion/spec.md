# Feature Specification: Source Resource and Local Ingestion Contract

**Feature Branch**: `N/A (retrospective migration; no branch created)`

**Created**: 2026-09-18

**Status**: Draft

**Input**: User description: "Migrar retrospectivamente `specs/004-source-resource-and-local-ingestion.md` para o formato nativo do GitHub Spec Kit, preservando integralmente seu significado, sem implementar código, sem alterar as demais specs e sem apagar o legado."

## Migration Provenance

Este artefato foi reconstruído retrospectivamente durante a migração para o GitHub Spec Kit. Ele expressa no formato atual o contrato de aquisição e ingestão local de recursos originalmente registrado em `specs/004-source-resource-and-local-ingestion.md`; não representa uma nova feature, não declara requisitos como já implementados e não autoriza implementação neste incremento. Esta especificação define o contrato de aquisição e ingestão mínima do primeiro incremento: como bytes são recebidos, verificados, preservados, deduplicados e rastreados. O documento legado permanece preservado como fonte histórica da migração.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ingerir arquivo local com integridade e deduplicação exata (Priority: P1)

Como operador de ingestão, preciso fornecer um arquivo local e obter recurso preservado com SHA-256, aquisição com contexto de origem e relatório de execução para que os bytes sejam rastreáveis, deduplicados por conteúdo e auditáveis.

**Why this priority**: Sem ingestão básica de arquivo local, nenhuma fonte pode ser preservada, rastreada ou utilizada pelo modelo de domínio.

**Independent Test**: Pode ser testada ingerindo um arquivo local, reingerindo os mesmos bytes, ingerindo os mesmos bytes com origem diferente, e verificando um recurso com N aquisições, hashes íntegros e sem fabricação de origem.

**Acceptance Scenarios**:

1. **Given** arquivo local legível, **When** ingerido, **Then** um run `SUCCESS`, um recurso com SHA-256/tamanho correspondentes aos bytes finais preservados, uma aquisição e payload independente preservado em raw. SQLite contém o manifesto equivalente; relatório mostra `resources_created = 1`. URL/provider podem ser nulos. *(Case A)*
2. **Given** mesmos bytes ingeridos duas vezes, **When** a segunda execução ocorre, **Then** um recurso, dois runs e duas aquisições. Segundo run valida payload e reporta reuso. Nenhum raw é sobrescrito; timestamps/IDs dos runs diferem sem quebrar determinismo do conteúdo. *(Case B)*
3. **Given** mesmos bytes com nomes, URLs e `source_definition_id` diferentes fornecidos como contexto, **When** ingeridos, **Then** um recurso e N aquisições preservando nomes, origens e catálogos conhecidos. Uma segunda origem não muda metadados intrínsecos nem apaga a primeira. *(Case D)*

---

### User Story 2 - Preservar ZIP e materializar membro selecionado com segurança (Priority: P1)

Como operador de ingestão, preciso preservar um ZIP inteiro, listar seus membros, selecionar explicitamente no máximo um membro e materializar seus bytes descomprimidos com hash próprio para que contêineres e membros sejam rastreáveis, seguros e auditáveis.

**Why this priority**: Fontes oficiais do ENEM são distribuídas em ZIP; sem preservação do contêiner e materialização segura de membros, os recursos internos não podem ser ingeridos.

**Independent Test**: Pode ser testada preservando um ZIP, listando-o sem criar recursos de membros, materializando um membro selecionado com hash próprio e verificando aquisição CONTAINER_MEMBER com parent e nome exato.

**Acceptance Scenarios**:

1. **Given** ZIP local preservado e listado, **When** membro `dados.csv` é selecionado, **Then** ZIP é recurso raw com aquisição própria. Listagem não cria recursos de membros. Membro materializado possui bytes descomprimidos em raw, SHA-256/tamanho próprios e aquisição `CONTAINER_MEMBER` com `parent_resource_id` = recurso ZIP e `container_locator = dados.csv`. Nenhuma cópia interim automática. *(Case E)*
2. **Given** ZIP A e ZIP B com bytes diferentes contendo membro binário idêntico, **When** ambos os membros são materializados, **Then** um recurso do membro e duas aquisições `CONTAINER_MEMBER`, cada qual com seu parent e nome exato. Recursos dos ZIPs são distintos; nenhum parent é armazenado no recurso do membro. *(Case M)*
3. **Given** mesmo conteúdo fornecido diretamente e como membro de ZIP, **When** ambos são ingeridos, **Then** um recurso do conteúdo, duas aquisições: `LOCAL_FILE` e `CONTAINER_MEMBER`. Para a direta, parent/member são nulos. A aquisição via contêiner não substitui a direta. *(Case N)*

---

### User Story 3 - Executar runs com falhas explícitas, publicação atômica e recuperação (Priority: P1)

Como operador de ingestão, preciso que toda execução registre um run com status por unidades solicitadas, que falhas sejam explícitas com issues, que publicação seja atômica e que recuperação de interrupção não invente histórico para que o estado operacional seja sempre confiável e auditável.

**Why this priority**: Sem falhas explícitas, publicação atômica e recuperação confiável, o operador não pode confiar no estado dos recursos nem diagnosticar problemas.

**Independent Test**: Pode ser testada injetando falhas durante cópia, após publicação e antes do commit, e verificando runs abandonados, temporários, órfãos e reconciliação íntegra.

**Acceptance Scenarios**:

1. **Given** preservação/listagem de ZIP concluídas mas materialização do membro solicitado falha, **When** o run finaliza, **Then** status `PARTIAL`, unidades bem-sucedidas/falhas identificadas e issue recuperável. Se nenhuma unidade solicitada for concluída, `FAILED`. Sem membro solicitado, apenas listar com sucesso é `SUCCESS`. Falha estrutural inteira leva a `FAILED` mesmo havendo recursos anteriores. *(Case J)*
2. **Given** falha durante cópia ou após publicação final e antes do commit, **When** recuperação ocorre, **Then** temporário não aparece como recurso válido. Payload órfão sem registro em SQLite é detectável, não registrado. Reingestão explícita com mesmos bytes valida órfão e reconcilia na execução atual, sem inventar aquisição passada. Órfão divergente falha sem sobrescrita. Registro existente com payload ausente e run abandonado em `RUNNING` são identificáveis. *(Case R)*
3. **Given** SQLite registra hash AAA mas payload foi corrompido, inclusive variante com o mesmo tamanho, **When** reingestão ocorre, **Then** falha explícita na validação, sem reutilização silenciosa, sem nova aquisição bem-sucedida, sem correção de manifesto ou sobrescrita de payload. *(Case G)*

---

### User Story 4 - Localizar e evidenciar fatos com contratos serializáveis (Priority: P2)

Como camada futura de interpretação, preciso de contratos de localização e evidência serializáveis que preservem recurso, tipo, coordenadas, papel e divergências para que revisões, gabaritos e associações possam referenciar posições precisas sem tabelas obrigatórias.

**Why this priority**: Sem contratos de localização e evidência, camadas futuras não podem vincular fatos de domínio a posições específicas nos recursos preservados.

**Independent Test**: Pode ser testada serializing/deserializando localizadores dos seis tipos e evidências com papéis distintos, verificando round-trip e preservação de divergências.

**Acceptance Scenarios**:

1. **Given** observação de teste com locator `{resource_id: R, locator_type: PDF_PAGE, locator_value: {page_index: 1}}` e papel `ANSWER_KEY`, **When** é registrada, **Then** representa segunda página física (zero-based), sem `resource_id` duplicado na raiz. Teste valida estrutura/serialização, sem parser de PDF nem criação automática de evidência pela aquisição. *(Case H)*
2. **Given** exemplos dos seis tipos de localizador, **When** serializados e desserializados, **Then** preservam recurso, índices, nome exato, range e configuração de parser. CSV multiline mantém significado de registro lógico; PDF usa zero-based físico; planilha usa intervalo explícito; JSON Pointer preserva tokens sem executar query. Teste não exige resolvers dos formatos adiados. *(Case V)*
3. **Given** duas declarações de teste apontando a recursos diferentes para valores C e D, **When** registradas, **Then** ambas são preservadas com contexto de divergência, sem escolher uma. Ingestão não detecta semanticamente essa divergência nem resolve gabarito; responsabilidade é posterior. *(Case I)*

### Edge Cases

- Fornecer dois arquivos locais sucessivos com mesmo caminho/URL mas conteúdo diferente → dois recursos preservados separadamente; não inventar supersessão. *(Case C)*
- Selecionar `../../evil.txt` em ZIP → rejeição, issue `ERROR`, nenhum arquivo fora do destino controlado, nenhum payload parcial. ZIP já preservado permanece. *(Case F)*
- Fixture sintética direta → método `FIXTURE`, `fixture_kind = SYNTHETIC`, URL/provider/catálogo oficiais não fabricados. Membro de fixture ZIP conserva natureza sintética. Fixture derivada de material real preserva origem conhecida e limitações. *(Case K)*
- V1 e V2 com bytes diferentes são preservados separadamente. Sem declaração explícita, V2 mais recente não supersede V1. Evidência fornecida pode permanecer documentada sem resolução automática/tabela genérica. Nenhuma alteração propaga ao domínio de questões. *(Case L)*
- Input inexistente, ilegível ou não regular → run criado antes da validação, issue com `resource_id = null`, entrada identificável e run `FAILED`; nenhum recurso/aquisição bem-sucedida fabricados. Falha do SQLite produz diagnóstico `FATAL` sem fingir persistência. *(Case O)*
- Arquivo regular com tipo não determinável → ingestão pode terminar `SUCCESS` com `media_type = null`, hash/tamanho e origem preservados. Extensão não autoriza inventar tipo. *(Case P)*
- Origem alterada durante leitura → operação pode falhar explicitamente; se publicar, SHA-256/tamanho MUST corresponder aos bytes do payload final, nunca a leitura anterior. Alterar a origem depois não modifica raw. *(Case Q)*
- ZIP com path absoluto ou link perigoso, escape por link no destino → rejeição; nenhum arquivo fora do diretório controlado. Nomes recebidos não determinam destino final. Nenhum conteúdo é executado. *(Case S)*
- Duas entradas com o mesmo nome exato selecionado → materialização rejeitada como ambígua; não escolher primeira/última ocorrência nem sobrescrever. Listagem informa ambiguidade sem criar recursos de membro. *(Case T)*
- Testar separadamente `max_input_bytes`, `max_zip_members`, `max_member_uncompressed_bytes` e `max_total_uncompressed_bytes` com defaults/overrides pequenos. Exceder limite durante leitura/descompressão interrompe a unidade, registra issue e não publica parcial. Incluir fronteira exatamente no limite e tentativa acima dele. *(Case U)*
- Recurso e aquisições exportados refletem SQLite; não há segundo estado autoritativo. Para membro, recuperar ZIP de input, nome selecionado, output, pipeline/versão, limites e parâmetros efetivos. Impedir segundo writer simultâneo. Listagem não gera aquisições de membros nem evidências semânticas. *(Case W)*
- Selecionar membro que também seja ZIP preserva seus bytes e aquisição, sem extrair seu conteúdo. Sem seleção explícita, nenhum membro é materializado. Nenhuma operação de lote/seleção automática é acionada. *(Case X)*

## Requirements *(mandatory)*

### Scope Boundaries

Esta especificação define o contrato de aquisição e ingestão local mínima do primeiro incremento. Ela cobre SourceResource, ResourceAcquisition, IngestionRun, IngestionIssue, SourceLocator, EvidenceReference, deduplicação exata por SHA-256, armazenamento raw, publicação atômica, recuperação, segurança de ZIP e limites finitos.

A ingestão MUST responder: quais bytes foram recebidos, por qual origem foram observados, quando esta execução os recebeu, como sua integridade foi verificada e qual operação os utilizou.

O primeiro incremento MUST suportar: (1) arquivo local → run → cópia segura → hash/tamanho → deduplicação exata → raw → recurso → aquisição → relatório; (2) ZIP local → preservação do ZIP → listagem segura → seleção explícita de no máximo um membro → materialização segura → hash/tamanho próprios → raw → aquisição vinculada ao ZIP; (3) reingestão, verificação de integridade, falhas explícitas e recuperação de publicação incompleta; (4) contratos serializáveis de localizador e evidência, sem tabelas ou interpretação semântica obrigatórias.

Somente execução sequencial e single writer. MUST NOT oferecer processamento paralelo, múltiplos writers, seleção automática ou extração recursiva. Uma execução que liste/ingira o ZIP e materialize seu membro continua sendo uma única invocação/run, com etapas internas.

O corpus prioritário permanece ENEM 2017–2025, aplicação regular, representação impressa padrão. Essa prioridade não limita o domínio nem exige adquirir esse corpus nesta implementação. Todos os testes usam fixtures pequenas, sem datasets completos.

A presente migração produz somente documentação: não implementa código, migrations, pipeline ou stack nova. A SPEC-001 define produto e simplicidade. A SPEC-002 define política de fontes, raw/interim/processed e proveniência. A SPEC-003 define o domínio de questões. Esta spec define aquisição local, integridade, deduplicação exata, armazenamento e contratos simples de localização/evidência. Preservar uma fonte não equivale a interpretar seu conteúdo. Aquisição simples MUST NOT gerar automaticamente evidências `CONTENT`, `ANSWER_KEY` ou `OFFICIAL_ASSOCIATION`.

As categorias de campos aplicáveis são:

| Categoria | Significado |
|-----------|-------------|
| Obrigatório | Campo presente com valor válido; referências devem existir |
| Nullable | Campo previsto, com `null` permitido quando ausente/desconhecido |
| Condicional | Obrigatório na condição descrita |
| Opcional | Pode ser omitido; se fornecido, não pode contradizer o contrato |

MUST NOT fabricar URL, provider, catálogo, data, título ou media type. MUST NOT usar string vazia indiscriminadamente. Datas seguem ISO 8601; instantes em UTC. Data documental sem horário MUST NOT receber horário inventado.

`SourceDefinition` é apenas a entrada de catálogo como DS-003, definida na SPEC-002. Não identifica arquivo nem exige tabela/serviço próprio. Pode ser configuração estática. Pertencimento conhecido ao catálogo é contexto da aquisição, não identidade do conteúdo.

Estão fora do escopo: HTTP download automático, scraping, browser automation, parsing de prova ou microdados, OCR, criação de Question/QuestionPlacement/AnswerKeyObservation, resolução de alternativas, classificação, analytics, mastery, recomendação, RAG, autenticação, extração em massa/recursiva, processamento paralelo, múltiplos writers, resolvers de todos os formatos, tabelas genéricas de fatos/evidências/supersessão, workflow engine, serviços de provenance, grafos, cloud e object storage remoto.

### Functional Requirements

#### Core Entity Contracts

- **FR-001**: A separação obrigatória MUST ser: `SourceResource` (identidade do conteúdo binário preservado), `ResourceAcquisition` (contexto/origem pela qual esse conteúdo foi observado) e `IngestionRun` (execução que realizou a operação). As camadas futuras que interpretarem a fonte associarão fatos às evidências apropriadas; aquisição MUST NOT gerar automaticamente essas referências semânticas.
- **FR-002**: SourceResource MUST representar conteúdo binário. Dois conteúdos binários diferentes correspondem a dois recursos; dois arquivos, nomes ou origens diferentes com bytes idênticos reutilizam o mesmo recurso. Campos obrigatórios: `id`, `sha256` (SHA-256 dos bytes efetivamente preservados), `byte_size` (inclusive zero quando o arquivo for vazio), `storage_locator` (endereço controlado, relativo ao data root ou reconstruível deterministicamente), `registered_at` (instante de registro no catálogo operacional). Campo nullable: `media_type` (tipo básico identificado com confiança). MUST NOT pertencer ao recurso: nome recebido, catálogo de origem, URL, provider, parent/member, data de publicação, título declarado pela fonte. SHA-256 significa identidade operacional do conteúdo binário para deduplicação exata; MUST NOT comprovar autenticidade institucional, validade pedagógica, correção factual, identidade de `Question` ou equivalência semântica. A identidade interna pode ser opaca ou derivada do hash; a escolha física MUST ser documentada sem alterar essa semântica. Deduplicação é por SHA-256, nunca por caminho, URL ou nome. Tamanho/hash divergentes no destino constituem falha, não autorização para sobrescrever. `registered_at` e metadados operacionais MUST NOT integrar a identidade binária. Reutilização MUST NOT redefinir a data do registro original. Media type é descrição técnica, não atributo de oficialidade.
- **FR-003**: ResourceAcquisition MUST representar contexto/origem observada. Cada aquisição aponta para exatamente um SourceResource e uma execução. Um recurso pode possuir zero ou mais aquisições; a ingestão bem-sucedida descrita nesta spec MUST registrar a aquisição correspondente. Falhas sem recurso são issues, não aquisições órfãs. Campos obrigatórios: `id`, `resource_id`, `ingestion_run_id`, `acquisition_method`, `observed_at`. Campos nullable: `source_definition_id`, `source_url`, `provider`, `received_filename`, `source_retrieved_at`. Campos condicionais: `parent_resource_id` (nullable; obrigatório para `CONTAINER_MEMBER`), `container_locator` (nullable; obrigatório para `CONTAINER_MEMBER` — nome exato do membro selecionado, não caminho de destino), `fixture_kind` (nullable; obrigatório quando a entrada for identificada como fixture). Métodos do primeiro incremento: `LOCAL_FILE`, `CONTAINER_MEMBER` e `FIXTURE`. Registrar URL conhecida como metadado de um arquivo local MUST NOT transformar o método em download. Para arquivo fornecido diretamente, parent/member ficam `null`; MUST NOT inferir contêiner anterior pelo nome. Uma nova origem nunca apaga aquisição anterior. Cada observação bem-sucedida registra aquisição, mesmo quando reutiliza conteúdo. MUST NOT registrar aquisições extras por etapa interna da mesma observação.
- **FR-004**: `observed_at` é o instante em que esta execução recebeu/observou o input; não é necessariamente o instante em que alguém baixou o arquivo da Internet. `source_retrieved_at` MAY registrar aquisição remota anterior somente se conhecida de maneira confiável; sua ausência MUST NOT ser preenchida com `observed_at`. Nenhuma dessas datas substitui uma data de publicação. Para ingestão local, o manifesto equivalente é composto pelos metadados de recurso e aquisições. `source_url`, `provider` e `source_definition_id` podem ser `null` quando desconhecidos. Esta é a especialização aprovada da obrigatoriedade genérica de origem na SPEC-002: documentar a ausência é válido; fabricar dados para preencher campos MUST NOT ser feito. SHA-256 do bruto materializado e rastreabilidade das informações conhecidas continuam obrigatórios. Um recurso sem origem oficial comprovada MUST NOT adquirir oficialidade por ter sido ingerido com sucesso.
- **FR-005**: `fixture_kind = SYNTHETIC` identifica fixture criada exclusivamente para testes. Usar `acquisition_method = FIXTURE` para sua entrada direta. MUST NOT inventar provider, URL ou catálogo oficiais. Para membro extraído de fixture ZIP, o método é `CONTAINER_MEMBER` e a natureza da fixture MUST continuar identificada na aquisição do membro. Fixture baseada em material real pode usar `fixture_kind = DERIVED_FROM_REAL` e MUST preservar a origem conhecida, eventuais transformações e limitações documentadas. O fixture MUST NOT passar a ser original oficial por derivar dele. Fora de fixtures, `fixture_kind = null`.

#### Input, Storage and ZIP

- **FR-006**: Input path localiza o arquivo fornecido, inclusive fora do projeto. É informação operacional, pode não ser persistida e nunca constitui identidade. Storage locator localiza o payload sob controle da aplicação, relativo ao data root ou reconstruível. MUST NOT usar caminho absoluto da máquina como identidade permanente. Uma direção simples para implementação é `raw/resources/<sha256>/payload` sob o data root configurado; esse layout especializa a organização exemplificada na SPEC-002, sem remover diretórios existentes e sem mudar a semântica raw/interim/processed. Nomes recebidos e nomes de membros MUST NOT controlar diretamente o caminho final. Entradas locais são somente leitura; MUST NOT modificar o arquivo fornecido. A cópia preservada MUST ser arquivo regular independente, não hard link ou symlink para a origem mutável. A operação MUST rejeitar entrada não regular ou links incompatíveis com a política de cópia segura e verificar que destinos controlados não escapem por links no filesystem. MUST NOT executar conteúdo ou comandos embutidos nos arquivos.
- **FR-007**: ZIP recebido → recurso raw do ZIP inteiro, com aquisição própria. Membro apenas listado → localizador dentro do ZIP, MUST NOT criar recurso nem aquisição de membro. Membro explicitamente materializado → cria ou reutiliza recurso raw dos bytes descomprimidos, com hash/tamanho próprios e aquisição `CONTAINER_MEMBER`. Conteúdo parseado, convertido, reserializado ou normalizado → derivado em interim quando houver parser futuro. Materialização de conteúdo não registrado cria recurso; conteúdo já preservado é reutilizado por deduplicação exata. A aquisição do membro preserva ZIP pai, nome exato e run responsável. SHA-256 do ZIP MUST NOT substituir SHA-256 dos bytes descomprimidos. Mesmo conteúdo como membro de ZIP A, membro de ZIP B e arquivo local direto resulta em um recurso do conteúdo e três aquisições. Os recursos dos ZIPs são contabilizados separadamente. `parent_resource_id` nunca é campo de SourceResource. MUST NOT criar automaticamente cópia interim do membro. ZIP dentro de ZIP pode ser preservado como bytes de um membro selecionado, mas MUST NOT ser aberto recursivamente; nova operação exigiria nova solicitação explícita. A invocação recebe no máximo um arquivo local e, se ZIP, no máximo um membro selecionado explicitamente. Listagem sem seleção também MUST funcionar.
- **FR-008**: Raw: bytes preservados, incluindo ZIP inteiro e membro selecionado descomprimido sem transformação; uma vez registrados, são imutáveis. Interim: interpretações técnicas ou transformações source-native; podem ser regeneradas a partir das fontes e lineage. Processed: resultados normalizados/mapeados ao domínio, definidos por specs posteriores. Descompressão fiel não é reserialização. MUST NOT colocar membro raw apenas em diretório descartável e anunciá-lo como materializado válido. Este incremento MUST NOT exigir gerar interim nem processed. Etapas posteriores nunca substituem o original. MUST NOT reconstruir raw a partir de interim/processed como se fosse o original; extrair novamente a partir do ZIP raw íntegro é operação diferente, sujeita às regras de reuso e preservação.

#### Locator and Evidence

- **FR-009**: SourceLocator MUST possuir: `resource_id`, `locator_type`, `locator_value`. Cada localizador possui exatamente um recurso de referência. Sem tabela obrigatória nem linguagem genérica de query. Tipos e convenções:

  | Tipo | Valor e convenção |
  |------|-------------------|
  | `DOCUMENT` | `{}`: recurso inteiro; não significa que localização mais precisa foi determinada |
  | `PDF_PAGE` | `{page_index: n}`: índice físico zero-based, inteiro não negativo; página impressa é metadado separado |
  | `CSV_ROW` | `{record_index: n, parser_config: ...}`: registro lógico zero-based após tratamento explícito do cabeçalho; configuração recuperável identifica encoding, delimitador, regras de aspas/escape, cabeçalho e tratamento de linhas vazias relevantes; não é linha física |
  | `ZIP_MEMBER` | `{member_name: "nome exato"}`; nomes duplicados tornam seleção/materialização ambígua e são rejeitados |
  | `SHEET_RANGE` | `{sheet_name, row_start, row_end, column_start, column_end}`: coordenadas zero-based, início inclusivo e fim exclusivo, intervalos não vazios |
  | `JSON_POINTER` | `{pointer: "..."}`: semântica RFC 6901; string vazia aponta para documento inteiro; MUST NOT interpretar como JSONPath |

  `parser_config` MUST estar embutida ou referenciar configuração imutável recuperável do run; MUST NOT exigir cadastro de perfis. A semântica lógica de CSV só pode ser resolvida com essa configuração. MUST NOT inventar regras de leitura desconhecidas para produzir localizador aparentemente preciso. O primeiro incremento valida/serializa os contratos e opera sobre `DOCUMENT` e `ZIP_MEMBER`; MUST NOT exigir resolver PDF, CSV, planilha ou JSON. Round-trip não equivale a validar existência da página/célula/registro no arquivo. `TABLE_ROW`, `TEXT_RANGE` e `OTHER` não são localizadores executáveis do núcleo inicial; extensões futuras exigem semântica e necessidade concretas.

- **FR-010**: EvidenceReference MUST possuir: `locator` (SourceLocator), `evidence_role`, `notes` (nullable). O recurso é identificado somente por `locator.resource_id`; MUST NOT duplicar `resource_id` na raiz da referência. Papéis conceituais incluem `CONTENT`, `PLACEMENT`, `ANSWER_KEY`, `EXTERNAL_IDENTIFIER`, `OFFICIAL_ASSOCIATION` e `PUBLICATION_METADATA`. A referência fica anexada à observação/fato que a camada interpretadora produzir. MUST NOT criar esquema genérico de `entity_type`, `entity_id`, `field_name` ou `fact_id`. Um fato pode ter várias evidências e um recurso pode apoiar vários fatos; o proprietário da referência define qual fato está sendo apoiado. Preservar recurso de origem oficial MUST NOT implicar que toda interpretação seja oficial. Em particular, MUST NOT implicar `QuestionSkill.relationship_type = OFFICIAL`. O papel `OFFICIAL_ASSOCIATION` não é prova por si só: a evidência MUST sustentar especificamente a associação, conforme SPEC-003. Aquisição registra bytes e origem; MUST NOT gerar automaticamente essas referências semânticas. O contrato suporta referências futuras sem criar tais entidades agora. Quando só o recurso for conhecido, usar referência documental sem fingir precisão de página/linha. Divergências MUST ser preservadas pelas camadas que as identificarem. MUST NOT implementar descoberta ou resolução de conflito semântico na ingestão. Evidências fornecidas explicitamente como contexto MUST NOT ser perdidas ou conciliadas silenciosamente.

#### Run Lifecycle

- **FR-011**: Toda invocação cria exatamente um IngestionRun, inclusive reingestão ou tentativa com input inexistente. A identidade da execução MUST ser criada antes de validar o input; etapas internas MUST NOT criar runs adicionais. Campos obrigatórios: `id`, `pipeline_name`, `pipeline_version`, `started_at`, `status`, `parameters` (inclui opções e limites efetivos; pode ser objeto vazio). Campos condicionais: `finished_at` (nullable enquanto `RUNNING`; obrigatório ao finalizar normalmente), `code_revision` (nullable quando indisponível; não dispensa versão do pipeline), inputs/outputs e resultados por unidade (obrigatórios quando necessários ao lineage; representação simples). Para entrada local, a unidade principal é preservar/registrar aquisição. Em operação ZIP, listagem e materialização solicitadas têm resultados identificáveis no mesmo run. Unidades não solicitadas MUST NOT contar como falha: listar sem materializar não é execução parcial. Reutilizar payload íntegro satisfaz a unidade, mesmo sem criar novo conteúdo. Se o armazenamento estiver indisponível a ponto de impedir registrar o próprio run, abortar com `FATAL` e relatório de diagnóstico com a identidade alocada; MUST NOT declarar que persistência ocorreu nem publicar payload novo nessa condição. MUST NOT criar segundo banco/log autoritativo para contornar a falha.
- **FR-012**: Statuses: `RUNNING` (execução iniciada, não finalizada), `SUCCESS` (todas as operações solicitadas concluídas), `PARTIAL` (pelo menos uma unidade solicitada concluída e pelo menos uma falhou, sem falha estrutural), `FAILED` (nenhuma saída solicitada confiável, ou falha que inviabilize a execução). `PARTIAL` não depende de registros CSV; pode futuramente abranger lotes ou parsing sem ampliar este incremento. Falha estrutural prevalece na classificação final; conteúdos já registrados com integridade MUST NOT ser apagados por causa dela. Severidades: `INFO` (informação operacional), `WARNING` (problema não bloqueante), `ERROR` (falha de unidade processável; pode ser possível continuar), `FATAL` (falha que compromete a execução inteira). MUST NOT existir "FATAL para aquele recurso". Hash divergente de payload específico gera `ERROR` e impede seu reuso. Problema estrutural do armazenamento/execução pode justificar `FATAL`. O status decorre dos resultados solicitados, não apenas da existência de warning ou recurso raw previamente preservado.
- **FR-013**: IngestionIssue MUST possuir campos obrigatórios: `id`, `run_id`, `stage`, `severity`, `message`. Campos nullable: `resource_id`, `input_reference`, `locator`, `exception_type`. Falha de leitura, caminho ou validação inicial MUST admitir `resource_id = null`, identificando a entrada em `input_reference` quando possível. Se locator estiver presente e também houver `resource_id`, ambos MUST concordar. Issues MAY ser estruturas dentro do run; tabela separada é opcional. Toda execução MUST emitir relatório serializável com: `run_id`, status e resultados das unidades solicitadas; `resources_seen`, `resources_created`, `resources_reused`, `resources_failed`; warnings/errors e issues com stage e causa; referências aos recursos e hashes conhecidos, aquisições e lineage; limitações/metadados ausentes quando relevantes. Os contadores representam tentativas de preservação de arquivo/membro, não quantidade de entradas apenas listadas. Ao encerrar, `resources_seen = resources_created + resources_reused + resources_failed`; tentativa iniciada mas não concluída por interrupção MUST ser reportada como falha ao reconciliar o run. Falhas de listagem não são recursos novos: aparecem nas unidades/issues. Sem parsing neste incremento, `records_read`, `records_accepted` e `records_rejected`, se expostos, são `null` (não aplicável), não zero para simular parser executado. Relatório final MUST refletir SQLite. Se houver falha de persistência, informar explicitamente. Retorno de execução parcial/falha MUST NOT parecer sucesso completo.

#### Integrity and Publication

- **FR-014**: Todo output produzido MUST permitir recuperar input(s), pipeline, versão e parâmetros relevantes. Referências MAY ficar no run/acquisition, sem lineage graph. Para cópia de arquivo local, aquisição registra contexto recebido; hash/tamanho representam o snapshot preservado; o caminho externo não é dependência necessária após ingestão. Para membro, o input é o ZIP raw identificado mais o nome exato selecionado; o output é o recurso dos bytes descomprimidos. MUST registrar limites/opções efetivos e versão da extração. MUST NOT classificar referências necessárias a essa relação como meramente recomendadas. Determinismo significa: mesmos inputs, versão e parâmetros produzem o mesmo output lógico. IDs de run, timestamps e metadados operacionais MUST NOT fazer parte do output determinístico. Para cópia/materialização raw, mesmos bytes preservados → mesmo SHA-256 e tamanho. Reingestão íntegra mantém um recurso e acrescenta run e aquisição da nova observação. MUST NOT confundir idempotência de conteúdo com ausência de histórico operacional. Deduplicação é somente exact content deduplication, sem fuzzy matching, similaridade textual, fingerprint normalizado ou fusão de Question.
- **FR-015**: SQLite é a autoridade dos metadados; bytes raw ficam no filesystem. Um recurso só é considerado registrado e válido quando payload completo e metadados correspondentes estiverem publicados e íntegros. Fluxo obrigatório para novo conteúdo: (1) Criar run e validar parâmetros/acesso ao armazenamento sob limitação single writer. (2) Abrir input regular em leitura; copiar em streaming para arquivo temporário controlado, no mesmo filesystem do destino final. (3) Calcular SHA-256 e contar bytes durante a própria cópia, aplicando limites efetivos; MUST NOT fazer hash de uma leitura e copiar em outra leitura posterior. (4) Flush/close, conferir tamanho e validar o hash do temporário antes da publicação; a conferência pode reler o temporário controlado; MUST NOT reler a origem como prova dos bytes copiados. (5) Consultar identidade/destino; se existir, aplicar FR-016; caso contrário, publicar temporário completo no destino final sem sobrescrita. (6) Registrar recurso, aquisição e vínculos/resultados necessários em transação SQLite; só após commit a unidade é anunciada como concluída. (7) Finalizar status/relatório do run. A operação MUST usar destino controlado e impedir substituição de payload existente. Se a origem mudar durante a leitura, o hash anunciado MUST sempre corresponder aos bytes efetivamente copiados/validados; MUST NOT prometer snapshot atômico do arquivo externo. A transação SQLite não torna filesystem e banco uma transação única; a janela entre publicação e commit é tratada pela recuperação (FR-017).
- **FR-016**: Destino correspondente ao hash já existente MUST NOT ser sobrescrito. No primeiro incremento, verificar tamanho e recalcular SHA-256 do payload existente antes de reutilizar; corrupção do mesmo tamanho também é detectada. MUST NOT confiar apenas no registro do banco. Se payload ou metadados mínimos divergem, falhar explicitamente, MUST NOT registrar aquisição bem-sucedida e MUST NOT "corrigir" automaticamente o hash esperado. Preservar diagnóstico e originais existentes. Recuperação de corrupção MUST NOT se confundir com reconciliação de payload íntegro ainda sem metadados. Registro com payload ausente ou parcial MUST NOT ser devolvido como íntegro. Linha em SQLite é necessária mas MUST NOT provar sozinha integridade física.

#### Recovery and Security

- **FR-017**: Estratégia do primeiro incremento: temporários nunca são recursos válidos; com exclusividade de escrita confirmada, nova execução pode limpar temporários abandonados, registrando a ação. Run abandonado em `RUNNING` MUST ser identificável; ao reconciliá-lo, registrar interrupção e finalizar como `FAILED`, com horário de recuperação e causa; MUST NOT inventar horário exato da interrupção. Preservar unidades já confirmadas e recursos íntegros. Payload final sem linha correspondente em SQLite é órfão não registrado; MUST NOT usá-lo silenciosamente como recurso válido nem fabricar aquisição histórica. Reconciliação mínima: reingestão explícita do mesmo conteúdo verifica tamanho/hash do órfão; se íntegro, pode registrar recurso e aquisição da execução atual em transação, indicando recuperação; MUST NOT inventar origem ou data do run anterior. Se divergente, falhar sem sobrescrever. Órfãos não reencontrados permanecem detectáveis pela comparação entre destinos controlados e registros SQLite, sem remoção automática de payload final. A implementação MUST impedir sobreposição de writers por mecanismo local simples de exclusividade/falha imediata e documentar essa limitação. MUST NOT criar filas, scheduler ou coordenação distribuída. MUST NOT limpar temporários pertencentes a execução ativa. Se unidade já estiver confirmada antes da interrupção do relatório, recuperação MUST NOT repetir nem desfazer aquela aquisição; registra o run interrompido.
- **FR-018**: Listar a partir do ZIP raw preservado, sem executar conteúdo e sem criar recursos para cada entrada. Seleção utiliza nome exato, nunca glob ou seleção automática. MUST rejeitar seleção/materialização quando: nome contém componente de traversal (`..`), caminho absoluto, raiz/unidade ou separadores que escapariam ao destino controlado; resolução atravessaria link ou escreveria fora do espaço controlado; entrada é symlink/link especial ou não é arquivo regular compatível; nome exato selecionado aparece mais de uma vez; limites, integridade do ZIP ou método de leitura necessário não puderem ser respeitados. Listagem MAY apresentar entradas inseguras ou duplicadas como não selecionáveis, com aviso explícito, sem escrevê-las. MUST NOT sanitizar nomes distintos para o mesmo destino nem escolher silenciosamente uma ocorrência duplicada. Materialização solicitada de entrada proibida gera `ERROR`. MUST NOT reproduzir a árvore de paths do ZIP no raw: o destino final deriva da identidade de conteúdo. Nomes perigosos MUST ser rejeitados conforme contrato. ZIP aninhado permanece bytes; MUST NOT realizar extração recursiva implícita. Conteúdo nunca é executado, importado como código ou aberto para executar macros. Limites obrigatórios, finitos e configuráveis:

  | Parâmetro | Alcance |
  |-----------|---------|
  | `max_input_bytes` | Bytes lidos do arquivo local/ZIP de entrada |
  | `max_zip_members` | Entradas admitidas na listagem/inspeção do ZIP |
  | `max_member_uncompressed_bytes` | Bytes efetivamente descomprimidos do membro selecionado |
  | `max_total_uncompressed_bytes` | Total descomprimido pela execução |

  Defaults finitos MUST ser centralizados, documentados e registrados entre parâmetros efetivos do run. Testes usam limites pequenos. MUST NOT desabilitar limites implicitamente. Verificar limites durante leitura/escrita quando aplicável, não apenas nos tamanhos anunciados pelo ZIP. Interromper ao exceder, limpar temporário de membro não publicado e registrar issue. O ZIP íntegro já preservado permanece. Hashing/cópia MUST operar em streaming; MUST NOT carregar payload inteiro na memória.

#### Manifest and Auxiliary

- **FR-019**: SQLite é a única fonte de verdade dos metadados operacionais. Payloads ficam no filesystem. Metadados persistidos constituem o manifesto auditável equivalente exigido pela SPEC-002. Um `manifest.json`, se produzido, é export/view serializável derivado de SQLite, identificável como snapshot. MUST NOT ser segunda autoridade nem atualizar o banco automaticamente. Reexportar a partir da autoridade evita duas lógicas de atualização divergentes. MUST NOT gravar sidecar JSON dentro de raw obrigatoriamente. Modelo físico esperado:

  | Tabela | Conteúdo |
  |--------|----------|
  | `source_resource` | Conteúdo, hash/tamanho, media type nullable, endereço e registro |
  | `resource_acquisition` | Origens, timestamps, nomes recebidos, catálogo/provider, parent/member e run |
  | `ingestion_run` | Execução, parâmetros, resultados, lineage e relatório/issues estruturados |
  | `ingestion_issue` | Opcional, somente se separar issues melhorar a clareza operacional |

  MUST exigir integridade das referências, unicidade operacional de SHA-256 e coerência de hash/tamanho/payload. O recurso tem zero ou mais aquisições; cada aquisição tem exatamente um recurso e um run. MUST NOT criar tabelas obrigatórias para EvidenceReference, SourceLocator, catálogo, fatos, supersessão genérica ou lineage graph. Runs/acquisitions e estruturas embutidas bastam. Nenhuma nova tecnologia é necessária: filesystem local, SQLite e Python da stack existente.

- **FR-020**: Nova versão com bytes diferentes cria ou referencia outro recurso e preserva o anterior. Uma mesma URL pode aparecer em aquisições de vários recursos; várias URLs podem aparecer em aquisições do mesmo recurso. Supersessão exige declaração/evidência explícita da fonte e contexto pertinente. `observed_at` ou `source_retrieved_at` mais recentes MUST NOT provar substituição. MUST NOT criar relação de supersessão consigo mesmo quando os bytes forem iguais. Adiar mecanismo genérico e resolução automática. Uma declaração explícita pode permanecer documentada junto ao contexto fornecido, sem exigir tabela ou parser. Nenhuma substituição de recurso propaga automaticamente anulação, gabarito ou estado de Question. Conflitos interpretados posteriormente preservam observações e evidências conforme SPEC-003. Aquisição MUST NOT decidir qual alternativa está correta nem detectar identidade semântica.
- **FR-021**: Media type básico é nullable. Extensão do nome recebido é somente evidência auxiliar; MUST NOT implementar detector universal. Conteúdo desconhecido pode ser preservado com sucesso como bytes sem interpretação de formato. Operação ZIP exige que seja possível tratar o conteúdo como ZIP válido, independentemente da extensão. Fixtures pequenas, contratos, testes e manifestos de teste MAY ser versionados. Payloads reais e SQLite operacional MUST NOT entrar no Git. Exports operacionais não são automaticamente material versionável; preservar a política de dados e MUST NOT incluir secrets, URLs com credenciais ou diagnóstico sensível em manifestos públicos. Fonte sem bytes pode existir futuramente como catálogo/pendência, não como recurso materializado válido com hash fabricado. No primeiro incremento, input inexistente gera run/issue e falha, sem cadastrar recurso de conteúdo imaginário.

### Domain Invariants

| ID | Invariante |
|----|------------|
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

### Requirement Acceptance Traceability

| Requirement | Acceptance evidence |
|-------------|---------------------|
| FR-001 | All user stories; separation verified across resource, acquisition and run |
| FR-002 | User Story 1 scenarios 1–3; SHA-256, deduplication, storage locator, identity semantics |
| FR-003 | User Story 1 scenarios 1–3 and User Story 2 scenarios 1–3; acquisition fields, methods, parent/member |
| FR-004–FR-005 | Edge cases K, P; timestamps, absence, fixtures |
| FR-006 | Edge cases C, Q, S; input paths, storage, safety |
| FR-007 | User Story 2 scenarios 1–3; edge cases X; ZIP cardinality, member materialization |
| FR-008 | User Story 2 scenario 1; raw/interim/processed separation |
| FR-009 | User Story 4 scenarios 1–2; locator types, round-trip, semantics |
| FR-010 | User Story 4 scenarios 1, 3; evidence roles, divergence preservation |
| FR-011–FR-013 | User Story 3 scenarios 1–3; edge cases J, O, R; run lifecycle, status, issues, report |
| FR-014 | Edge case W; lineage, determinism, idempotency |
| FR-015–FR-016 | User Story 3 scenarios 2–3; edge case G; publication protocol, reuse, integrity |
| FR-017 | User Story 3 scenario 2; edge case R; recovery, single writer |
| FR-018 | Edge cases F, S, T, U; ZIP security, limits |
| FR-019 | Edge case W; manifest, physical model, SQLite authority |
| FR-020 | Edge case L; retifications, supersession |
| FR-021 | Edge cases K, P; media type, Git, incomplete sources |
| INV-004-001–INV-004-023 | All acceptance scenarios; cross-cutting invariant verification |

### Key Entities *(include if feature involves data)*

- **SourceResource**: Conteúdo binário preservado, identificado operacionalmente por SHA-256 dos bytes efetivamente armazenados. Não contém contexto de origem.
- **ResourceAcquisition**: Contexto e origem observada de um conteúdo: método, timestamps, provider, URL, catálogo, nome recebido, parent/member para contêineres, fixture kind. Cada aquisição aponta para exatamente um recurso e um run.
- **IngestionRun**: Execução que realizou operações de aquisição. Uma invocação cria exatamente um run. Registra pipeline, versão, parâmetros, status, unidades solicitadas e resultados.
- **IngestionIssue**: Problema registrado durante execução, com stage, severity e referências disponíveis. Pode existir antes do recurso (resource_id nullable).
- **SourceLocator**: Contrato de localização serializável com exatamente um recurso de referência. Seis tipos no primeiro incremento: DOCUMENT, PDF_PAGE, CSV_ROW, ZIP_MEMBER, SHEET_RANGE, JSON_POINTER.
- **EvidenceReference**: Contrato para camadas futuras vinculando localizador, papel (CONTENT, PLACEMENT, ANSWER_KEY, EXTERNAL_IDENTIFIER, OFFICIAL_ASSOCIATION, PUBLICATION_METADATA) e notas ao fato que a camada interpretadora produzir. Não criada automaticamente pela aquisição.
- **SourceDefinition**: Entrada de catálogo (e.g., DS-003) definida pela SPEC-002; não identifica arquivo nem exige tabela própria.

## Success Criteria *(mandatory)*

### Measurable Outcomes

Os critérios abaixo validam o contrato do primeiro incremento; não validam parsers, domínio de questões ou features pedagógicas.

- **SC-001**: Arquivo local ingerido produz recurso, aquisição e payload preservado com SHA-256/tamanho correspondentes aos bytes efetivamente preservados. *(Cases A, P)*
- **SC-002**: Mesmos bytes de N origens/execuções diferentes produzem um recurso e N aquisições, preservando todas as origens e todo o histórico operacional. *(Cases B, D)*
- **SC-003**: ZIP preservado com aquisição própria; membro materializado possui hash/tamanho próprios dos bytes descomprimidos e aquisição CONTAINER_MEMBER com parent e nome exato. *(Cases E, M, N)*
- **SC-004**: Traversal, caminhos absolutos, links, nomes duplicados e entradas inseguras são rejeitados sem payload parcial ou recursos fabricados; conteúdo nunca é executado. *(Cases F, S, T)*
- **SC-005**: Limites finitos de input, membros e descompressão são configuráveis, registrados e verificados durante leitura; excesso interrompe sem publicar parcial. *(Case U)*
- **SC-006**: Status do run reflete unidades solicitadas: SUCCESS quando todas concluídas, PARTIAL quando pelo menos uma concluída e pelo menos uma falhou sem falha estrutural, FAILED quando nenhuma saída solicitada confiável ou quando falha estrutural inviabiliza a execução como um todo, mesmo que unidades anteriores tenham sido concluídas individualmente. *(Case J)*
- **SC-007**: Issues registram stage, severity e referências disponíveis; issues anteriores ao recurso preservam `resource_id = null`. *(Cases J, O)*
- **SC-008**: Payload corrompido é detectado por hash/tamanho divergentes e falha explicitamente sem reutilização silenciosa, sobrescrita ou correção automática de metadados. *(Case G)*
- **SC-009**: Publicação segue protocolo: cópia com hashing simultâneo, validação de temporário e destino controlado. Se SQLite não puder registrar o run inicial, a execução aborta antes de publicar qualquer payload novo. Se SQLite falhar após publicação no filesystem mas antes do commit de metadados, o payload pode permanecer como órfão não registrado; o órfão não é recurso válido e a recuperação segue FR-017 (Case R). Uma unidade só é anunciada como concluída após o commit da transação de metadados correspondente. *(Cases A, O, Q, R)*
- **SC-010**: Recuperação identifica runs abandonados e temporários; reconciliação verifica integridade sem inventar origem, data ou aquisição anterior. *(Case R)*
- **SC-011**: Single writer garante exclusividade; nenhuma extração recursiva, seleção automática ou processamento paralelo é acionado. *(Cases W, X)*
- **SC-012**: Localizadores dos seis tipos documentados serializam e desserializam sem perda, com semântica de coordenadas explícita. *(Case V)*
- **SC-013**: EvidenceReference preserva recurso via localizador, papel e notas sem duplicar resource_id; aquisição não gera referências semânticas automaticamente. *(Cases H, I)*
- **SC-014**: Fixtures são identificadas; origem oficial não é fabricada; fixtures derivadas preservam origem conhecida e limitações. *(Case K)*
- **SC-015**: SQLite é autoridade dos metadados; manifesto JSON é export/view derivado, não segunda autoridade. *(Case W)*
- **SC-016**: Todo output possui inputs, pipeline/versão e parâmetros relevantes recuperáveis; lineage pode ser recuperado sem lineage graph obrigatório. *(Case W)*
- **SC-017**: Nova versão com bytes diferentes preserva anterior; supersessão exige evidência explícita; nenhuma alteração propaga automaticamente ao domínio de questões. *(Case L)*

### Migration Acceptance

- **MA-001**: Uma auditoria de escopo encontra zero requisitos novos não presentes no documento legado `specs/004-source-resource-and-local-ingestion.md`.
- **MA-002**: Todos os 23 invariantes do legado (INV-004-001 a INV-004-023) estão preservados integralmente.
- **MA-003**: Todos os 24 casos conceituais de aceite do legado (Cases A–X) estão mapeados a user story scenarios ou edge cases.

## Assumptions

- Esta especificação define o contrato de aquisição e ingestão mínima; o README continua sendo a referência para o estado efetivamente implementado.
- O primeiro corpus normalizado prioriza ENEM 2017–2025, aplicação regular, representação impressa padrão; esta é uma prioridade de implementação, não uma limitação permanente do domínio nem exigência de adquirir esse corpus nesta implementação.
- Defaults finitos, detalhes de CLI, IDs e armazenamento de issues são escolhas de implementação a documentar dentro deste contrato, não novas decisões de produto.
- UUID versus hash de ID, colunas físicas e convenções de saída do comando podem ser definidos na implementação sem mudar a semântica especificada.
- Listas de métodos de aquisição (`LOCAL_FILE`, `CONTAINER_MEMBER`, `FIXTURE`) são extensíveis; não constituem enum físico fechado.
- A stack vigente (ADR-0001) permanece inalterada: filesystem local, SQLite e Python.
- Não há decisão bloqueante remanescente para iniciar a implementação.

## Dependencies

- `specs/004-source-resource-and-local-ingestion.md`: fonte histórica integral desta reconstrução retrospectiva e mantida sem alteração.
- `.specify/memory/constitution.md`: princípios I (Specification Is the Source of Truth), III (Simple, Local-First Architecture), IV (Deterministic and Tested Domain Rules) e V (Data Integrity, Provenance, and Security) governam diretamente este contrato.
- `specs/001-product-foundation/spec.md`: FR-005 e FR-028 da SPEC-001 dependem de proveniência e reprodutibilidade garantidas por este contrato.
- `specs/002-data-sources/spec.md`: FR-007–FR-010 (integridade/armazenamento), FR-011–FR-012 (lineage/reprodutibilidade) fornecem as regras de dados que este contrato implementa. FR-004 (§6) registra a especialização aprovada de metadados desconhecidos em aquisição local.
- `specs/003-question-data-model/spec.md`: FR-006 (revisões), FR-011 (gabarito), FR-025 (proveniência) do modelo de domínio referenciam SourceResource e EvidenceReference definidos aqui. Este contrato não cria entidades do modelo de domínio.
- `docs/adr/0001-initial-architecture.md`: define a stack (SQLite, Python, filesystem local) e decisões arquiteturais vigentes.
