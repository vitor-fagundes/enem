# SPEC-001 — Product Goal

## Status

Draft v1.

## 1. Contexto

O projeto tem como objetivo apoiar uma preparação intensiva para o ENEM 2026 com foco específico no ingresso no curso de Relações Econômicas Internacionais da Universidade Federal de Minas Gerais via SiSU.

O usuário possui horizonte curto de preparação. Portanto, o produto não deve tentar reproduzir um cursinho completo nem cobrir integralmente todo o currículo do ensino médio.

O problema central é de alocação de recurso escasso:

> Como utilizar cada hora disponível de estudo para maximizar o ganho esperado de desempenho no ENEM?

O software deve funcionar como um sistema de apoio à decisão de estudo.

---

## 2. Objetivo principal

Maximizar o ganho esperado na nota do ENEM por unidade de tempo de estudo.

Métrica conceitual:

Δ desempenho esperado / hora de estudo

O sistema deve continuamente responder:

> Qual é a melhor próxima atividade que o usuário deve executar?

---

## 3. Objetivo de ingresso

Curso-alvo:

* Universidade: UFMG
* Curso: Relações Econômicas Internacionais
* Turno: noturno
* Modalidade principal de acompanhamento: LI_EP
* Processo seletivo: SiSU
* Meta estratégica inicial: 755 pontos
* Meta deve ser configurável

A meta de 755 não representa garantia de aprovação.

Ela representa uma margem operacional de planejamento baseada em resultados históricos recentes e deverá ser reavaliada quando novos dados oficiais estiverem disponíveis.

Notas de corte históricas nunca devem ser hardcoded na lógica da aplicação.

Devem ser armazenadas como observações temporais associadas a:

* edição;
* curso;
* instituição;
* modalidade;
* chamada;
* data;
* fonte.

---

## 4. Princípios do produto

### P1 — Questões antes de teoria

O fluxo padrão é:

questão → tentativa → correção → diagnóstico → estudo pontual → nova questão → revisão

O produto não deve incentivar consumo passivo prolongado de conteúdo.

### P2 — Evidência antes de intuição

Recomendações devem ser baseadas em dados observáveis, como:

* desempenho;
* frequência histórica;
* dificuldade;
* recorrência do erro;
* tempo gasto;
* intervalo desde última revisão;
* progresso recente.

### P3 — Fonte oficial antes de fonte secundária

Informações institucionais devem priorizar:

1. Inep;
2. MEC/SiSU;
3. UFMG;
4. análise produzida pelo próprio projeto a partir dos dados oficiais;
5. fontes educacionais secundárias;
6. inferências produzidas por LLM.

### P4 — Analytics determinístico

Métricas quantitativas não podem depender de julgamento arbitrário de LLM.

Exemplos:

* taxa de acerto;
* frequência;
* tempo médio;
* mastery score;
* intervalo de revisão;
* priority score.

Devem ser calculados de forma determinística e reproduzível.

### P5 — IA como ferramenta auxiliar

LLMs podem ser utilizadas para:

* classificação semântica;
* explicações;
* análise textual;
* geração de hipóteses;
* identificação preliminar de conceitos;
* feedback de redação;
* auxílio na categorização de erros.

LLMs não constituem fonte de verdade.

### P6 — Proveniência

Todo dado externo relevante deve possuir registro de origem.

### P7 — Desenvolvimento subordinado ao estudo

Nenhuma funcionalidade deve ser implementada apenas por interesse técnico.

Antes de incluir uma feature, deve-se responder:

> Esta funcionalidade tem probabilidade razoável de melhorar a preparação para o ENEM antes da prova?

Se não, ela deve ser postergada.

---

# 5. Usuário primário

Inicialmente existe um único usuário.

Não faz parte do MVP:

* sistema multiusuário;
* marketplace;
* recursos sociais;
* ranking;
* chat entre estudantes;
* assinatura;
* pagamentos;
* aplicativo mobile nativo;
* gamificação complexa.

---

# 6. Fluxo principal

## 6.1 Seleção

O sistema seleciona um conjunto recomendado de questões.

## 6.2 Resolução

O usuário responde às questões.

Devem ser registrados no mínimo:

* questão;
* resposta;
* horário;
* duração;
* confiança opcional.

## 6.3 Correção

O sistema determina:

* acerto;
* erro;
* alternativa correta.

## 6.4 Diagnóstico

Para respostas incorretas, registrar a causa provável.

Taxonomia inicial:

* KNOWLEDGE — falta de conhecimento;
* INTERPRETATION — interpretação;
* CALCULATION — cálculo;
* ATTENTION — desatenção;
* TIME — gerenciamento de tempo;
* GUESS — chute;
* METHOD — método inadequado;
* UNKNOWN — não classificado.

Uma tentativa pode possuir mais de uma causa, mas deve haver no máximo uma causa primária.

## 6.5 Remediação

Com base no erro, o sistema pode recomendar:

* explicação curta;
* conteúdo específico;
* questões semelhantes;
* revisão futura.

## 6.6 Atualização

Após cada tentativa, atualizar:

* desempenho do tópico;
* histórico;
* domínio estimado;
* prioridade dos tópicos;
* fila de revisão.

---

# 7. Modelo conceitual de domínio

Entidades principais:

## Question

Representa uma questão de uma prova.

## Exam

Representa uma edição/prova oficial.

## Area

Uma das áreas avaliadas no ENEM.

## Competency

Competência da Matriz de Referência.

## Skill

Habilidade da Matriz de Referência.

## Topic

Taxonomia temática própria do projeto.

## Attempt

Tentativa do usuário em uma questão.

## ErrorDiagnosis

Diagnóstico associado a tentativa incorreta.

## Mastery

Estimativa do domínio do usuário.

## Review

Atividade de revisão agendada.

## StudySession

Sessão de estudo.

## Recommendation

Recomendação produzida pelo motor de prioridade.

## AdmissionTarget

Curso, modalidade, notas históricas e meta estratégica.

---

# 8. Áreas

Identificadores canônicos:

* LC — Linguagens;
* CH — Ciências Humanas;
* CN — Ciências da Natureza;
* MT — Matemática;
* RED — Redação.

Não utilizar nomes livres internamente quando existir identificador canônico.

---

# 9. Mastery

O sistema deve possuir uma estimativa de domínio por:

* área;
* tópico;
* subtema;
* habilidade, quando houver dados suficientes.

Mastery não pode ser simplesmente:

acertos / tentativas

O cálculo posterior deve considerar, quando possível:

* recência;
* dificuldade;
* número de observações;
* consistência;
* tentativas consecutivas;
* necessidade de revisão.

Na primeira versão é aceitável utilizar uma aproximação simples, desde que explicitamente documentada.

---

# 10. Priority Engine

O motor de priorização deve produzir uma pontuação entre 0 e 1.

Conceitualmente:

priority = f(
weakness,
incidence,
expected_gain,
review_urgency,
difficulty_fit
)

Versão inicial candidata:

priority =
0.30 × weakness
+ 0.25 × incidence
+ 0.20 × expected_gain
+ 0.15 × review_urgency
+ 0.10 × difficulty_fit

Os coeficientes não são considerados cientificamente validados.

Devem:

* estar centralizados;
* ser configuráveis;
* possuir testes;
* não ser espalhados pelo código.

O sistema deve permitir futura comparação entre estratégias.

---

# 11. Princípio de dificuldade

A aplicação deve privilegiar consolidação de itens fáceis e médios antes de direcionar esforço excessivo a itens difíceis.

O produto não deve afirmar que consegue prever exatamente a nota TRI da próxima edição.

É permitido produzir:

* indicadores de coerência de desempenho;
* estimativas históricas;
* faixas;
* alertas de baixo desempenho em itens básicos.

É proibido apresentar uma simulação aproximada como nota TRI real.

---

# 12. Home do MVP

A página inicial deve responder imediatamente:

1. Qual é minha meta?
2. Quanto falta para a prova?
3. Como estou performando?
4. Onde estou perdendo desempenho?
5. O que devo fazer agora?

Componentes mínimos:

* meta;
* dias restantes;
* questões realizadas;
* taxa de acerto;
* desempenho por área;
* tópicos prioritários;
* revisões pendentes;
* CTA "Iniciar sessão".

---

# 13. Sessão recomendada

O usuário deve conseguir iniciar uma sessão gerada pelo sistema.

Exemplo:

* 15 questões de matemática básica;
* 10 de ecologia;
* 5 revisões;
* 10 questões de interpretação.

Cada recomendação deve possuir uma justificativa legível.

Exemplo:

"Prioridade alta porque possui alta incidência histórica, domínio estimado de 48% e três erros recentes."

O sistema não deve mostrar apenas um score opaco.

---

# 14. Explicabilidade

Toda recomendação automática deve possuir razões rastreáveis.

Exemplo:

priority = 0.81

Motivos:

* weakness = 0.82;
* incidence = 0.76;
* reviewUrgency = 0.91;
* difficultyFit = 0.74.

O usuário deve conseguir entender por que determinado tópico está sendo priorizado.

---

# 15. Redação

Redação deverá futuramente possuir subsystem próprio.

Entidades mínimas futuras:

* Essay;
* EssayEvaluation;
* CompetencyScore;
* EssayRevision.

Competências C1–C5 devem ser armazenadas separadamente.

Não faz parte do primeiro incremento funcional.

---

# 16. Requisitos não funcionais

## Reprodutibilidade

Transformações de dados devem poder ser reproduzidas.

## Auditabilidade

Deve ser possível identificar a origem de dados externos.

## Testabilidade

Regras de negócio devem ser isoladas de UI.

## Simplicidade

Evitar arquitetura distribuída ou infraestrutura desnecessária.

## Local-first

O MVP deve conseguir executar localmente.

## Performance

Não existe necessidade inicial de processamento distribuído.

## Segurança

Não incluir credenciais ou API keys no repositório.

---

# 17. Stack inicial

Preferencial:

Frontend / aplicação:

* Next.js;
* TypeScript;
* Tailwind.

Banco operacional:

* SQLite.

ORM:

* Drizzle ORM.

Pipeline:

* Python.

Processamento:

* Polars.

Armazenamento analítico:

* Parquet.

Consultas analíticas:

* DuckDB.

Testes:

* Vitest;
* Playwright;
* pytest.

A stack pode ser alterada somente mediante justificativa documentada em ADR.

---

# 18. Non-goals do MVP

O MVP não deve tentar:

* ensinar todo o conteúdo do ENEM;
* substituir professor;
* prever nota TRI exata;
* produzir redações para memorização;
* criar rede social;
* competir com plataformas de cursinho;
* suportar múltiplos vestibulares;
* suportar múltiplas instituições;
* usar Spark;
* criar microsserviços;
* introduzir Kafka;
* utilizar banco vetorial sem caso de uso demonstrado;
* implementar agentes autônomos sem necessidade.

---

# 19. Critérios de aceite da SPEC-001

A implementação inicial é considerada aderente quando:

1. existe configuração de objetivo de ingresso;
2. meta é configurável;
3. usuário consegue registrar tentativa de questão;
4. sistema registra acerto/erro;
5. erro pode receber categoria;
6. desempenho é agregado por área/tópico;
7. sistema produz lista ordenada de prioridades;
8. recomendação apresenta justificativa;
9. regras quantitativas são determinísticas;
10. nenhuma dependência de LLM é necessária para o fluxo principal.

---

# 20. Regra de ouro

Quando existir conflito entre:

* sofisticação técnica; e
* velocidade de aprendizado,

priorizar velocidade de aprendizado.

