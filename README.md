# TRACE-LM

**Transformação Rastreável e Análise Confiável de Evidências**
Plataforma **local-first** de IA para preparação, resolução, análise e auditoria de dados investigativos.

> *AI-assisted · human-controlled · provenance-first*

Este repositório implementa o **MVP** definido no [Blueprint Mestre](docs/TRACELM_Blueprint_Mestre.md) (§81): as sete capacidades fundamentais, com viés didático/acadêmico e fidelidade aos princípios epistemológicos do documento.

---

## Estado atual — MVP completo (7/7) + roadmap M4

**MVP (§81):**

| # | Capacidade | Blueprint | Status |
|---|---|---|---|
| 1 | Ingestão (CSV/TSV/JSON/JSONL/XLSX) | §10 | ✅ M1 |
| 2 | Raw preservation (vault imutável, hash, read-only) | §11, P1 | ✅ M1 |
| 3 | Profiling (estrutura, missingness, formatos, chaves, duplicidade) | §12–13 | ✅ M1 |
| 4 | Normalização versionada (preview + aprovação, regras com ID+versão) | §16–17, §52 | ✅ M2 |
| 5 | Deduplicação por unidade de evento | §20–21 | ✅ M2 |
| 6 | Entity Resolution assistida + Impact Analysis | §22–27 | ✅ M3 |
| 7 | Lineage / Provenance ("Como chegamos aqui?") | §34–35, §45 | ✅ M3 |

**Roadmap M4 (além do MVP):**

| Módulo | Blueprint | Status |
|---|---|---|
| Temporal Engine (parsing, qualidade temporal, guardrail P6) | §18–19 | ✅ M4 |
| EDA + Finding Registry (histogramas, outliers, Pattern Provenance/Stability) | §28–33, §76 | ✅ M4 |
| Adversarial Auditor ("como isso poderia estar errado?", SUPPORT×CHALLENGE) | §41–42 | ✅ M4 |
| Rollback + Dependency Graph + Invalidação Automática | §57–59, P10 | ✅ M5 |
| Pacote de Entregáveis (16 itens, relatório, ZIP, Provenance Completeness) | §60–61, §63 | ✅ M6 |
| Segurança — login obrigatório, RBAC, MFA/TOTP, segregação por caso, audit log | §48 | ✅ M7 |
| Integridade da trilha — hash-chain + selo HMAC no Diário e no audit log | §36 | ✅ M8 |
| LLM Orchestrator + RAG local (model-agnostic, prompt constitucional, papéis) | §37–40, §49–51 | ✅ M9 |
| Métricas formais de validação (ER, dedup, reprodutibilidade, avaliação do LLM) | §62–67 | ✅ M10 |
| Execution Sandbox (inspeção estática → sandbox → dataset de teste → diff) | §53 | ✅ M11 |
| Missing Data Semantic Analyzer (sentinelas por campo, confirmação humana → ER) | §15 | ✅ M12 |
| Quality Analyzer (7 dimensões; distingue erro provável de divergência legítima) | §14 | ✅ M13 |
| Tiers de modelo (workstation/servidor, roteamento por papel, model-agnostic) | §50 | ✅ M14 |

> **Demonstração §89-90:** o EDA encontra um "pico 00h-02h" que, sob a Pattern Stability
> e o Adversarial Auditor, se revela **não robusto** — dependia de um parser que colapsa
> `24:00` para meia-noite. Reproduza nas abas EXPLORE → FINDINGS.
>
> **Demonstração §57-59:** um achado depende de um merge de entidade; reverter o merge
> (aba AUDIT) marca o achado como `STALE_REQUIRES_RECOMPUTATION` automaticamente. O diário
> não é apagado (§36) — a reversão registra uma transformação inversa.
>
> **Demonstração §36:** cada entrada do Diário e do log de acesso é encadeada por hash e
> selada com HMAC. Adulterar, remover ou reordenar qualquer entrada (mesmo direto no SQLite)
> é detectado por `GET /integrity/verify` — aba AUDIT → "Verificar integridade".
>
> **Demonstração §92 (aba ASSISTANT):** à pergunta "quantas transações Carlos realizou?",
> o assistente responde como o TRACE-LM, não como um "chat com planilha": *N linhas nominais
> → M eventos candidatos → ≥2 homônimos → atribuição a uma pessoa única não suportada*,
> com guardrails e plano de ferramentas rastreável.

## Camada de IA (§37–40, §49–51)

O **LLM Orchestrator** interpreta, planeja, explica e coordena ferramentas — **mas não é
motor de execução** (§4): quem calcula são os motores determinísticos. A arquitetura é
**model-agnostic** (§50) — a composição da resposta passa por um `LLMProvider` plugável.

> ⚠️ O provider **padrão é local e determinístico** (sem pesos de modelo, sem rede — §47).
> É o esqueleto do §49 ("open-weight + RAG + tool calling + políticas") com um *seam* pronto
> para plugar um modelo open-weight local, sem reescrever a plataforma. Não há LLM neural
> embutido neste repositório; `TRACELM_LLM_PROVIDER` seleciona o provider.

O **RAG local** (§51) recupera conhecimento de domínio (`backend/kb/*.md`) por TF-IDF em
Python puro — sem embeddings externos. Ele fornece conhecimento de método, **não substitui
os dados do caso**.

O esqueleto de governança (Diário de Transformação §35, Provenance Graph §34,
status epistemológicos §9) já está no código, pronto para as próximas capacidades.

---

## Arquitetura (subconjunto do §54, local-first)

```
Frontend (React/Vite)  ──/api──▶  Backend (FastAPI)
  CASE · DATA · QUALITY              ├── modules/ingestion         (§10)
  TRANSFORM · ENTITIES              ├── modules/raw_vault         (§11, P1)
  EXPLORE · FINDINGS                 ├── modules/profiling         (§12)
  AUDIT · EXPORT
                                     ├── modules/rules             (§52)
                                     ├── modules/normalization     (§16-17)
                                     ├── modules/deduplication     (§20)
                                     ├── modules/entity_resolution (§22-27)
                                     ├── modules/temporal          (§18-19)
                                     ├── modules/eda               (§28-33)
                                     ├── modules/adversarial       (§41-42)
                                     ├── modules/rollback          (§57-59)
                                     ├── modules/export            (§60-61, §63)
                                     ├── modules/auth              (§48 — RBAC/MFA)
                                     ├── core/security · authmw    (§48)
                                     ├── core/integrity            (§36 — hash-chain)
                                     ├── modules/rag               (§51 — RAG local)
                                     ├── modules/orchestrator      (§37-40 — LLM)
                                     ├── modules/metrics           (§62-67 — validação)
                                     ├── modules/sandbox           (§53 — execução isolada)
                                     ├── modules/missing           (§15 — missing semântico)
                                     ├── modules/quality           (§14 — quality analyzer)
                                     └── governance/               (§34, §35, §45)
                                          │
                                   SQLite + Raw Vault (disco local)
```

**Zero exfiltration por padrão (§47):** nenhuma dependência de API externa. Os
dados de caso vivem apenas em `backend/data/` (não versionado).

---

## Segurança (§48)

Login é obrigatório em todas as rotas (exceto `/health` e `/auth/login*`). Papéis:
**admin** (acesso total + gestão de usuários), **investigator** (ingere/transforma/
decide/reverte/exporta nos seus casos) e **viewer** (somente leitura). Há segregação
por caso, MFA opcional por TOTP, session timeout e log de acesso append-only.

> ⚠️ **Credenciais padrão são apenas para o demo local.** Na primeira execução o
> sistema semeia `admin`, `arcos` (investigator) e `promotor` (viewer) com senhas
> padrão. **Antes de qualquer uso real, defina senhas por variável de ambiente e
> ative o MFA.**

Variáveis de ambiente relevantes:

```bash
TRACELM_SECRET=<segredo-forte>          # chave de assinatura dos tokens (senão gera local)
TRACELM_ADMIN_PASSWORD=<senha>          # senha do admin no seed
TRACELM_INVESTIGATOR_PASSWORD=<senha>
TRACELM_VIEWER_PASSWORD=<senha>
TRACELM_SESSION_TTL=28800               # timeout de sessão em segundos (default 8h)
```

## Como executar

### Backend
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. uvicorn app.main:app --reload    # http://127.0.0.1:8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev                                    # http://127.0.0.1:5173
```

### Testes
```bash
cd backend && source .venv/bin/activate
PYTHONPATH=. pytest -q
```

### Deploy — demo público (Supabase Auth + FastAPI)
Para colocar o MVP no ar (Supabase como Auth gerenciado, FastAPI no Fly.io/Render
e o frontend no Vercel/Netlify), com **apenas dados sintéticos**, veja
[docs/DEPLOY.md](docs/DEPLOY.md). O login usa o SDK do Supabase; o FastAPI valida
o JWT e emite a sessão TRACE-LM, preservando RBAC, segregação e audit log (§48).

### Dataset demonstrador (Illicit Matrix — §82)
```bash
python3 datasets/illicit_matrix/generate.py    # gera 72 registros + ground truth
```
Ingerir `datasets/illicit_matrix/illicit_matrix.csv` pela aba CASE para reproduzir
o caso de aula: dois "Carlos" homônimos com CPF/nascimento conflitantes, duplicatas
técnicas, eventos repetidos legítimos, missingness ambíguo e anomalias temporais.

---

## Princípios inegociáveis (materializados em código)

- **P1 — Raw Immutability:** o raw nunca é sobrescrito (teste de aceite em `tests/`).
- **P2 — Derived Data Separation:** `cpf_raw` ≠ `cpf_norm`.
- **P3 / P8 — Uncertainty Preservation / No Silent Inference:** status epistemológicos
  explícitos; nenhuma promoção automática de hipótese a fato.
- **P7 — Provenance by Default:** toda transformação relevante gera registro de lineage.
- **P9 — Human Authority:** decisões de alto impacto exigem aprovação humana (M3).

Cobertura do blueprint: MVP (§81) + todos os módulos do roadmap conceitual estão
implementados (M4–M14). O que permanece fora é estritamente de **infraestrutura/deploy**,
não de código de aplicação: TLS interno, criptografia de disco at-rest e MFA por
hardware. O restante do §48 (RBAC, MFA/TOTP, segregação, audit log, secrets) está
implementado.

---

## Aviso

Ferramenta de **preparação e análise de dados**. Não determina autoria,
culpabilidade ou tipificação penal (§91). Todos os dados de exemplo são fictícios.
