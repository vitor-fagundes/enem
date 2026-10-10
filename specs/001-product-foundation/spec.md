# Feature Specification: Product Foundation

**Feature Branch**: `N/A (retrospective migration; no branch created)`

**Created**: 2026-09-18

**Status**: Draft

**Input**: User description: "Migrar retrospectivamente `specs/001-product-goal.md` para o formato nativo do GitHub Spec Kit, preservando integralmente seu significado, sem implementar código, sem alterar as specs 002, 003 ou 004 e sem apagar o legado."

## Migration Provenance

Este artefato foi reconstruído retrospectivamente durante a migração para o GitHub Spec Kit. Ele expressa no formato atual o Product Foundation originalmente registrado em `specs/001-product-goal.md`; não representa uma nova feature, não declara requisitos como já implementados e não autoriza implementação neste incremento. O Product Foundation define as capacidades pretendidas do produto; cada capacidade será implementada por meio de especificações de feature menores e incrementais. O documento legado permanece preservado como fonte histórica da migração.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Escolher a próxima atividade de maior valor (Priority: P1)

Como estudante em preparação intensiva para o ENEM 2026, quero receber uma próxima atividade priorizada a partir do meu desempenho e de evidências do exame para aplicar meu tempo escasso onde existe maior ganho esperado por hora de estudo.

**Why this priority**: Apoiar essa decisão é o problema central do produto. Sem uma próxima ação útil, o produto não cumpre sua finalidade.

**Independent Test**: Pode ser testada fornecendo histórico de desempenho, incidência, urgência de revisão e adequação de dificuldade, e verificando que o produto apresenta uma lista ordenada, uma próxima atividade e uma justificativa rastreável.

**Acceptance Scenarios**:

1. **Given** que existem evidências suficientes sobre desempenho e conteúdo, **When** o usuário solicita o que estudar agora, **Then** o produto apresenta uma lista ordenada de prioridades e uma próxima atividade recomendada.
2. **Given** uma recomendação automática, **When** o usuário consulta seus motivos, **Then** ele vê uma justificativa legível e os fatores rastreáveis que contribuíram para a prioridade.
3. **Given** os mesmos dados e a mesma configuração, **When** a prioridade é recalculada, **Then** o resultado quantitativo é reproduzido sem depender de LLM.

---

### User Story 2 - Aprender por um ciclo orientado por questões (Priority: P1)

Como estudante, quero resolver questões, corrigir minhas respostas, diagnosticar meus erros e receber remediação pontual para transformar cada tentativa em evidência de aprendizagem e evitar consumo passivo prolongado de teoria.

**Why this priority**: O fluxo questão → tentativa → correção → diagnóstico → estudo pontual → nova questão → revisão é o princípio operacional básico do produto.

**Independent Test**: Pode ser testada completando uma tentativa incorreta e verificando o registro mínimo, a correção, o diagnóstico, uma opção de remediação e a atualização do histórico e das prioridades.

**Acceptance Scenarios**:

1. **Given** uma questão selecionada, **When** o usuário responde, **Then** ficam registrados a questão, a resposta, o horário, a duração e, se informado, o nível de confiança.
2. **Given** uma tentativa concluída com gabarito oficial válido e aplicável, **When** ocorre a correção, **Then** o produto informa acerto ou erro e a alternativa correta.
3. **Given** uma tentativa concluída associada a questão anulada ou com gabarito não resolvido, **When** ocorre a correção, **Then** o produto respeita a situação oficial do gabarito e não trata a tentativa como erro do usuário.
4. **Given** uma resposta incorreta, **When** o usuário registra o diagnóstico, **Then** pode associar uma ou mais causas permitidas, com no máximo uma causa primária.
5. **Given** um erro diagnosticado, **When** o ciclo continua, **Then** o produto pode oferecer explicação curta, conteúdo específico, questões semelhantes ou revisão futura e atualiza o histórico correspondente.

---

### User Story 3 - Entender progresso e prioridades (Priority: P2)

Como estudante, quero visualizar minha meta, o tempo restante, meu desempenho, minhas principais perdas e a ação recomendada para compreender meu estado sem interpretar um score opaco.

**Why this priority**: A visão consolidada sustenta decisões rápidas e mantém a recomendação vinculada à meta de ingresso.

**Independent Test**: Pode ser testada abrindo a visão inicial com dados de exemplo e verificando que ela responde às cinco perguntas essenciais e oferece acesso ao início de uma sessão.

**Acceptance Scenarios**:

1. **Given** uma meta e tentativas registradas, **When** o usuário acessa a visão inicial, **Then** encontra meta, dias restantes, questões realizadas, taxa de acerto, desempenho por área, tópicos prioritários, revisões pendentes e a ação "Iniciar sessão".
2. **Given** dados suficientes em diferentes níveis, **When** o usuário consulta seu domínio, **Then** encontra estimativas por área, tópico, subtema e, quando suportado pelas evidências, habilidade.
3. **Given** uma estimativa ou faixa relacionada à TRI, **When** ela é exibida, **Then** é identificada como aproximação histórica e nunca como a nota TRI real ou uma previsão exata da próxima edição.

---

### User Story 4 - Manter uma meta de ingresso contextualizada (Priority: P2)

Como estudante, quero configurar minha meta de ingresso e acompanhar observações históricas com edição, modalidade, chamada, data e fonte para planejar sem tratar uma nota de corte passada como garantia permanente.

**Why this priority**: A recomendação só tem valor estratégico quando relacionada a uma meta explícita e temporalmente contextualizada.

**Independent Test**: Pode ser testada configurando a meta inicial, alterando a pontuação estratégica e registrando duas observações históricas distintas sem substituir ou fixar uma delas como verdade permanente.

**Acceptance Scenarios**:

1. **Given** o perfil inicial do produto, **When** a meta é consultada, **Then** ela identifica UFMG, Relações Econômicas Internacionais, turno noturno, modalidade LI_EP, SiSU e a meta estratégica inicial de 755 pontos.
2. **Given** que o usuário deseja outro valor de planejamento, **When** ele altera a meta estratégica, **Then** o novo valor passa a orientar o acompanhamento sem ser apresentado como garantia de aprovação.
3. **Given** novas informações oficiais de ingresso, **When** uma observação é registrada, **Then** ela permanece vinculada à edição, curso, instituição, modalidade, chamada, data e fonte correspondentes.

### Edge Cases

- Quando ainda não há observações suficientes, estimativas de domínio e recomendações devem explicitar a insuficiência de evidência, sem inventar precisão.
- Uma tentativa pode ter várias causas de erro, mas nunca mais de uma causa primária; `UNKNOWN` representa causa explicitamente não classificada.
- A ausência de confiança informada não invalida a tentativa, pois esse campo é opcional.
- Uma nova nota de corte ou regra de ingresso não sobrescreve silenciosamente observações anteriores nem se torna um fato atemporal.
- A indisponibilidade de LLM não impede seleção, registro de tentativa, correção, métricas, priorização ou justificativa do fluxo principal.
- Desempenho elevado em itens difíceis não deve desviar esforço da consolidação necessária de itens fáceis e médios.
- Quando não existem revisões pendentes, a visão inicial deve distinguir fila vazia de informação desconhecida.
- Uma aproximação simples de domínio é aceitável na primeira versão apenas se suas limitações e regras forem explícitas.

## Requirements *(mandatory)*

### Scope Boundaries

Esta especificação define as capacidades pretendidas do produto de apoio à decisão de estudo para um único usuário, a serem implementadas por meio de especificações de feature subsequentes, e preserva capacidades futuras descritas no legado. A presente migração produz somente documentação: não implementa essas capacidades e não altera o estado atual descrito no README.

Estão fora do MVP: cobertura integral do currículo, substituição de professor, previsão exata de nota TRI, redações para memorização, múltiplos usuários, marketplace, recursos sociais, ranking, chat, assinatura, pagamentos, aplicativo móvel nativo, gamificação complexa, múltiplos vestibulares, múltiplas instituições e complexidade técnica sem caso de uso demonstrado. Isso inclui arquitetura distribuída, processamento de grande escala, mensageria distribuída, busca vetorial e agentes autônomos enquanto não houver necessidade comprovada. O subsistema de redação também fica fora do primeiro incremento funcional.

### Functional Requirements

- **FR-001**: O produto MUST funcionar como sistema de apoio à decisão para maximizar o ganho esperado de desempenho no ENEM por hora de estudo e MUST responder qual é a melhor próxima atividade do usuário.
- **FR-002**: O produto MUST adotar como fluxo padrão questão → tentativa → correção → diagnóstico → estudo pontual → nova questão → revisão e MUST NOT incentivar consumo passivo prolongado de conteúdo.
- **FR-003**: Recomendações MUST usar evidências observáveis, incluindo, quando disponíveis, desempenho, frequência histórica, dificuldade, recorrência do erro, tempo gasto, intervalo desde a última revisão e progresso recente.
- **FR-004**: Informações institucionais MUST respeitar a precedência Inep; MEC/SiSU; UFMG; análises do projeto baseadas em dados oficiais; fontes educacionais secundárias; inferências de LLM.
- **FR-005**: Todo dado externo relevante MUST manter proveniência, e fatos oficiais, resultados derivados, fontes secundárias e inferências de IA MUST permanecer distinguíveis conforme a SPEC-002.
- **FR-006**: Métricas quantitativas, incluindo taxa de acerto, frequência, tempo médio, domínio, intervalo de revisão e prioridade, MUST ser determinísticas e reproduzíveis e MUST NOT depender de julgamento de LLM.
- **FR-007**: LLM MAY auxiliar classificação semântica, explicações, análise textual, hipóteses, identificação preliminar de conceitos, feedback de redação e categorização de erros, mas MUST NOT ser fonte de verdade nem requisito do fluxo principal.
- **FR-008**: O produto MUST atender inicialmente a um único usuário.
- **FR-009**: A meta inicial MUST representar UFMG, Relações Econômicas Internacionais, turno noturno, modalidade LI_EP e processo SiSU, com meta estratégica inicial configurável de 755 pontos.
- **FR-010**: A meta estratégica MUST ser apresentada como margem operacional de planejamento, MUST NOT ser tratada como garantia de aprovação e MUST poder ser reavaliada quando surgirem novos dados oficiais.
- **FR-011**: Notas históricas de ingresso MUST NOT ser fixadas como regra permanente e MUST ser observações temporais associadas a edição, curso, instituição, modalidade, chamada, data e fonte.
- **FR-012**: Ao registrar uma tentativa, o produto MUST guardar a questão, a resposta, o horário e a duração; a confiança MAY ser registrada opcionalmente.
- **FR-013**: Quando existir gabarito oficial válido e aplicável, a correção MUST determinar acerto ou erro e a alternativa correta. Para questões anuladas ou com gabarito não resolvido, a tentativa MUST ser preservada, mas MUST NOT ser classificada como acerto ou erro e MUST NOT ser contabilizada como erro do usuário.
- **FR-014**: Uma resposta incorreta MUST poder receber uma ou mais causas dentre `KNOWLEDGE`, `INTERPRETATION`, `CALCULATION`, `ATTENTION`, `TIME`, `GUESS`, `METHOD` e `UNKNOWN`, com no máximo uma causa primária.
- **FR-015**: A remediação de um erro MAY recomendar explicação curta, conteúdo específico, questões semelhantes ou revisão futura.
- **FR-016**: Após cada tentativa, o produto MUST atualizar o histórico, o desempenho agregado por área e tópico, o domínio estimado, a prioridade dos tópicos e a fila de revisão.
- **FR-017**: As áreas MUST usar os identificadores canônicos `LC`, `CH`, `CN`, `MT` e `RED` sempre que houver identificador aplicável, evitando nomes livres equivalentes.
- **FR-018**: O domínio MUST poder ser estimado por área, tópico, subtema e, quando houver dados suficientes, habilidade; o cálculo MUST NOT ser apenas acertos divididos por tentativas.
- **FR-019**: A estimativa de domínio SHOULD considerar recência, dificuldade, quantidade de observações, consistência, tentativas consecutivas e necessidade de revisão. Uma aproximação inicial mais simples MAY ser usada se estiver explicitamente documentada.
- **FR-020**: O motor de priorização MUST produzir pontuação entre 0 e 1 a partir de fraqueza, incidência, ganho esperado, urgência de revisão e adequação da dificuldade.
- **FR-021**: A política candidata inicial de prioridade MUST preservar os pesos `0,30 × fraqueza + 0,25 × incidência + 0,20 × ganho esperado + 0,15 × urgência de revisão + 0,10 × adequação da dificuldade`; esses pesos MUST ser tratados como hipótese não validada, mantidos em uma configuração única, ajustável e verificável, permitindo comparação futura entre estratégias.
- **FR-022**: A priorização MUST favorecer a consolidação de itens fáceis e médios antes de direcionar esforço excessivo a itens difíceis.
- **FR-023**: O produto MUST NOT afirmar que prevê exatamente a nota TRI da próxima edição. Ele MAY apresentar coerência de desempenho, estimativas históricas, faixas e alertas de baixo desempenho em itens básicos, desde que aproximações não sejam apresentadas como nota TRI real.
- **FR-024**: A visão inicial MUST responder qual é a meta, quanto falta para a prova, como está o desempenho, onde há perda de desempenho e o que fazer agora.
- **FR-025**: A visão inicial MUST apresentar meta, dias restantes, questões realizadas, taxa de acerto, desempenho por área, tópicos prioritários, revisões pendentes e a ação "Iniciar sessão".
- **FR-026**: O usuário MUST poder iniciar uma sessão gerada pelo produto, combinando questões direcionadas e revisões conforme as prioridades disponíveis.
- **FR-027**: Toda recomendação automática MUST apresentar justificativa legível e razões rastreáveis, incluindo os valores disponíveis dos fatores que formaram sua prioridade, em vez de somente um score opaco.
- **FR-028**: Transformações e cálculos MUST ser reproduzíveis; dados externos MUST ser auditáveis; regras de negócio MUST ser testáveis separadamente da interface; e o produto MUST permanecer simples e local-first, sem exigir processamento distribuído no cenário inicial.
- **FR-029**: Credenciais, tokens e chaves de acesso MUST NOT ser registrados no repositório nem em dados versionados.
- **FR-030**: Uma capacidade MUST ser adiada quando não houver probabilidade razoável de melhorar a preparação para o ENEM antes da prova; em conflitos entre sofisticação técnica e velocidade de aprendizado, a velocidade de aprendizado MUST prevalecer.

### Deferred Capabilities

As capacidades abaixo fazem parte da visão do produto, mas estão explicitamente fora do primeiro incremento funcional. Serão especificadas em features próprias.

- **DC-001** *(originalmente FR-031)*: O futuro subsistema de redação MUST representar redação, avaliação, pontuações separadas por competência (C1–C5) e revisão. Este subsistema permanece fora do primeiro incremento funcional.

### Requirement Acceptance Traceability

| Requirement | Acceptance evidence |
|-------------|---------------------|
| FR-001–FR-007 | User Story 1 scenarios 1–3; deterministic repetition and recommendation provenance review |
| FR-008–FR-011 | User Story 4 scenarios 1–3; single-user scope inspection |
| FR-012–FR-016 | User Story 2 scenarios 1–5; invalid multiple-primary diagnosis rejection |
| FR-017–FR-023 | User Story 3 scenarios 2–3; canonical-area, mastery, priority-range and difficulty-policy checks |
| FR-024–FR-027 | User Story 1 scenarios 1–2 and User Story 3 scenario 1 |
| FR-028–FR-030 | Reproducibility, auditability, local operation, secret scan and scope review |
| DC-001 (ex-FR-031) | Scope review confirms the subsystem and C1–C5 model remain documented but unimplemented in the first increment |

### Key Entities *(include if feature involves data)*

- **Question**: Questão de uma prova que pode ser selecionada e respondida.
- **Exam**: Edição ou prova oficial à qual questões e metadados pertencem.
- **Area**: Uma das áreas canônicas `LC`, `CH`, `CN`, `MT` ou `RED`.
- **Competency**: Competência da Matriz de Referência oficial.
- **Skill**: Habilidade da Matriz de Referência oficial, distinta de tópico analítico.
- **Topic**: Classificação temática própria do projeto, incluindo possíveis subtemas.
- **Attempt**: Resposta do usuário a uma questão, com horário, duração, confiança opcional e resultado de correção.
- **ErrorDiagnosis**: Uma ou mais causas associadas a uma tentativa incorreta, com no máximo uma causa primária.
- **Mastery**: Estimativa documentada do domínio do usuário em uma granularidade e momento determinados.
- **Review**: Atividade de revisão agendada a partir das evidências de aprendizagem.
- **StudySession**: Conjunto recomendado de questões e revisões executado como uma unidade de estudo.
- **Recommendation**: Próxima ação ou prioridade calculada, acompanhada de score e razões rastreáveis.
- **AdmissionTarget**: Instituição, curso, turno, modalidade, processo seletivo e meta estratégica configurável.
- **AdmissionObservation**: Registro temporal de informação histórica de ingresso associado à edição, chamada, data e fonte.

## Success Criteria *(mandatory)*

### Measurable Product Outcomes

- **SC-001**: Em uma avaliação de ponta a ponta, o usuário completa o ciclo de questão, tentativa, correção, diagnóstico, remediação e atualização sem depender de LLM.
- **SC-002**: 100% das tentativas aceitas contêm questão, resposta, horário e duração; 100% das tentativas corrigidas com gabarito oficial válido e aplicável indicam acerto ou erro e alternativa correta; tentativas associadas a questões anuladas ou com gabarito não resolvido são preservadas, não classificadas como acerto ou erro e não contabilizadas como erro do usuário.
- **SC-003**: 100% das recomendações automáticas exibidas contêm pontuação no intervalo de 0 a 1, uma justificativa legível e os fatores disponíveis que sustentam a ordem apresentada.
- **SC-004**: Para 100% dos casos de teste, entradas e configurações quantitativas idênticas produzem as mesmas métricas, prioridades e filas de revisão.
- **SC-005**: A visão inicial apresenta os oito componentes mínimos e permite ao usuário responder às cinco perguntas essenciais sem consultar outra tela.
- **SC-006**: 100% das observações históricas de ingresso utilizadas no planejamento estão ligadas a edição, curso, instituição, modalidade, chamada, data e fonte, e nenhuma é apresentada como garantia de aprovação.
- **SC-007**: Em revisão de aceitação, o usuário identifica corretamente a meta vigente, a atividade recomendada e pelo menos um motivo verificável para essa recomendação.
- **SC-008**: O fluxo principal permanece utilizável quando qualquer recurso de LLM está indisponível.
- **SC-009**: Nenhuma estimativa aproximada é rotulada como nota TRI real ou previsão exata, e os cenários de consolidação priorizam itens fáceis e médios quando essa necessidade está evidenciada.

### Migration Acceptance

- **MA-001**: Uma auditoria de escopo encontra zero capacidades dos non-goals ou do subsistema de redação implementadas como parte da migração desta especificação.

## Assumptions

- O usuário inicial é uma única pessoa preparando-se para o ENEM 2026 com foco em Relações Econômicas Internacionais na UFMG via SiSU, modalidade LI_EP e turno noturno.
- A meta de 755 pontos é um valor estratégico inicial configurável e uma margem de planejamento, não uma promessa de ingresso.
- O Product Foundation descreve o produto pretendido; o README continua sendo a referência para o estado efetivamente implementado.
- Os coeficientes de prioridade são uma hipótese inicial preservada do documento legado e exigem validação futura, sem serem apresentados como verdade científica.
- Datas oficiais, notas históricas e demais fatos externos serão obtidos e versionados segundo a SPEC-002; nenhum valor temporal é presumido permanente.
- A arquitetura vigente e eventuais mudanças materiais são governadas pelo ADR-0001 e por ADRs posteriores, sem serem redefinidas nesta especificação funcional.
- Esta migração não substitui nem modifica as specs 002, 003 e 004; cada uma permanece autoritativa em seu próprio escopo.

## Dependencies

- `specs/001-product-goal.md`: fonte histórica integral desta reconstrução retrospectiva e mantida sem alteração.
- `.specify/memory/constitution.md`: princípios de governança, disciplina de escopo, determinismo e integridade de dados.
- `specs/002-data-sources.md`: regras detalhadas de fontes, proveniência, temporalidade, reprodutibilidade e segurança de dados.
- `docs/adr/0001-initial-architecture.md`: decisão arquitetural vigente para a fundação.
- `README.md`: registro do estado atual da implementação e do escopo técnico já entregue.
