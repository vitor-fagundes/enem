# Spec Analysis — fundação

Fontes: [SPEC-001](../specs/001-product-goal.md) e [SPEC-002](../specs/002-data-sources.md), lidas integralmente, Draft v1. O pedido desta entrega limita o trabalho ao esqueleto; não equivale à satisfação dos critérios funcionais das specs.

## 1. Domínio

Ferramenta pessoal de apoio à decisão para preparação intensiva ao ENEM: maximizar ganho esperado por hora de estudo. Objetivo inicial especificado: REI/UFMG, noturno, LI_EP, meta configurável de 755. A meta é planejamento, não garantia de ingresso nem nota de corte oficial verificada.

## 2. Requisitos funcionais

SPEC-001 §§3,6,9–14,19: configurar ingresso/meta; selecionar questões; registrar resposta, horário, duração e confiança opcional; corrigir; diagnosticar erros; recomendar remediação; agregar desempenho; atualizar domínio, prioridade e revisão; iniciar sessões justificadas; home com meta, prazo, desempenho e próxima ação.
SPEC-002 §§6–20: catalogar fontes, preservar originais, manifestos e SHA-256; transformar com lineage e qualidade; guardar observações temporais; separar taxonomias oficial/analítica; versionar classificações; contextualizar incidências e parametrizar recência.
Esses requisitos são identificados, não implementados nesta fundação.

## 3. Requisitos não funcionais

Execução local para um usuário; simplicidade; testabilidade com domínio separado da UI; cálculo determinístico; reprodutibilidade; auditabilidade; secrets fora do Git. Não há SLO, orçamento de memória ou tamanho máximo de datasets especificados. Baixo volume operacional não implica microdados pequenos.

## 4. Invariantes

- Originais raw imutáveis; SHA-256 na ingestão e proveniência de todo dado externo relevante.
- Precedência oficial; dados calculados, secundários e de IA distinguíveis.
- Meta configurável; notas históricas vinculadas a edição, instituição, curso, modalidade, chamada, data e fonte.
- Áreas canônicas LC, CH, CN, MT, RED; tópico não é habilidade.
- Questão com um tópico principal e zero ou mais secundários; múltiplas habilidades possíveis.
- Diagnóstico de tentativa incorreta com múltiplas causas e no máximo uma primária; categorias canônicas da SPEC-001 §6.4.
- Priority entre 0 e 1; pesos configuráveis/centralizados/testados; justificativa rastreável.
- Mastery não se reduz a acertos/tentativas; estimativa não é TRI real.
- Datas ISO 8601; horários em UTC; não inventar horário para documento que tem somente data.
- Distinguir null, categoria desconhecida e valor concreto; falhas de qualidade não são silenciosas.

## 5. Entidades

Explícitas: Question, Exam, Area, Competency, Skill, Topic, Attempt, ErrorDiagnosis, Mastery, Review, StudySession, Recommendation, AdmissionTarget.
Conceitos implicados pela SPEC-002, ainda sem schema decidido: Subtopic, recurso de origem, manifesto, observação temporal de ingresso, classificação versionada, execução de transformação e relatório de qualidade.
Futuras para redação: Essay, EssayEvaluation, CompetencyScore, EssayRevision (C1–C5 separadas).

## 6. Fluxos

1. Seleção → resolução → correção → diagnóstico → estudo pontual → nova questão/revisão → atualização de indicadores.
2. Fonte autorizada → aquisição original + manifesto/hash → raw → transformação em interim → processed, com lineage e relatório de qualidade em cada estágio.
3. Observação oficial de ingresso → histórico temporal → reavaliação da meta, sem transformar histórico em garantia.

## 7. Riscos

Taxonomia ou gabarito incorretos propagam erros; dados incompletos enviesam incidências; poucas tentativas fragilizam domínio estimado; heurísticas não validadas podem parecer precisão científica. Dados institucionais podem mudar e a disponibilidade até 2025 precisa ser conferida antes da ingestão. Originais podem incluir dados sensíveis; aquisição futura precisa definir minimização. Crescimento de escopo compete com tempo de estudo. Contratos divergentes entre Python e aplicação podem produzir resultados inconsistentes.

## 8. Ambiguidades e critérios ausentes

- Q1: identidade de questão entre cadernos, versões, aplicações e idiomas; tratamento de anuladas e gabaritos retificados.
- Q2: fórmulas, normalização, ausência de dados e critérios de aceite para mastery, prioridade, dificuldade, ganho esperado e revisão. Pesos candidatos não são decisão aprovada.
- Q3: duração/pausa de sessão, repetição de tentativa e autoria/correção do diagnóstico.
- Q4: construção/versionamento de tópicos e subtemas; aprovação humana das classificações candidatas.
- Q5: URLs e versões oficiais das fontes, janela histórica, disponibilidade das edições e precedência em conflitos dentro do Tier A.
- Q6: formato/local do manifesto, identidade do recurso, deduplicação, atomicidade, política de rejeições e contrato de lineage.
- Q7: reprodutibilidade significa bytes ou conteúdo lógico? Timestamps de execução devem ser separados dos outputs determinísticos.
- Q8: Tier B é descrito como derivado de Tier A, mas inclui desempenho pessoal: definir proveniência de observações locais.
- Q9: datas da prova, regras/pesos de ingresso e atualização histórica precisam de fontes temporais; não serão hardcoded.
- Q10: critérios de aceite por incremento, limites de performance, backup/restauração e intercâmbio analytics/aplicação ainda não definidos.

Nada disso bloqueia um esqueleto sem regras de produto. Bloqueia a implementação das respectivas funcionalidades até especificação.

## 9. Decisões arquiteturais

ADR-0001 registra monólito Next.js/SQLite com Drizzle e analytics Python/Polars/DuckDB/Parquet. npm workspaces evita um orquestrador extra. uv com lockfile reproduz o ambiente Python; ESLint/Prettier e Ruff atendem lint/format. better-sqlite3 é o adaptador local do Drizzle. Schema e migrações aguardam spec; a conexão não tem efeitos no import. Troca de dados e algoritmos ficam em aberto.

## 10. Fora do MVP e desta entrega

Fora do MVP: cursinho completo, substituição de professor, TRI exata, redações para memorização, multiusuário, marketplace, social/ranking/chat, assinatura/pagamentos, mobile nativo, gamificação complexa, múltiplos vestibulares/instituições e infraestrutura distribuída sem necessidade.
Adiados nesta entrega: importação completa de provas, parser de microdados, login/autenticação, RAG/OpenAI, recommendation engine, mastery, redação, scraping e dashboard completo. Redação é futura na SPEC-001, não faz parte do primeiro incremento funcional.

## Próxima spec recomendada

SPEC-004 — Source Resource and Minimal Local Ingestion Contract. Definir manifesto, identidade, SHA-256, imutabilidade, duplicação/retificação, datas, lineage e qualidade, com critérios de aceite em fixtures pequenas. Sem baixar microdados completos. Não implementada nesta entrega.
