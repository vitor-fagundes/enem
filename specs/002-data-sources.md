# SPEC-002 — Data Sources and Provenance

## Status

Draft v1.

# 1. Objetivo

Definir:

* fontes autorizadas;
* prioridade entre fontes;
* política de ingestão;
* proveniência;
* armazenamento;
* validação;
* versionamento dos dados.

O projeto não deve misturar fatos oficiais, estatísticas calculadas, informação secundária e inferência de IA sem identificação explícita.

---

# 2. Classificação das fontes

## Tier A — Fontes institucionais primárias

Possuem maior prioridade.

### Inep

Utilizar para:

* Matriz de Referência do ENEM;
* provas;
* gabaritos;
* microdados;
* informações sobre itens;
* documentação metodológica;
* documentação da TRI;
* cartilha do participante;
* materiais de redação;
* cronograma oficial.

### MEC / SiSU

Utilizar para:

* regras do processo seletivo;
* legislação;
* modalidades;
* cronogramas;
* procedimentos.

### UFMG

Utilizar para:

* Termo de Adesão ao SiSU;
* vagas;
* modalidades;
* pesos;
* notas máximas/mínimas;
* chamadas;
* editais;
* procedimentos institucionais.

---

# 3. Tier B — Dados derivados

São resultados calculados pelo próprio projeto a partir das fontes Tier A.

Exemplos:

* incidência de temas;
* distribuição de questões;
* taxa histórica por competência;
* frequência por subtema;
* tendência temporal;
* métricas de dificuldade derivadas;
* desempenho do usuário;
* priority score;
* mastery score.

Dados derivados devem registrar:

* versão do pipeline;
* inputs;
* data de geração;
* algoritmo;
* parâmetros relevantes.

---

# 4. Tier C — Fontes educacionais secundárias

Podem incluir:

* livros;
* artigos;
* professores;
* universidades;
* materiais didáticos;
* cursinhos.

Devem ser utilizadas principalmente para explicações e complementação conceitual.

Não devem substituir uma fonte oficial quando esta existir.

---

# 5. Tier D — Conteúdo gerado por IA

LLM pode produzir:

* classificação candidata;
* explicação;
* resumo;
* feedback;
* hipótese;
* diagnóstico candidato.

Saída de LLM deve possuir indicador explícito de que foi gerada automaticamente.

Não pode sobrescrever silenciosamente informação oficial.

---

# 6. Fontes iniciais obrigatórias

## DS-001 — Matriz de Referência ENEM 2026

Fornecedor:
Inep.

Tipo:
documento institucional.

Uso:

* competências;
* habilidades;
* objetos de conhecimento;
* estrutura conceitual do ENEM.

Prioridade:
Tier A.

---

## DS-002 — Microdados ENEM

Fornecedor:
Inep.

Cobertura inicial:
edições disponíveis até 2025.

Uso:

* provas;
* gabaritos;
* informações de itens;
* notas;
* análise histórica.

Prioridade:
Tier A.

---

## DS-003 — Provas e gabaritos oficiais

Fornecedor:
Inep.

Uso:

* conteúdo das questões;
* alternativas;
* resposta correta;
* metadados da prova.

Prioridade:
Tier A.

---

## DS-004 — Documentação TRI

Fornecedor:
Inep.

Uso:

* compreensão metodológica;
* restrições do sistema;
* documentação de métricas derivadas.

Prioridade:
Tier A.

---

## DS-005 — UFMG / SiSU

Fornecedor:
UFMG.

Uso:

* curso;
* modalidade;
* vagas;
* pesos;
* notas históricas;
* chamadas;
* regras de ingresso.

Prioridade:
Tier A.

---

# 7. Imutabilidade

Arquivos originais devem ser armazenados em:

data/raw/

Arquivos em `raw` não podem ser alterados por pipeline.

Correção de ingestão deve gerar:

* novo arquivo;
* nova versão;
* ou nova transformação.

Nunca alterar silenciosamente o original.

---

# 8. Estrutura de armazenamento

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

---

# 9. Manifesto de origem

Cada recurso ingerido deve possuir um registro equivalente a:

```json
{
  "source_id": "DS-001",
  "provider": "INEP",
  "title": "Matriz de Referência ENEM",
  "source_url": "...",
  "retrieved_at": "...",
  "published_at": "...",
  "sha256": "...",
  "original_filename": "...",
  "content_type": "application/pdf",
  "pipeline_version": null
}
```

Campos obrigatórios:

* source_id;
* provider;
* source_url;
* retrieved_at;
* sha256.

---

# 10. Hash

Todo arquivo bruto deve possuir SHA-256 calculado no momento da ingestão.

Objetivos:

* detectar mudanças;
* confirmar integridade;
* impedir duplicação acidental;
* permitir rastreabilidade.

---

# 11. Data lineage

Transformações devem preservar lineage.

Exemplo:

```text
microdados_enem_2025.zip
        ↓
extract-v1
        ↓
items_2025.parquet
        ↓
normalize-items-v2
        ↓
questions.parquet
        ↓
classify-topic-v3
        ↓
questions_classified.parquet
```

Cada estágio deve informar:

* input;
* output;
* versão;
* timestamp;
* código responsável.

---

# 12. Dados temporais

Nenhum dado de ingresso deve ser tratado como eternamente verdadeiro.

Exemplo:

```text
admission_observation

institution
course
edition
modality
call_number
minimum_score
maximum_score
published_at
retrieved_at
source_id
```

Não criar coluna:

```text
current_cutoff
```

sem relacioná-la a uma edição/fonte/data.

---

# 13. Taxonomia ENEM

Separar:

## Taxonomia oficial

Competências e habilidades definidas pelo Inep.

## Taxonomia analítica

Tema/subtema criados pelo projeto.

Exemplo:

```text
Área:
Matemática

Topic:
Proporcionalidade

Subtopic:
Porcentagem

Skill:
Habilidade oficial X
```

Tema e habilidade não são sinônimos.

Uma questão pode envolver:

* múltiplos tópicos;
* múltiplas habilidades.

Deve existir:

* um tópico principal;
* zero ou mais tópicos secundários.

---

# 14. Classificação de questões

Classificação automática deve gerar candidato.

Exemplo:

```json
{
  "primary_topic": "porcentagem",
  "secondary_topics": ["razão"],
  "confidence": 0.87,
  "classified_by": "llm",
  "model": "...",
  "classification_version": "v1"
}
```

Não registrar classificação automática como verdade não versionada.

---

# 15. Frequência de temas

Qualquer ranking "mais cai no ENEM" utilizado pelo produto deve, preferencialmente, ser calculado internamente.

Exemplo:

```text
incidence(topic, window)
=
questions_of_topic / valid_questions_in_window
```

A janela deve ser explícita.

Exemplo:

* 2015–2025;
* 2021–2025.

Nunca exibir:

"Porcentagem cai em 8,4%"

sem possuir:

* período;
* método de classificação;
* quantidade de itens;
* versão do dataset.

---

# 16. Recência

O motor pode dar maior peso a edições recentes.

Entretanto, esse comportamento precisa ser parametrizado.

Exemplo candidato:

```text
historical_weight =
  0.50 × recent_window
+ 0.30 × intermediate_window
+ 0.20 × old_window
```

Os coeficientes são hipótese de modelagem, não fato educacional.

Devem ser configuráveis.

---

# 17. Qualidade

Cada pipeline deverá produzir relatório mínimo com:

* quantidade de registros lidos;
* quantidade válida;
* quantidade rejeitada;
* duplicatas;
* campos ausentes;
* inconsistências;
* checksums.

Falhas não devem ser ignoradas silenciosamente.

---

# 18. Separação entre ausência e desconhecido

Não utilizar string vazia indiscriminadamente.

Distinguir:

* `null` — informação desconhecida/não existente;
* `unknown` — categoria explicitamente não determinada;
* valor concreto.

---

# 19. Datas

Datas devem ser armazenadas em formato ISO 8601.

Quando horário for relevante:

UTC no armazenamento.

Quando o documento possuir apenas data:

não inventar horário.

---

# 20. Requisitos de reprodutibilidade

Dado um conjunto idêntico de inputs e uma versão idêntica do pipeline determinístico, o output deverá ser idêntico.

Outputs que dependam de LLM devem registrar:

* provider;
* model;
* prompt version;
* input hash;
* timestamp;
* configuração relevante.

---

# 21. Segurança

Nunca armazenar:

* API keys;
* tokens;
* senhas;
* cookies de sessão;

dentro de:

* dataset;
* código versionado;
* manifestos públicos.

Utilizar variáveis de ambiente.

---

# 22. Critérios de aceite

A SPEC está satisfeita quando:

1. existe estrutura raw/interim/processed;
2. raw é tratado como imutável;
3. cada fonte possui manifesto;
4. arquivos possuem SHA-256;
5. dados de SiSU possuem dimensão temporal;
6. transformação possui lineage;
7. classificações de IA são identificáveis;
8. métricas derivadas indicam versão/método;
9. fontes oficiais têm precedência;
10. nenhuma informação temporal relevante é hardcoded como fato permanente.
