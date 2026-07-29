# 00 — Sumário executivo

> **Documento**: Especificação Técnica PROJUR v1.0
> **Origem**: PROJUR — Proposta Inicial de Produto v0.1, 28/07/2026
> **Responsável técnico**: Tech Lead / Senior Full-Stack AI Engineer
> **Data**: 29 de julho de 2026

---

## 1. O que este documento é

A proposta v0.1 definiu **o que** construir e **por quê**. Esta especificação define
**como** construir, com decisões técnicas assumidas e justificadas. Ela é o insumo
para: revisão de arquitetura, threat modeling, orçamento, contratação do time e
abertura do backlog de engenharia.

A proposta v0.1 declarou explicitamente que "não constitui especificação técnica
definitiva" e listou dez decisões em aberto (§16.3). Este documento **fecha as
decisões que são técnicas** e **mantém abertas as que são de negócio, jurídicas ou
contratuais**, marcando cada uma com o responsável pela decisão e o prazo em que ela
bloqueia a engenharia. A tabela de dependências está em
[13 — Estratégia de MVP §6](13-estrategia-de-mvp.md#6-decisões-que-bloqueiam-a-engenharia).

## 2. A tese técnica

A proposta afirma que o diferencial defensável do PROJUR não está no modelo de
linguagem, mas no processo integrado (v0.1 §2.2). A tradução técnica dessa afirmação
é direta e organiza toda esta especificação:

> **O modelo de linguagem é um componente substituível dentro de um sistema cuja
> propriedade central é a rastreabilidade verificável entre afirmação, evidência,
> fonte, aprovação humana e registro de auditoria.**

Disso decorrem quatro invariantes de sistema. Elas não são "boas práticas": são
propriedades que o código deve tornar **impossíveis de violar**, verificadas por
testes automatizados que quebram o build.

| # | Invariante | Onde é imposta | Teste que a garante |
|---|---|---|---|
| **I-1** | Nenhuma recuperação retorna conteúdo fora do escopo autorizado do usuário e do caso | Filtro de autorização **antes** da busca vetorial + RLS no PostgreSQL | Suíte adversarial de vazamento cross-tenant no CI ([09 §4.4](09-observabilidade-custos-e-avaliacao.md)) |
| **I-2** | Toda afirmação material gerada carrega referência resolvível a trecho de origem, ou é rotulada como hipótese sem suporte | Contrato de saída estruturada + verificador de suporte pós-geração | Métrica de atribuição com limiar mínimo no CI |
| **I-3** | Nenhum indicador jurimétrico é produzido por LLM | Camada analítica SQL separada; a LLM só recebe resultados já calculados | Teste de reprodutibilidade: mesma consulta + mesmo dataset ⇒ mesmo número |
| **I-4** | Nenhuma transição de estado crítica ocorre sem identidade, autorização e evento de auditoria | Máquina de estados no servidor + trilha append-only encadeada por hash | Teste de máquina de estados; verificação de integridade da cadeia |

Cada invariante mapeia diretamente para os critérios de aceite da proposta:
I-1 → CA-003; I-2 → CA-001, CA-002, CA-004; I-3 → CA-008, CA-009; I-4 → CA-005,
CA-006, CA-007, CA-011.

## 3. Decisões estruturantes

| Área | Decisão | Justificativa resumida | ADR |
|---|---|---|---|
| Banco vetorial | PostgreSQL 16 + pgvector (HNSW), **não** vector DB dedicado | Manter vetores no mesmo motor que aplica RLS elimina a duplicação da fronteira de autorização — a causa mais comum de vazamento entre tenants | [0001](../adr/0001-postgres-pgvector-como-banco-vetorial.md) |
| Aplicação | Monorepo: Next.js (App Router, TypeScript) + FastAPI (Python 3.12) + workers Celery | Frontend precisa de editor rico e streaming; backend de IA precisa do ecossistema Python; separar HTTP de processamento longo é requisito de §10.3 | [0002](../adr/0002-monorepo-next-e-fastapi.md) |
| Isolamento | Duas camadas: ABAC na aplicação + Row-Level Security no banco | Defesa em profundidade: um bug de query não basta para vazar; um bug de política não basta para vazar | [0003](../adr/0003-isolamento-multitenant-em-duas-camadas.md) |
| Modelos | Gateway próprio com interface provider-agnostic; roteamento por criticidade e custo | §10.3 exige portabilidade; §16.1 lista dependência de fornecedor como risco; custo variável de IA é risco de margem | [0004](../adr/0004-gateway-de-modelos-e-portabilidade.md) |
| Recuperação | Busca híbrida (denso + léxico pt-BR) fundida por RRF, seguida de reranker cross-encoder | Texto jurídico combina vocabulário técnico exato (artigos, súmulas, números) com paráfrase semântica; nenhuma das duas buscas sozinha é suficiente | [0005](../adr/0005-busca-hibrida-rrf-e-reranking.md) |
| Jurimetria | Pipeline de dados versionado + cálculo em SQL; LLM apenas classifica (com validação humana medida) e explica | A proposta é categórica: "os cálculos pertencem à camada analítica estruturada" (§7.5) | [0006](../adr/0006-camada-analitica-separada-da-llm.md) |
| Auditoria | Tabela append-only com encadeamento de hash + exportação WORM | Trilha que o próprio operador pode alterar não sustenta prova; §10.1 exige registro de acessos e exportações | [0007](../adr/0007-auditoria-append-only-com-encadeamento-de-hash.md) |
| Identidade | Keycloak (OIDC) autogerenciado, com MFA e SAML para SSO corporativo | Requisito de residência de dados e de SSO em vendas B2B para escritórios de médio porte | [0008](../adr/0008-identidade-com-keycloak-oidc.md) |

## 4. Onde esta especificação diverge ou aprofunda a proposta

Três pontos merecem atenção explícita do comitê de produto, porque implicam escolha
consciente e não são simples detalhamento.

**4.1 — "Chat" não é a interface primária, e isso tem custo de adoção.**
A proposta acerta ao dizer que o chat é interface complementar sobre entidades
(§3.3). Tecnicamente isso significa que quase toda geração é *estruturada* e ancorada
em uma entidade (fato, tese, bloco de peça), não em uma conversa livre. O efeito
colateral é que o usuário perde a flexibilidade a que se acostumou em ferramentas
generalistas. A mitigação prevista é um **chat de caso com escopo restrito**, que
opera sobre as mesmas entidades e sob as mesmas invariantes, mas ele não substitui os
fluxos estruturados e não pode promover conteúdo para a base institucional.

**4.2 — Jurimetria no MVP é a parte mais frágil do plano, por dependência de dados.**
Toda a arquitetura de RAG e produção de peças depende apenas de documentos que o
escritório já possui. A jurimetria depende de **coleta externa**, cuja cobertura,
licença e qualidade não estão sob nosso controle. A recomendação técnica é tratar a
jurimetria como um **incremento separado, com critério de interrupção próprio**: se a
amostra validada manualmente não atingir os limiares de qualidade definidos em
[06 §7](06-jurimetria.md), a jurimetria sai do MVP sem que isso comprometa o restante.
Isso está refletido no sequenciamento de sprints.

**4.3 — Isolamento reforçado tem preço, e o preço deve entrar no modelo comercial.**
A proposta menciona "avaliação de isolamento reforçado quando o risco exigir"
(§10.1). Tecnicamente, o MVP usa multi-tenancy lógico (RLS + ABAC), que é adequado e
auditável. Escritórios que exijam instância dedicada — o que é previsível em contas
maiores — exigem topologia própria, custo de infraestrutura próprio e um plano de
release diferente. Isso é **decisão comercial**, não técnica, e deve ser precificada
antes do primeiro contrato enterprise. Ver [10 §6](10-infraestrutura-cicd-ambientes.md).

## 5. Números-chave

| Item | Valor | Origem |
|---|---|---|
| Duração do MVP controlado | 12 sprints de 2 semanas (~24 semanas) | [11](11-estimativa-esforco-e-sprints.md) |
| Time recomendado no MVP | 6 pessoas em tempo integral + 3 parciais | [11 §1](11-estimativa-esforco-e-sprints.md) |
| Esforço estimado do MVP | ~148 pessoa-semanas (faixa 125–180) | [11 §4](11-estimativa-esforco-e-sprints.md) |
| Infraestrutura no piloto | Faixa mensal estimada, sem inferência | [09 §5](09-observabilidade-custos-e-avaliacao.md) |
| Custo de inferência | Modelado por caso, não por assinatura | [09 §5](09-observabilidade-custos-e-avaliacao.md) |
| Épicos do backlog | E1–E14, herdados da proposta (Anexo B) | [11 §3](11-estimativa-esforco-e-sprints.md) |

As estimativas de custo são apresentadas como **modelo paramétrico com faixas**, não
como número fechado. Preços de inferência e de bases jurídicas licenciadas mudam por
contrato e por região; um número único aqui seria falsa precisão. O modelo permite
recalcular em minutos assim que os contratos forem assinados.

## 6. Matriz de rastreabilidade — requisitos funcionais

Todos os 30 requisitos funcionais da proposta (§9) têm componente responsável e
sprint de entrega. "MVP" indica que o requisito está no recorte controlado; "Fase 2"
indica produto operacional.

| RF | Requisito | Componente responsável | Recorte |
|---|---|---|---|
| RF-001 | Autenticar e segregar por organização | `identity` + Keycloak + RLS | MVP |
| RF-002 | Usuários, grupos, perfis, permissões granulares | `identity` + `authz` (ABAC) | MVP (parcial: 6 papéis fixos) |
| RF-003 | Criar, editar, arquivar e localizar casos | `matters` | MVP |
| RF-004 | Equipe, responsáveis, prazos, status, sigilo | `matters` | MVP |
| RF-005 | Upload individual e em lote com integridade e versão | `ingest` + object storage | MVP |
| RF-006 | Extrair texto, páginas e metadados com qualidade | `ingest.extract` + OCR | MVP |
| RF-007 | Detectar duplicados e conflitos | `ingest.dedupe` (hash + MinHash) | MVP |
| RF-008 | Classificar documentos com correção humana | `ingest.classify` (LLM + revisão) | MVP |
| RF-009 | Extrair entidades, fatos, datas, valores, pedidos | `analysis.extract` (structured output) | MVP |
| RF-010 | Vincular elemento estruturado a trecho documental | `evidence` (âncoras de span) | MVP |
| RF-011 | Cronologia editável com divergências | `analysis.timeline` | MVP |
| RF-012 | Identificar lacunas documentais | `analysis.gaps` | MVP |
| RF-013 | Busca semântica nos documentos do caso | `retrieval` | MVP |
| RF-014 | Busca em ativos internos e fontes externas | `retrieval` + `sources` | MVP (interno) / Fase 2 (externo) |
| RF-015 | Sugerir teses com requisitos, evidências, riscos | `theses.suggest` | MVP |
| RF-016 | Status, comentários, ressalvas, aprovação de teses | `theses.workflow` | MVP |
| RF-017 | Confronto de argumentos e objeções | `confrontation` | MVP |
| RF-018 | Minutas por blocos vinculados a fatos/teses/fontes | `drafting` | MVP |
| RF-019 | Versões, comparação, comentários, trilha | `drafting.versions` | MVP |
| RF-020 | Verificações automáticas de qualidade configuráveis | `quality` (regras + verificador) | MVP (regras fixas) |
| RF-021 | Bloquear/advertir exportação conforme política | `quality.gates` | MVP |
| RF-022 | Exportar minutas em formatos definidos | `export` (DOCX/PDF) | MVP |
| RF-023 | Promover conteúdo aprovado a ativo interno | `knowledge.promote` | MVP |
| RF-024 | Validade, escopo, sigilo e retirada de ativos | `knowledge.lifecycle` | MVP (parcial) |
| RF-025 | Consultas jurimétricas com metodologia visível | `jurimetrics.query` | MVP restrito |
| RF-026 | Acesso às decisões que sustentam indicadores | `jurimetrics.drilldown` | MVP restrito |
| RF-027 | Registrar eventos críticos | `audit` | MVP |
| RF-028 | Exibir modelo, fontes e resultado para auditoria | `audit` + `ai_runs` | MVP |
| RF-029 | Configurar modelos, prompts, taxonomias, checklists | `admin.config` | Fase 2 (MVP: versionado em código) |
| RF-030 | Métricas operacionais, de qualidade e adoção | `analytics` | MVP (parcial) |

## 7. Matriz de rastreabilidade — critérios de aceite

Cada critério de aceite da proposta (Anexo C) tem um **mecanismo de imposição** e um
**teste**. Critério sem mecanismo é intenção; critério com mecanismo é engenharia.

| CA | Critério | Mecanismo de imposição | Verificação |
|---|---|---|---|
| CA-001 | Fonte obrigatória | Schema de saída exige `evidence_refs` não vazio ou `status="hipotese_nao_validada"` | Teste de contrato + métrica de atribuição |
| CA-002 | Abstenção | Sentinela de insuficiência no schema; verificador rejeita afirmação sem suporte | Conjunto de avaliação com perguntas sem resposta na base |
| CA-003 | Segregação | Filtro de autorização pré-busca + RLS + chave de tenant no índice | Suíte adversarial cross-tenant (bloqueia o build) |
| CA-004 | Rastreabilidade | Âncoras `document_id + page + char_span` persistidas por chunk e propagadas ao bloco | Teste E2E: clicar na afirmação abre o trecho correto |
| CA-005 | Aprovação | Máquina de estados server-side impede tese `rejeitada` em bloco de minuta | Teste de máquina de estados |
| CA-006 | Versão | Versionamento imutável com `author_id`, `created_at`, `parent_version_id` | Teste de integridade referencial |
| CA-007 | Exportação | Gate de qualidade bloqueia transição para `pronta_para_protocolo` | Teste de gate + auditoria da transição |
| CA-008 | Jurimetria transparente | Toda resposta de indicador inclui envelope de metodologia obrigatório no schema | Teste de contrato de API |
| CA-009 | Reprodutibilidade | Consulta versionada com `dataset_version_id` + hash de parâmetros | Teste de reexecução determinística |
| CA-010 | Correção humana | Grafo de dependências fato → tese → bloco; alteração propaga sinalização | Teste de propagação de impacto |
| CA-011 | Auditoria | Eventos emitidos na mesma transação da mutação | Teste de cobertura de eventos por endpoint crítico |
| CA-012 | Falha parcial | Estado por documento; agregação nunca reporta sucesso total com falha parcial | Teste de ingestão com arquivo corrompido |

## 8. O que esta especificação não resolve

Honestidade sobre limites é requisito do próprio produto; vale para o documento
também.

- **Cobertura e licença das fontes jurídicas externas.** Depende de contrato e de
  parecer jurídico. A arquitetura acomoda várias fontes; a viabilidade de cada uma não
  é decisão de engenharia.
- **Qualidade real do dado jurimétrico no recorte escolhido.** Só é conhecida após a
  coleta e validação manual da amostra. Por isso há critério de interrupção.
- **Preço final de inferência e de infraestrutura.** Modelado, não fechado.
- **Desempenho de OCR sobre o acervo real do escritório.** Depende da qualidade dos
  digitalizados. A prova técnica da Sprint 0 mede isso antes de comprometer prazos.
- **Adequação do recorte de peça escolhido.** É decisão de produto e do escritório
  design partner, informada pelo baseline (§14.1 da proposta).

---

**Próximo documento**: [01 — Arquitetura de referência](01-arquitetura-de-referencia.md)
