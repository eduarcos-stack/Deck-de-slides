# PROJUR — Especificação Técnica

Repositório da documentação de engenharia do **PROJUR**, plataforma web de produção
jurídica assistida por IA, RAG e jurimetria.

Este repositório contém a **Especificação Técnica v1.0**, produzida a partir da
*Proposta Inicial de Produto v0.1* (28/07/2026) e destinada a responder ao entregável
descrito na seção 17.2 daquele documento: arquitetura de referência, decisões
tecnológicas registradas, modelo de dados, estratégia de segregação e auditoria,
componentes do RAG, pipeline jurimétrico, requisitos de segurança, plano de avaliação
da IA, estimativa de esforço, divisão por sprints, riscos técnicos, custo operacional
estimado e estratégia de MVP.

## Como ler

| Se você é | Comece por |
|---|---|
| Sponsor / gestor | [00 — Sumário executivo](docs/especificacao-tecnica/00-sumario-executivo.md) e [13 — Estratégia de MVP](docs/especificacao-tecnica/13-estrategia-de-mvp.md) |
| Arquiteto / tech lead | [01 — Arquitetura](docs/especificacao-tecnica/01-arquitetura-de-referencia.md) e os [ADRs](docs/adr/) |
| Engenheiro de IA | [04 — Pipeline RAG](docs/especificacao-tecnica/04-pipeline-rag.md) e [05 — Guardrails](docs/especificacao-tecnica/05-comportamento-da-ia-e-guardrails.md) |
| Backend / frontend | [02 — Stack](docs/especificacao-tecnica/02-stack-tecnologico.md) e [03 — Modelo de dados](docs/especificacao-tecnica/03-modelo-de-dados.md) |
| Segurança / DPO | [07 — Segurança e privacidade](docs/especificacao-tecnica/07-seguranca-e-privacidade.md) |
| Dados / jurimetria | [06 — Jurimetria](docs/especificacao-tecnica/06-jurimetria.md) |
| Product / planejamento | [11 — Esforço e sprints](docs/especificacao-tecnica/11-estimativa-esforco-e-sprints.md) |

## Índice

| # | Documento | Conteúdo |
|---|---|---|
| 00 | [Sumário executivo](docs/especificacao-tecnica/00-sumario-executivo.md) | Decisões estruturantes, o que muda em relação à v0.1, matriz de rastreabilidade |
| 01 | [Arquitetura de referência](docs/especificacao-tecnica/01-arquitetura-de-referencia.md) | Contexto, contêineres, componentes, fluxos síncronos e assíncronos |
| 02 | [Stack tecnológico](docs/especificacao-tecnica/02-stack-tecnologico.md) | Linguagens, frameworks, bibliotecas e critérios de escolha |
| 03 | [Modelo de dados](docs/especificacao-tecnica/03-modelo-de-dados.md) | Entidades, DDL essencial, RLS, versionamento e estados |
| 04 | [Pipeline RAG](docs/especificacao-tecnica/04-pipeline-rag.md) | Ingestão, OCR, chunking, embeddings, busca híbrida, reranking, atribuição |
| 05 | [Comportamento da IA e guardrails](docs/especificacao-tecnica/05-comportamento-da-ia-e-guardrails.md) | Contratos de saída, abstenção, verificação de suporte, prompt injection |
| 06 | [Jurimetria](docs/especificacao-tecnica/06-jurimetria.md) | Coleta, tratamento, classificação, camada analítica, reprodutibilidade |
| 07 | [Segurança e privacidade](docs/especificacao-tecnica/07-seguranca-e-privacidade.md) | Threat model, autorização, criptografia, LGPD, auditoria |
| 08 | [Integrações](docs/especificacao-tecnica/08-integracoes.md) | Fontes jurídicas, storage, identidade, assinatura, e-mail e calendário |
| 09 | [Observabilidade, custos e avaliação](docs/especificacao-tecnica/09-observabilidade-custos-e-avaliacao.md) | Telemetria, avaliação de RAG em CI, modelo de custo de inferência |
| 10 | [Infraestrutura, CI/CD e ambientes](docs/especificacao-tecnica/10-infraestrutura-cicd-ambientes.md) | Topologia de nuvem, IaC, pipelines, backup e DR |
| 11 | [Estimativa de esforço e sprints](docs/especificacao-tecnica/11-estimativa-esforco-e-sprints.md) | Time, épicos, sequenciamento, incrementos verticais |
| 12 | [Riscos técnicos](docs/especificacao-tecnica/12-riscos-tecnicos.md) | Riscos, gatilhos, mitigação e planos de contingência |
| 13 | [Estratégia de MVP](docs/especificacao-tecnica/13-estrategia-de-mvp.md) | Recorte, critérios de saída, o que fica fora e por quê |

### Decisões arquiteturais (ADR)

| ADR | Decisão |
|---|---|
| [0001](docs/adr/0001-postgres-pgvector-como-banco-vetorial.md) | PostgreSQL + pgvector como banco vetorial, em vez de vector DB dedicado |
| [0002](docs/adr/0002-monorepo-next-e-fastapi.md) | Monorepo com Next.js (web) e FastAPI/Python (API e workers) |
| [0003](docs/adr/0003-isolamento-multitenant-em-duas-camadas.md) | Isolamento multi-tenant em duas camadas: ABAC na aplicação + RLS no banco |
| [0004](docs/adr/0004-gateway-de-modelos-e-portabilidade.md) | Gateway de modelos próprio para evitar dependência de fornecedor |
| [0005](docs/adr/0005-busca-hibrida-rrf-e-reranking.md) | Busca híbrida (denso + léxico) com fusão RRF e reranker cross-encoder |
| [0006](docs/adr/0006-camada-analitica-separada-da-llm.md) | Cálculo jurimétrico em camada analítica SQL, isolada da LLM |
| [0007](docs/adr/0007-auditoria-append-only-com-encadeamento-de-hash.md) | Trilha de auditoria append-only com encadeamento de hash |
| [0008](docs/adr/0008-identidade-com-keycloak-oidc.md) | Identidade com Keycloak (OIDC) autogerenciado |

## Status

| Campo | Valor |
|---|---|
| Versão | 1.0 |
| Data | 29 de julho de 2026 |
| Documento de origem | PROJUR — Proposta Inicial de Produto v0.1 (28/07/2026) |
| Status | Especificação técnica para revisão de arquitetura, segurança e planejamento |
| Natureza | Decisões técnicas assumidas e justificadas; dependem de validação em discovery, de contratos com fornecedores e de parecer jurídico sobre fontes e dados |
| Confidencialidade | Uso interno e compartilhamento restrito à equipe do projeto |
