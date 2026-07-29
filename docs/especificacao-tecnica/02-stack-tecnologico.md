# 02 — Stack tecnológico

## 1. Critérios de escolha

Toda escolha abaixo foi avaliada contra cinco critérios, nesta ordem de prioridade —
que não é arbitrária: reflete o que a proposta identifica como risco maior
(vazamento e alucinação) versus preferência de equipe.

1. **Capacidade de impor as invariantes** ([00 §2](00-sumario-executivo.md)). Uma
   tecnologia que dificulte a segregação de dados é descartada mesmo se for superior
   em outros aspectos.
2. **Portabilidade** — §10.3 e §16.1 tratam lock-in como risco explícito.
3. **Maturidade operacional** — um time pequeno não pode gastar sprints depurando
   infraestrutura exótica.
4. **Disponibilidade de profissionais no mercado brasileiro** — o projeto precisa
   contratar.
5. **Custo total**, incluindo operação e não apenas licença.

## 2. Stack por camada

| Camada | Escolha | Versão-alvo | Alternativa considerada | Por que não a alternativa |
|---|---|---|---|---|
| Frontend | Next.js (App Router) + TypeScript | 15.x / TS 5.x | Remix, SPA + Vite | Streaming de servidor e RSC importam para exibir geração incremental; ecossistema maior facilita contratação |
| UI | Tailwind CSS + Radix UI (headless) | — | Component library pronta | Radix entrega acessibilidade real (foco, teclado, ARIA) sem impor estética; §10.4 é requisito, não enfeite |
| Editor de peças | TipTap (ProseMirror) | 2.x | Slate, Lexical | Precisamos de marcas customizadas persistentes que carreguem `evidence_ref`; o modelo de documento do ProseMirror suporta isso com garantias de integridade |
| Estado do cliente | TanStack Query + Zustand | — | Redux Toolkit | Quase todo estado é servidor; cache de servidor resolve 90 % do problema |
| Backend | Python 3.12 + FastAPI | — | Node/NestJS, Go, Java/Spring | Todo o ferramental de documentos, avaliação de RAG e ciência de dados vive em Python; usar outra linguagem obrigaria a um segundo runtime só para IA |
| ORM / migrações | SQLAlchemy 2 + Alembic | — | Django ORM, Prisma | Precisamos de SQL explícito para busca híbrida e de controle fino de sessão para setar o contexto de RLS |
| Validação e contratos | Pydantic v2 | — | dataclasses + jsonschema | Os schemas de saída da LLM e os contratos de API compartilham as mesmas definições |
| Fila | Celery + Redis | — | RQ, Dramatiq, SQS | Maturidade em jobs longos, encadeamento, retries e visibilidade operacional |
| Banco | PostgreSQL 16 + `pgvector`, `pg_trgm`, `unaccent` | pgvector 0.8+ | Vector DB dedicado | [ADR-0001](../adr/0001-postgres-pgvector-como-banco-vetorial.md) |
| Analítico | Schema separado no mesmo Postgres + dbt | — | Warehouse dedicado | Volume do MVP não justifica warehouse; dbt dá versionamento e testes desde o dia um |
| Object storage | S3-compatível com SSE-KMS e Object Lock | — | Disco em volume | Object Lock é o que viabiliza a trilha WORM exigida pela auditoria |
| Identidade | Keycloak (OIDC/SAML) | 26.x | Auth0, Clerk, WorkOS | [ADR-0008](../adr/0008-identidade-com-keycloak-oidc.md) |
| Gateway de modelos | Serviço próprio, fino | — | LiteLLM, LangChain | [ADR-0004](../adr/0004-gateway-de-modelos-e-portabilidade.md) |
| Observabilidade de LLM | Langfuse autogerenciado | — | LangSmith, SaaS equivalente | Traces contêm conteúdo de casos; precisam ficar dentro do nosso perímetro |
| Telemetria | OpenTelemetry + Prometheus + Grafana + Loki | — | APM proprietário | Portabilidade e custo |
| IaC | Terraform + Helm | — | CDK, Pulumi | Neutralidade de provedor, que é a própria política de portabilidade |
| CI/CD | GitHub Actions | — | GitLab CI | Já é onde o código vive |
| Testes | pytest, Playwright, Vitest, Locust | — | — | — |

## 3. Sobre orquestração de LLM: por que não um framework

A tentação em projetos de RAG é adotar um framework de orquestração completo. A
decisão aqui é **não adotar** e escrever a orquestração explicitamente, por três
razões concretas ao PROJUR:

1. **A autorização precisa ser inspecionável.** Nossa etapa de filtro pré-busca é o
   ponto onde a invariante I-1 é imposta. Ela precisa ser código legível por um
   auditor de segurança, não configuração de um pipeline genérico.
2. **A atribuição é o produto.** O rastreamento de `evidence_refs` desde o chunk até o
   parágrafo exportado é a funcionalidade central. Frameworks tratam citação como
   recurso opcional; aqui ela é o invariante.
3. **Superfície de dependência.** Frameworks de orquestração evoluem rápido e trazem
   árvores de dependência grandes — atrito direto com revisão de dependências exigida
   em §10.1.

Bibliotecas pontuais e substituíveis continuam bem-vindas: parsing de documentos,
avaliação, clientes de provedores. A recusa é ao framework que assume o controle do
fluxo.

## 4. Processamento de documentos

O acervo de um escritório é heterogêneo: PDFs nativos, digitalizações antigas,
`.docx`, planilhas, mensagens exportadas, imagens. A cascata abaixo é a política de
extração.

| Situação | Ferramenta | Observação |
|---|---|---|
| PDF com camada de texto | PyMuPDF | Preserva coordenadas por bloco — essencial para âncoras de destaque |
| PDF sem camada de texto | OCRmyPDF + Tesseract (por-BR) | Gera PDF pesquisável **e** preserva o original imutável |
| PDF com estrutura complexa (tabelas, colunas) | Docling ou `unstructured` | Avaliar na prova técnica da Sprint 0 com documentos reais |
| `.docx` / `.odt` | python-docx / odfpy | Extrai estrutura de títulos, útil para chunking estrutural |
| Planilhas | openpyxl / pandas | Vira texto tabular normalizado com referência de célula |
| Imagens soltas | Tesseract | Marcadas com confiança baixa por padrão |
| E-mails / mensagens | mailparser + normalizador próprio | Fio de conversa vira documento único com participantes e datas |

**Regra invariável**: o arquivo original nunca é modificado nem substituído. Todo
derivado (texto, PDF com OCR, thumbnails) é armazenado ao lado, referenciando o hash
do original. Isso sustenta CA-004 e a integridade probatória do acervo.

**Sobre serviços gerenciados de Document AI**: são mais precisos em documentos ruins,
e mais caros e mais invasivos em privacidade, porque enviam o documento inteiro para
fora. A política é: OCR local por padrão; serviço externo só mediante autorização
explícita da organização, registrada por documento e auditada. A decisão fica
configurável por organização em vez de imposta pelo produto.

## 5. Modelos de linguagem e embeddings

### 5.1 Roteamento por tier

O gateway expõe **tiers lógicos**, não nomes de modelo. Código de domínio pede
`tier="extraction"`; o mapeamento tier → modelo vive em configuração versionada. É o
que torna a troca de fornecedor uma mudança de configuração e não uma refatoração.

| Tier lógico | Uso | Perfil de modelo | Sensibilidade a custo |
|---|---|---|---|
| `classification` | Tipo documental, roteamento, triagem | Pequeno e rápido | Altíssima — alto volume |
| `extraction` | Entidades, fatos, datas, valores | Médio, com saída estruturada confiável | Alta |
| `generation` | Blocos de peça, sumarização, explicação | Médio-alto, boa redação em pt-BR jurídico | Média |
| `reasoning` | Sugestão e confronto de teses | Alto, raciocínio longo | Baixa — poucas chamadas, alto valor |
| `verification` | Verificação de suporte afirmação↔evidência | Médio, calibrado para julgamento binário | Alta — roda em cada afirmação |

Famílias candidatas para cada tier: modelos comerciais de fronteira (Anthropic,
OpenAI, Google) e modelos abertos hospedados em nosso perímetro (família Llama,
Qwen, Mistral) para os tiers de alto volume, onde o ganho de custo e de privacidade é
maior e a dificuldade da tarefa é menor. A escolha final por tier sai do *bake-off* da
Sprint 0 ([09 §4](09-observabilidade-custos-e-avaliacao.md)), medida contra o conjunto
de avaliação, não por impressão.

### 5.2 Embeddings

| Requisito | Decisão |
|---|---|
| Idioma | Multilíngue com desempenho verificado em pt-BR jurídico |
| Candidatos | BGE-M3 (aberto, autogerenciado, denso + esparso) vs. embeddings comerciais de ponta |
| Recomendação inicial | **BGE-M3 autogerenciado**, sujeito a validação no bake-off |
| Dimensão | 1024 |
| Versionamento | `embedding_model_id` e `embedding_version` gravados em **cada** chunk |
| Reindexação | Job de reindexação incremental sem downtime, com índice sombra |

A recomendação por modelo aberto autogerenciado nos embeddings tem uma razão que não
vale para a geração: embeddings processam **todo** o acervo — inclusive documentos
sigilosos que jamais precisariam sair do perímetro — e o volume é ordens de grandeza
maior que o de geração. É onde privacidade e custo apontam na mesma direção.

Gravar a versão do modelo em cada chunk parece detalhe e não é: sem isso, trocar de
modelo de embedding significa reindexar tudo de uma vez, com downtime, ou conviver com
um índice silenciosamente inconsistente — vetores de espaços diferentes comparados
entre si, produzindo recuperação ruim sem erro visível.

### 5.3 Reranking

Cross-encoder autogerenciado (família BGE-reranker ou equivalente), pelos mesmos
motivos de privacidade: o reranker vê o conteúdo dos trechos candidatos do caso.
Serviços comerciais de rerank ficam disponíveis no gateway como alternativa, sujeitos
à política de saída de conteúdo.

## 6. Organização do repositório

```
projur/
├── apps/
│   ├── web/                  # Next.js
│   └── api/                  # FastAPI + workers Celery
├── packages/
│   ├── contracts/            # OpenAPI + tipos TS gerados; fonte única
│   ├── ui/                   # design system
│   └── eval/                 # datasets e harness de avaliação de IA
├── services/
│   ├── llm-gateway/
│   ├── embeddings/
│   └── reranker/
├── data/
│   ├── jurimetrics_dbt/      # transformações versionadas
│   └── collectors/           # coletores por fonte
├── infra/
│   ├── terraform/
│   └── helm/
├── docs/
│   ├── especificacao-tecnica/
│   ├── adr/
│   └── runbooks/
└── .github/workflows/
```

Monorepo com pnpm workspaces + Turborepo no lado JS e uv no lado Python. A razão é
o pacote `contracts`: tipos de API gerados a partir do OpenAPI do backend e consumidos
pelo frontend, com verificação de compatibilidade no CI. Contrato divergente entre
front e back é uma classe inteira de bug que desaparece.

## 7. Padrões de engenharia

| Prática | Regra |
|---|---|
| Estilo | `ruff` (Python), `eslint` + `prettier` (TS); formatação não é discussão de PR |
| Tipagem | `mypy --strict` no domínio; TS `strict` |
| Migrações | Alembic, sempre reversíveis; migração destrutiva exige duas etapas e aprovação |
| Testes | Unitário no domínio; integração com Postgres real via Testcontainers; E2E Playwright nos fluxos críticos |
| Cobertura | Limiar por módulo, mais alto em `authz`, `retrieval`, `quality`, `audit` |
| Segredos | Nunca em código ou `.env` versionado; Secrets Manager + injeção em runtime |
| Dependências | Renovate + verificação de vulnerabilidades bloqueando o merge em severidade alta |
| Commits | Conventional Commits; PR exige revisão humana e CI verde |
| Documentação | ADR obrigatório para decisão estrutural; runbook obrigatório para todo alerta |

## 8. Definition of Done técnica

Complementa a DoD ampliada da proposta (§15.3), traduzindo cada item em verificação
executável.

- [ ] Testes unitários e de integração passando; cobertura acima do limiar do módulo
- [ ] Autorização verificada por teste, incluindo caso negativo cross-tenant
- [ ] Eventos de auditoria emitidos e cobertos por teste, quando a mudança toca ação crítica
- [ ] Métricas e traces instrumentados; painel atualizado se houver novo indicador
- [ ] Avaliação de RAG/IA executada quando a mudança toca prompt, recuperação, modelo ou verificador
- [ ] Estados de carregando, vazio, erro, parcial, incerto e abstenção implementados
- [ ] Acessibilidade verificada (teclado, foco, contraste, leitor de tela) no escopo
- [ ] Migração reversível e testada em ambiente de homologação
- [ ] Runbook atualizado se houver novo modo de falha
- [ ] Especialista jurídico validou textos de alertas críticos e rótulos epistêmicos

---

**Anterior**: [01 — Arquitetura](01-arquitetura-de-referencia.md) · **Próximo**: [03 — Modelo de dados](03-modelo-de-dados.md)
