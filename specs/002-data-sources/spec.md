# Feature Specification: Data Sources and Provenance

**Feature Branch**: `N/A (retrospective migration; no branch created)`

**Created**: 2026-09-18

**Status**: Draft

**Input**: User description: "Migrar retrospectivamente `specs/002-data-sources.md` para o formato nativo do GitHub Spec Kit, preservando integralmente seu significado, sem implementar código, sem alterar as demais specs e sem apagar o legado."

## Migration Provenance

Este artefato foi reconstruído retrospectivamente durante a migração para o GitHub Spec Kit. Ele expressa no formato atual a política de fontes de dados e proveniência originalmente registrada em `specs/002-data-sources.md`; não representa uma nova feature, não declara requisitos como já implementados e não autoriza implementação neste incremento. Esta especificação é uma política de governança de dados foundational: define regras que outras especificações e implementações devem seguir. O documento legado permanece preservado como fonte histórica da migração.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ingerir dados externos com proveniência preservada (Priority: P1)

Como contribuidor do projeto, quero que toda ingestão de dados externos preserve proveniência, hash de integridade, imutabilidade do original e manifesto de origem para que a integridade dos dados seja verificável e qualquer resultado possa ser rastreado à sua fonte.

**Why this priority**: Sem proveniência e integridade garantidas, nenhum resultado derivado é auditável e nenhuma recomendação é confiável.

**Independent Test**: Pode ser testada ingerindo um recurso de exemplo e verificando que o original permanece imutável em `data/raw/`, possui SHA-256 e `observed_at`, que metadados de origem conhecidos estão registrados sem fabricação e que nenhum dado original foi alterado pelo pipeline.

**Acceptance Scenarios**:

1. **Given** um arquivo externo a ser ingerido, **When** o pipeline o processa, **Then** o original é armazenado em `data/raw/` e permanece imutável; o manifesto registra `sha256` e `observed_at` incondicionalmente, e `source_id`, `provider`, `source_url` e `source_retrieved_at` quando conhecidos e aplicáveis.
2. **Given** um arquivo já ingerido, **When** uma correção de ingestão é necessária, **Then** a correção gera novo arquivo, nova versão ou nova transformação, sem alterar o original.
3. **Given** um arquivo bruto ingerido, **When** seu hash é verificado, **Then** o SHA-256 calculado no momento da ingestão coincide com o hash registrado no manifesto.

---

### User Story 2 - Distinguir categorias de dados por origem (Priority: P1)

Como produto, preciso distinguir fatos oficiais (Tier A), dados derivados pelo projeto (Tier B), fontes educacionais secundárias (Tier C) e inferências de IA (Tier D) para que recomendações ao usuário mantenham rastreabilidade e confiabilidade e nenhuma categoria sobrescreva silenciosamente outra de maior precedência.

**Why this priority**: A confiabilidade do produto depende de que o usuário e o sistema consigam identificar a origem e a categoria de cada informação utilizada.

**Independent Test**: Pode ser testada consultando dados de diferentes origens e verificando que cada um possui identificação de tier, que fontes oficiais prevalecem sobre secundárias e inferências, e que inferências de IA estão explicitamente marcadas.

**Acceptance Scenarios**:

1. **Given** uma informação disponível em fonte oficial (Tier A) e em fonte secundária (Tier C), **When** ambas são consultadas, **Then** a precedência é Inep > MEC/SiSU > UFMG > análise do projeto > fontes secundárias > inferências de LLM.
2. **Given** uma classificação produzida por LLM, **When** ela é registrada, **Then** possui indicador explícito de que foi gerada automaticamente e não sobrescreve silenciosamente informação oficial.
3. **Given** um dado derivado pelo projeto (Tier B), **When** ele é registrado, **Then** possui versão do pipeline, inputs, data de geração, algoritmo e parâmetros relevantes.

---

### User Story 3 - Rastrear transformações e garantir reprodutibilidade (Priority: P2)

Como operador de pipeline, quero que cada transformação registre lineage completo, versão e relatório de qualidade para que qualquer resultado derivado possa ser auditado, reproduzido e verificado.

**Why this priority**: Sem lineage e reprodutibilidade, falhas de transformação são invisíveis e métricas derivadas não são verificáveis.

**Independent Test**: Pode ser testada executando um pipeline de transformação de exemplo e verificando que cada estágio registra input, output, versão, timestamp e código responsável, e que o relatório de qualidade indica registros lidos, válidos, rejeitados, duplicatas, campos ausentes, inconsistências e checksums.

**Acceptance Scenarios**:

1. **Given** uma transformação de dados de raw para processed, **When** o pipeline é executado, **Then** cada estágio registra input, output, versão, timestamp e código responsável.
2. **Given** um pipeline determinístico com inputs e versão idênticos, **When** é reexecutado, **Then** o output é idêntico.
3. **Given** um output que depende de LLM, **When** é registrado, **Then** possui provider, model, prompt version, input hash, timestamp e configuração relevante.
4. **Given** um pipeline concluído, **When** o relatório de qualidade é consultado, **Then** indica quantidade de registros lidos, válidos, rejeitados, duplicatas, campos ausentes, inconsistências e checksums.

---

### User Story 4 - Tratar dados temporais sem permanência artificial (Priority: P2)

Como produto, preciso que dados de ingresso, notas históricas e demais informações temporais permaneçam vinculados à sua edição, fonte e data para que nenhuma informação temporal seja tratada como fato permanente.

**Why this priority**: Notas de corte, regras de ingresso e cronogramas mudam entre edições; tratá-los como permanentes compromete a confiabilidade das recomendações de estudo.

**Independent Test**: Pode ser testada registrando duas observações de ingresso de edições distintas e verificando que cada uma preserva sua dimensão temporal completa e que nenhuma é tratada como valor permanente.

**Acceptance Scenarios**:

1. **Given** uma observação de dados de ingresso, **When** ela é registrada, **Then** está vinculada a instituição, curso, edição, modalidade, chamada, data e fonte.
2. **Given** uma nova nota de corte de uma edição posterior, **When** ela é registrada, **Then** não sobrescreve a observação anterior nem se torna um fato atemporal.

### Edge Cases

- Quando existir conflito entre uma fonte Tier A e uma Tier C para a mesma informação, a fonte Tier A prevalece; a Tier C permanece registrada mas identificada como secundária.
- Os campos incondicionais do manifesto (`sha256`, `observed_at`) MUST estar presentes em toda aquisição. Campos de origem institucional (`source_id`, `provider`, `source_url`, `source_retrieved_at`) MUST ser registrados quando conhecidos e aplicáveis, mas MUST NOT ser fabricados quando desconhecidos ou inaplicáveis.
- Classificação automática sem metadados de execução (provider, model, prompt version) não pode ser registrada como classificação versionada.
- `null`, `unknown` (categoria explicitamente não determinada) e string vazia não são intercambiáveis; cada um possui semântica distinta.
- Quando um documento possui apenas data (sem horário), não se deve inventar horário; registrar somente a data em ISO 8601.
- Falhas de pipeline não podem ser ignoradas silenciosamente; o relatório de qualidade MUST registrar rejeições e inconsistências.
- Coeficientes de recência são hipótese de modelagem e MUST ser configuráveis, não fatos educacionais fixos.

## Requirements *(mandatory)*

### Scope Boundaries

Esta especificação define a política de governança de dados do projeto: fontes autorizadas, precedência, proveniência, integridade, imutabilidade, lineage, reprodutibilidade, qualidade, temporalidade, segurança e convenções de dados. Ela estabelece regras que outras especificações e implementações devem seguir. A presente migração produz somente documentação: não implementa pipelines, storage, manifestos ou qualquer capacidade descrita.

O projeto MUST NOT misturar fatos oficiais, estatísticas calculadas, informação secundária e inferência de IA sem identificação explícita.

A definição do modelo de domínio de questões pertence à SPEC-003. O contrato de aquisição e ingestão local de recursos pertence à SPEC-004. Esta especificação não redefine entidades desses escopos; estabelece as regras de dados que eles devem cumprir.

### Functional Requirements

#### Source Classification and Precedence

- **FR-001**: Informações institucionais MUST respeitar a hierarquia de precedência: Inep > MEC/SiSU > UFMG > análises do projeto a partir de dados oficiais > fontes educacionais secundárias > inferências de LLM.
- **FR-002**: Fontes Tier A (institucionais primárias) incluem Inep (Matriz de Referência, provas, gabaritos, microdados, informações sobre itens, documentação metodológica, documentação TRI, cartilha do participante, materiais de redação, cronograma oficial), MEC/SiSU (regras do processo seletivo, legislação, modalidades, cronogramas, procedimentos) e UFMG (Termo de Adesão ao SiSU, vagas, modalidades, pesos, notas máximas/mínimas, chamadas, editais, procedimentos institucionais).
- **FR-003**: Dados derivados (Tier B), calculados pelo projeto a partir de fontes Tier A, MUST registrar versão do pipeline, inputs, data de geração, algoritmo e parâmetros relevantes. Exemplos incluem incidência de temas, distribuição de questões, taxa histórica por competência, frequência por subtema, tendência temporal, métricas de dificuldade derivadas, desempenho do usuário, priority score e mastery score.
- **FR-004**: Fontes educacionais secundárias (Tier C), incluindo livros, artigos, professores, universidades, materiais didáticos e cursinhos, MUST ser utilizadas principalmente para explicações e complementação conceitual e MUST NOT substituir fontes oficiais quando estas existirem.
- **FR-005**: Conteúdo gerado por IA (Tier D), incluindo classificação candidata, explicação, resumo, feedback, hipótese e diagnóstico candidato, MUST possuir indicador explícito de geração automática e MUST NOT sobrescrever silenciosamente informação oficial.

#### Source Catalog

- **FR-006**: O catálogo inicial de fontes obrigatórias MUST incluir DS-001 (Matriz de Referência ENEM), DS-002 (Microdados ENEM), DS-003 (Provas e gabaritos oficiais), DS-004 (Documentação TRI) e DS-005 (UFMG/SiSU), todos Tier A, conforme a tabela abaixo.

| ID | Fornecedor | Tipo | Uso principal | Tier |
|--------|------------|------|---------------|------|
| DS-001 | Inep | Documento institucional (Matriz de Referência ENEM) | Competências, habilidades, objetos de conhecimento, estrutura conceitual do ENEM | A |
| DS-002 | Inep | Microdados (edições disponíveis até 2025) | Provas, gabaritos, informações de itens, notas, análise histórica | A |
| DS-003 | Inep | Provas e gabaritos oficiais | Conteúdo das questões, alternativas, resposta correta, metadados da prova | A |
| DS-004 | Inep | Documentação TRI | Compreensão metodológica, restrições do sistema, documentação de métricas derivadas | A |
| DS-005 | UFMG | Dados institucionais (SiSU) | Curso, modalidade, vagas, pesos, notas históricas, chamadas, regras de ingresso | A |

#### Data Integrity and Storage

- **FR-007**: Arquivos originais MUST ser armazenados em `data/raw/` e MUST ser tratados como imutáveis. Correções de ingestão MUST gerar novo arquivo, nova versão ou nova transformação e MUST NOT alterar o original.
- **FR-008**: A estrutura de armazenamento MUST manter a separação `data/raw/`, `data/interim/` e `data/processed/`. A organização física interna de `data/raw/` MAY seguir layout por fornecedor e tipo, layout por endereçamento de conteúdo ou outro esquema documentado. O layout ilustrativo original por fornecedor é:

```text
data/
├── raw/
│   ├── inep/
│   │   ├── matrix/
│   │   ├── microdata/
│   │   ├── exams/
│   │   └── methodology/
│   └── ufmg/
│       └── sisu/
├── interim/
└── processed/
```

  Independentemente do layout físico adotado, informações de fornecedor e catálogo MUST permanecer recuperáveis por meio dos metadados de aquisição.

- **FR-009**: Cada recurso ingerido MUST possuir `sha256` dos bytes preservados. Cada aquisição bem-sucedida MUST registrar `observed_at` (instante em que a execução recebeu o input). Campos de origem institucional (`source_id`, `provider`, `source_url`) MUST ser registrados quando conhecidos e aplicáveis, mas MUST NOT ser fabricados quando desconhecidos ou inaplicáveis. `source_retrieved_at` MAY registrar coleta remota anterior quando conhecida de forma confiável e MUST NOT ser preenchido com `observed_at`. O manifesto MAY incluir `title`, `published_at`, `original_filename`, `content_type` e `pipeline_version`.
- **FR-010**: Todo arquivo bruto MUST possuir SHA-256 calculado no momento da ingestão para detectar mudanças, confirmar integridade, impedir duplicação acidental e permitir rastreabilidade.

#### Lineage and Reproducibility

- **FR-011**: Transformações MUST preservar lineage; cada estágio MUST registrar input, output, versão, timestamp e código responsável.
- **FR-012**: Dado um conjunto idêntico de inputs e uma versão idêntica do pipeline determinístico, o output MUST ser idêntico. Outputs que dependam de LLM MUST registrar provider, model, prompt version, input hash, timestamp e configuração relevante.

#### Temporal Validity

- **FR-013**: Nenhum dado de ingresso MUST ser tratado como eternamente verdadeiro. Observações de dados de ingresso MUST estar vinculadas a instituição, curso, edição, modalidade, chamada, data e fonte. MUST NOT existir valor temporal relevante apresentado sem relação a edição, fonte e data.

#### Taxonomy and Classification

- **FR-014**: A taxonomia oficial (competências e habilidades do Inep) MUST ser separada da taxonomia analítica (temas e subtemas do projeto). Tema e habilidade não são sinônimos. Uma questão MAY envolver múltiplos tópicos e múltiplas habilidades; um conjunto temático completo MUST possuir um tópico principal e zero ou mais tópicos secundários. A cardinalidade detalhada e os conjuntos parciais são definidos pela SPEC-003 §18.
- **FR-015**: Classificação automática de questões MUST gerar resultado candidato versionado com confiança, método, modelo e versão; classificação automática MUST NOT ser registrada como verdade não versionada.
- **FR-016**: Rankings de frequência de temas utilizados pelo produto SHOULD ser calculados internamente, com janela temporal explícita, método de classificação, quantidade de itens e versão do dataset. O produto MUST NOT exibir frequência sem essas informações de contexto.
- **FR-017**: O motor MAY dar maior peso a edições recentes, mas esse comportamento MUST ser parametrizado. A política candidata inicial preserva os pesos `0,50 × janela recente + 0,30 × janela intermediária + 0,20 × janela antiga`; esses coeficientes são hipótese de modelagem, não fato educacional, e MUST ser configuráveis.

#### Data Quality

- **FR-018**: Cada pipeline MUST produzir relatório de qualidade com quantidade de registros lidos, válidos, rejeitados, duplicatas, campos ausentes, inconsistências e checksums. Falhas MUST NOT ser ignoradas silenciosamente.

#### Data Conventions

- **FR-019**: O projeto MUST distinguir `null` (informação desconhecida/não existente), categoria explicitamente não determinada (`unknown`) e valor concreto. String vazia MUST NOT ser utilizada indiscriminadamente como substituto de ausência.
- **FR-020**: Datas MUST ser armazenadas em formato ISO 8601. Quando horário for relevante, MUST ser armazenado em UTC. Quando o documento possuir apenas data, MUST NOT inventar horário.

#### Security

- **FR-021**: Credenciais, API keys, tokens, senhas e cookies de sessão MUST NOT ser armazenados em datasets, código versionado ou manifestos públicos. Variáveis de ambiente MUST ser utilizadas.

### Requirement Acceptance Traceability

| Requirement | Acceptance evidence |
|-------------|---------------------|
| FR-001–FR-005 | User Story 2 scenarios 1–3; tier identification and precedence verification |
| FR-006 | Source Catalog completeness review; all five DS entries present with Tier A |
| FR-007–FR-010 | User Story 1 scenarios 1–3; raw immutability, manifest, and hash verification |
| FR-011–FR-012 | User Story 3 scenarios 1–3; lineage, reproducibility, and LLM metadata verification |
| FR-013 | User Story 4 scenarios 1–2; temporal dimension and non-permanence verification |
| FR-014–FR-017 | User Story 2 scenarios 2–3; taxonomy separation, classification candidate, frequency context, and recency configurability checks |
| FR-018 | User Story 3 scenario 4; quality report completeness verification |
| FR-019–FR-020 | Null semantics and date format review across ingested data |
| FR-021 | Secret scan and environment variable verification |

### Key Entities *(include if feature involves data)*

- **SourceTier**: Classificação de precedência de fontes de dados: Tier A (institucional primária), Tier B (derivado pelo projeto), Tier C (educacional secundária), Tier D (gerado por IA).
- **DataSource (DS-nnn)**: Entrada no catálogo de fontes autorizadas com identificador, fornecedor, tipo e tier.
- **OriginManifest**: Registro de proveniência de um recurso ingerido. Campos incondicionais: `sha256` (identidade do conteúdo) e `observed_at` (instante da observação). Campos obrigatórios quando conhecidos: `source_id`, `provider`, `source_url`. Campo opcional: `source_retrieved_at` (coleta remota anterior, distinto de `observed_at`).
- **TransformationStage**: Etapa rastreável na cadeia de lineage, com input, output, versão, timestamp e código responsável.
- **QualityReport**: Relatório de qualidade produzido por pipeline, com registros lidos, válidos, rejeitados, duplicatas, campos ausentes, inconsistências e checksums.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A estrutura `data/raw/`, `data/interim/` e `data/processed/` existe e é respeitada por todos os pipelines.
- **SC-002**: 100% dos arquivos em `data/raw/` são tratados como imutáveis; nenhuma alteração direta é realizada por pipeline.
- **SC-003**: 100% dos recursos ingeridos possuem `sha256` e toda aquisição bem-sucedida registra `observed_at`; campos de origem institucional (`source_id`, `provider`, `source_url`) estão presentes quando conhecidos e aplicáveis, e nenhum campo de origem é fabricado quando desconhecido.
- **SC-004**: 100% dos arquivos brutos ingeridos possuem SHA-256 calculado e registrado no momento da ingestão.
- **SC-005**: 100% dos dados de SiSU utilizados no planejamento possuem dimensão temporal completa (edição, chamada, data, fonte).
- **SC-006**: 100% das transformações registradas possuem lineage com input, output, versão, timestamp e código responsável.
- **SC-007**: 100% das classificações de IA são identificáveis como geradas automaticamente, com metadados de execução.
- **SC-008**: 100% das métricas derivadas indicam versão e método de cálculo.
- **SC-009**: Em toda consulta de dados, fontes oficiais (Tier A) prevalecem sobre as demais categorias.
- **SC-010**: Nenhuma informação temporal relevante é apresentada como fato permanente sem vinculação a edição, fonte e data.

### Migration Acceptance

- **MA-001**: Uma auditoria de escopo encontra zero requisitos novos não presentes no documento legado `specs/002-data-sources.md`.

## Assumptions

- Esta especificação define política de governança de dados; o README continua sendo a referência para o estado efetivamente implementado.
- O catálogo de fontes (DS-001 a DS-005) reflete as fontes identificadas no documento legado; novas fontes serão adicionadas quando identificadas, sem exigir alteração estrutural nesta especificação.
- A estrutura de diretórios `data/raw/`, `data/interim/` e `data/processed/` é uma convenção organizacional; a implementação física pode evoluir via ADR sem alterar as regras de imutabilidade e separação.
- A cobertura de microdados refere-se inicialmente às edições disponíveis até 2025; edições futuras serão incorporadas quando publicadas pelo Inep.
- Coeficientes de recência e pesos de frequência são hipóteses de modelagem que exigem validação futura.
- A SPEC-003 detalha o modelo de domínio de questões; a SPEC-004 detalha o contrato de aquisição e ingestão. Esta especificação não redefine entidades desses escopos.

## Dependencies

- `specs/002-data-sources.md`: fonte histórica integral desta reconstrução retrospectiva e mantida sem alteração.
- `.specify/memory/constitution.md`: princípios V (Data Integrity, Provenance, and Security) e IV (Deterministic and Tested Domain Rules) governam diretamente esta política.
- `specs/001-product-foundation/spec.md`: FR-004, FR-005 e FR-006 da SPEC-001 referenciam diretamente as regras de fontes, proveniência e determinismo desta especificação.
- `specs/003-question-data-model.md`: utiliza as regras de taxonomia, classificação, proveniência e temporalidade definidas aqui.
- `specs/004-source-resource-and-local-ingestion.md`: implementa o contrato de aquisição e ingestão conforme as regras de imutabilidade, hash, manifesto e lineage definidas aqui.
