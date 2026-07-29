# 11 — Estimativa de esforço e sprints

## 1. Time

### 1.1 Composição recomendada para o MVP

| Papel | Dedicação | Responsabilidade principal |
|---|---|---|
| Tech Lead / Senior Full-Stack AI Engineer | Integral | Arquitetura, RAG, guardrails, decisões técnicas, revisão |
| Engenheiro backend sênior | Integral | Domínio, APIs, autorização, workers, auditoria |
| Engenheiro frontend sênior | Integral | Workspace, editor, estados de IA, acessibilidade |
| Engenheiro de dados | Integral a partir da Sprint 5 | Coleta, tratamento, dbt, qualidade da jurimetria |
| Product Designer | Integral | Pesquisa, fluxos, protótipos, testes, design system |
| Product Owner com domínio jurídico | Integral | Backlog, critérios de aceite, priorização |
| Especialista jurídico (curador) | ~50 % | Conjuntos de avaliação, validação de teses, textos de alerta |
| Segurança | ~20 % | Threat model, revisão de autorização, pentest |
| DevOps / plataforma | ~30 % | Infraestrutura, CI/CD, observabilidade, custos |
| Cientista de dados / jurimetria | ~30 % a partir da Sprint 5 | Metodologia, variáveis, validação estatística |

**6 pessoas em tempo integral + 4 parciais**, equivalente a aproximadamente 7,3 FTE.

### 1.2 Como isso se relaciona à estrutura mínima da proposta

A proposta sugere 1 designer, 1 PO jurídico, 1 tech lead, 1 full-stack AI engineer, 1
dev frontend, 1 especialista jurídico e apoio parcial de segurança e dados, admitindo
que tech lead e AI engineer sejam a mesma pessoa em time enxuto.

Duas diferenças, ambas deliberadas:

**Acumular tech lead e AI engineer é viável; acumular tech lead, AI engineer e backend
não é.** O volume de trabalho de backend no MVP — autorização ABAC, RLS, máquinas de
estado, auditoria encadeada, workers idempotentes, exportação — é grande e não tem
sobreposição com o trabalho de IA. Sem o backend sênior dedicado, ou o RAG atrasa ou a
segurança fica superficial. Como a segurança é o requisito que não admite
superficialidade neste produto, o backend dedicado é a recomendação firme.

**O engenheiro de dados não é opcional se a jurimetria estiver no MVP.** A proposta já
reconhece isso ao dizer que a jurimetria exige três competências distintas. Se a
jurimetria for adiada — o que é uma decisão legítima —, esse papel e o de cientista de
dados saem do MVP e o esforço cai em cerca de 30 pessoa-semanas.

## 2. Método de estimativa

- Sprints de 2 semanas
- Capacidade de ~8 pessoa-semanas úteis por sprint por FTE de engenharia, descontadas
  reuniões, revisões e imprevistos
- Estimativa por épico em pessoa-semanas, com faixa otimista–provável–pessimista
- Reserva de 15 % para incerteza técnica, alocada explicitamente e não escondida nas
  tarefas
- Não há estimativa para o que depende de decisão externa ainda em aberto (fontes
  licenciadas, integrações do escritório)

## 3. Esforço por épico

Épicos herdados do Anexo B da proposta.

| Épico | Nome | Otim. | Prov. | Pess. | No MVP | Observação |
|---|---|---|---|---|---|---|
| E1 | Identidade e organização | 6 | 8 | 12 | Sim | Keycloak, ABAC, RLS, auditoria básica |
| E2 | Casos e acesso | 5 | 7 | 10 | Sim | Inclui barreiras éticas |
| E3 | Documentos | 12 | 16 | 24 | Sim | Ingestão, OCR, dedupe, classificação — maior incerteza é o OCR |
| E4 | Estruturação | 10 | 14 | 20 | Sim | Fatos, cronologia, lacunas, propagação de impacto |
| E5 | Conhecimento e RAG | 16 | 22 | 32 | Sim | Chunking, índice, híbrida, rerank, atribuição |
| E6 | Teses | 8 | 11 | 16 | Sim | Sugestão, requisitos, workflow de aprovação |
| E7 | Confronto | 5 | 7 | 10 | Sim | Reaproveita a infraestrutura de E6 |
| E8 | Peças | 14 | 19 | 28 | Sim | Editor com marcas de evidência é o item mais caro do frontend |
| E9 | Qualidade | 8 | 11 | 16 | Sim | Verificador + gates + checklists |
| E10 | Memória institucional | 6 | 8 | 12 | Sim | Promoção, curadoria, validade, retirada |
| E11 | Jurimetria | 18 | 26 | 40 | Restrito | Maior variância: depende inteiramente da qualidade da fonte |
| E12 | Administração | 4 | 6 | 9 | Parcial | MVP com configuração mínima |
| E13 | Observabilidade | 6 | 8 | 12 | Sim | OTel, Langfuse, painéis, custos |
| E14 | Métricas | 4 | 6 | 9 | Parcial | Baseline + indicadores essenciais |
| — | Plataforma e CI/CD | 8 | 11 | 16 | Sim | IaC, ambientes, pipelines |
| — | Design e pesquisa | 12 | 16 | 22 | Sim | Contínuo ao longo do MVP |
| — | Reserva de incerteza (15 %) | — | 19 | — | Sim | Explícita |

**Total do MVP (provável): ~148 pessoa-semanas.** Faixa: 125–180 pessoa-semanas.

Com ~7,3 FTE e considerando que designer, PO e especialista jurídico não contribuem
para o total de engenharia na mesma proporção, o cronograma resultante é de
**12 sprints ≈ 24 semanas ≈ 5,5 meses** até o final do MVP controlado.

**Se a jurimetria sair do MVP**: −26 pessoa-semanas e −2 sprints, resultando em
~10 sprints (~4,5 meses).

## 4. Sequenciamento

O princípio é o da própria proposta: **incrementos verticais**, medindo qualidade e
valor desde o início. Cada sprint entrega algo demonstrável de ponta a ponta, não uma
camada horizontal.

### Sprint 0 — Fundação e prova técnica (2 semanas)

Objetivo: **descobrir cedo o que pode inviabilizar o plano**.

- Monorepo, CI, ambientes, IaC mínimo, observabilidade básica
- Keycloak, esqueleto de autenticação, `org_id` e RLS desde a primeira migração
- **Prova técnica de RAG** sobre documentos reais autorizados: ingerir → OCR → chunk →
  indexar → recuperar → citar → abster
- **Bake-off de modelos e embeddings**, primeira medição
- Medição real de OCR sobre o acervo do design partner

Saída: viabilidade confirmada ou plano ajustado. Esta sprint existe para que uma
descoberta ruim custe duas semanas e não quatro meses.

### Sprint 1 — Identidade, organização e caso (E1, E2)

Autenticação com MFA, papéis, ABAC, RLS em todas as tabelas, barreiras éticas, CRUD de
casos, equipe, auditoria básica. **Suíte adversarial de isolamento entra no CI já
aqui** — antes de existir conteúdo para vazar, o que é o momento certo de estabelecer
o gate.

### Sprint 2 — Ingestão documental (E3)

Upload em lote, extração, OCR, qualidade por página, dedupe, classificação assistida
com correção humana, estados de falha parcial (CA-012). Primeira calibração de
chunking contra o conjunto de avaliação.

### Sprint 3 — Recuperação (E5, parte 1)

Índice híbrido, RRF, reranking, filtro pré-busca, small-to-big, busca no workspace do
caso. Teste de carga do índice. **Gates de avaliação passam a bloquear o merge.**

### Sprint 4 — Estruturação do caso (E4)

Extração de entidades, fatos, datas, valores e pedidos; cronologia editável;
`evidence_link`; lacunas e inconsistências; confirmação humana no nível médio de
criticidade; propagação de impacto (CA-010).

### Sprint 5 — Teses (E6) · início da jurimetria

Sugestão de teses com requisitos, evidências favoráveis e contrárias, riscos; workflow
de aprovação com ressalvas. Em paralelo, o engenheiro de dados inicia coleta e
tratamento do recorte jurimétrico — que é trabalho longo e precisa começar cedo.

### Sprint 6 — Confronto (E7) e base institucional (E10, parte 1)

Objeções, fragilidades, precedentes divergentes, respostas com pendências explícitas.
Modelo de ativo institucional, promoção manual, curadoria, validade.

### Sprint 7 — Composição de peças (E8, parte 1)

Templates por blocos, geração bloco a bloco, editor com marcas de evidência
persistentes, versões imutáveis, comparação entre versões.

### Sprint 8 — Qualidade e exportação (E9, E8 parte 2)

Verificador em quatro camadas, gates bloqueantes, checklist do revisor, máquina de
estados da peça, exportação DOCX/PDF com validação de gates (CA-007).
**Gate de decisão da jurimetria** ([06 §10](06-jurimetria.md)): segue ou sai.

### Sprint 9 — Jurimetria: pipeline (E11, parte 1)

Coleta consolidada, tratamento, classificação com validação humana medida, modelagem
dbt, marts versionados, testes de reprodutibilidade.

### Sprint 10 — Jurimetria: consulta e painel (E11, parte 2)

API de consulta com envelope de metodologia obrigatório, painel com filtros,
drill-down para as decisões, explicação por LLM sobre números já calculados.

### Sprint 11 — Observabilidade, custos e endurecimento (E13, E14, E12)

Painéis completos, atribuição de custo por caso e organização, cotas e disjuntores,
métricas de adoção e valor contra baseline, configuração mínima por organização,
pentest, correções, runbooks, acessibilidade revisada.

### Sprint 12 — Piloto assistido

Casos reais controlados com usuários reais, acompanhamento diário, correções rápidas,
medição contra baseline, avaliação dos critérios de saída do MVP.

## 5. Marcos e portões

| Marco | Sprint | Critério de passagem |
|---|---|---|
| M0 — Viabilidade técnica | 0 | RAG demonstra recuperação e citação corretas sobre documentos reais; OCR dentro do aceitável |
| M1 — Isolamento comprovado | 1 | Suíte adversarial passa; RLS validada com papel de aplicação real |
| M2 — Recuperação com qualidade | 3 | Recall@10 e Precision@5 acima do limiar no conjunto anotado |
| M3 — Fluxo jurídico completo | 8 | Documento → fato → tese → peça → revisão → exportação, ponta a ponta |
| M4 — Decisão sobre jurimetria | 8 | Gate de qualidade de dados avaliado |
| M5 — Prontidão para piloto | 11 | Pentest sem achado crítico; runbooks; observabilidade completa |
| M6 — Saída do MVP | 12 | Critérios de §12.5 da proposta atendidos ([13](13-estrategia-de-mvp.md)) |

## 6. Dependências não técnicas

Não estimáveis por engenharia, e capazes de atrasar o cronograma se não forem
resolvidas no prazo:

| Dependência | Necessária até | Se atrasar |
|---|---|---|
| Escritório design partner definido | Sprint 0 | Sem documentos reais, a prova técnica é sintética e perde valor |
| Autorização de uso de acervo para avaliação | Sprint 0 | Conjuntos de avaliação ficam sintéticos; limiares perdem significado |
| Área e tipo de peça definidos | Sprint 1 | Templates e chunking estrutural sem alvo |
| Baseline medido | Sprint 2 | Impossível demonstrar valor ao final |
| Tempo do especialista jurídico | Contínuo | Conjuntos de avaliação e validação de teses travam |
| Decisão sobre fontes jurimétricas | Sprint 5 | E11 não começa |
| Contratos com provedores de LLM | Sprint 1 | Bake-off fica restrito |
| Parecer do DPO sobre a base jurimétrica | Sprint 5 | E11 não começa |

## 7. Depois do MVP

| Fase | Duração estimada | Conteúdo |
|---|---|---|
| Produto operacional | 3–4 meses | Administração avançada, integrações prioritárias, design system completo, SSO, tier dedicado, SLA maior |
| Escala por áreas | 3–4 meses | Novos tipos de peça, taxonomias, workflows, mais organizações |
| Inteligência ampliada | contínuo | Novos recortes jurimétricos, avaliação contínua, orquestração avançada |

Estimativas indicativas. Serão refeitas com os dados reais de velocidade do time, que
só existem depois de três ou quatro sprints — velocidade estimada antes disso é
suposição.

---

**Anterior**: [10 — Infraestrutura, CI/CD e ambientes](10-infraestrutura-cicd-ambientes.md) · **Próximo**: [12 — Riscos técnicos](12-riscos-tecnicos.md)
