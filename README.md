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

> **Demonstração §89-90:** o EDA encontra um "pico 00h-02h" que, sob a Pattern Stability
> e o Adversarial Auditor, se revela **não robusto** — dependia de um parser que colapsa
> `24:00` para meia-noite. Reproduza nas abas EXPLORE → FINDINGS.
>
> **Demonstração §57-59:** um achado depende de um merge de entidade; reverter o merge
> (aba AUDIT) marca o achado como `STALE_REQUIRES_RECOMPUTATION` automaticamente. O diário
> não é apagado (§36) — a reversão registra uma transformação inversa.

O esqueleto de governança (Diário de Transformação §35, Provenance Graph §34,
status epistemológicos §9) já está no código, pronto para as próximas capacidades.

---

## Arquitetura (subconjunto do §54, local-first)

```
Frontend (React/Vite)  ──/api──▶  Backend (FastAPI)
  CASE · DATA · QUALITY              ├── modules/ingestion         (§10)
  TRANSFORM · ENTITIES              ├── modules/raw_vault         (§11, P1)
  EXPLORE · FINDINGS · AUDIT         ├── modules/profiling         (§12)
                                     ├── modules/rules             (§52)
                                     ├── modules/normalization     (§16-17)
                                     ├── modules/deduplication     (§20)
                                     ├── modules/entity_resolution (§22-27)
                                     ├── modules/temporal          (§18-19)
                                     ├── modules/eda               (§28-33)
                                     ├── modules/adversarial       (§41-42)
                                     ├── modules/rollback          (§57-59)
                                     └── governance/               (§34, §35, §45)
                                          │
                                   SQLite + Raw Vault (disco local)
```

**Zero exfiltration por padrão (§47):** nenhuma dependência de API externa. Os
dados de caso vivem apenas em `backend/data/` (não versionado).

---

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

Fora do escopo do MVP (roadmap): Temporal Engine completo, EDA/anomaly detection,
Adversarial Auditor, RAG, orquestração LLM, sandbox de execução, criptografia at-rest/RBAC.

---

## Aviso

Ferramenta de **preparação e análise de dados**. Não determina autoria,
culpabilidade ou tipificação penal (§91). Todos os dados de exemplo são fictícios.
