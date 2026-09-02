# TRACE-LM
## Blueprint Mestre — Transformação Rastreável e Análise Confiável de Evidências

**Categoria:** plataforma local de IA para preparação, resolução, análise e auditoria de dados investigativos.  
**Princípio:** *AI-assisted, human-controlled, provenance-first.*

---

# 1. Visão do Produto

## 1.1 Problema central

Investigações contemporâneas recebem dados oriundos de múltiplas fontes: bases bancárias, dados cadastrais, registros de operadoras, logs, arquivos CSV/XLSX, JSON, sistemas corporativos, documentos, dados OSINT, metadados, relatórios e dados produzidos por ferramentas forenses.

Esses dados frequentemente apresentam inconsistências, formatos diferentes, duplicação, campos ausentes, ambiguidades, identificadores incompletos, timestamps incompatíveis, entidades homônimas, erros de cadastro e diferentes níveis de confiabilidade.

O risco não é apenas obter uma análise ruim. O risco mais grave é:

> **A própria preparação dos dados introduzir uma relação, entidade, evento ou padrão que não existia no fenômeno investigado.**

---

# 2. Missão do Sistema

O TRACE-LM deverá:

> **Transformar dados investigativos heterogêneos em bases analíticas tecnicamente utilizáveis, preservando o dado originário, explicitando as decisões de tratamento, representando a incerteza e permitindo reconstruir integralmente o caminho entre qualquer achado e sua fonte.**

O sistema não será concebido para responder “quem é o culpado?”. Sua pergunta central será:

> **“Que transformações são necessárias para analisar estes dados sem alterar indevidamente aquilo que eles representam?”**

---

# 3. Princípio Epistemológico Central

A plataforma deve materializar tecnicamente esta regra:

> **Nenhuma transformação relevante pode converter silenciosamente uma hipótese em fato.**

Isso significa, entre outros controles:

- nomes semelhantes não viram automaticamente a mesma pessoa;
- registros semelhantes não viram automaticamente o mesmo evento;
- `NULL` não vira automaticamente zero;
- horário sem timezone não vira automaticamente UTC;
- outlier não vira automaticamente comportamento ilícito;
- correlação não vira automaticamente causalidade;
- ausência de registro não vira automaticamente inexistência de fato.

---

# 4. O TRACE-LM não é apenas um LLM

Sua arquitetura deverá conter quatro camadas principais:

1. **LLM** — interpretação, planejamento, interação e explicação.
2. **Motores determinísticos** — normalização, parsing, validação, consultas, cálculos e transformações reproduzíveis.
3. **Motores probabilísticos/estatísticos** — Entity Resolution, similarity matching, anomaly detection e outros procedimentos quantitativos.
4. **Governança** — provenance, lineage, revisão humana, versionamento, auditoria e controle de acesso.

Portanto:

> **LLM ≠ motor de execução.**

O LLM deverá dizer **o que pretende fazer e por quê**. Um serviço especializado efetivamente executará a operação.

---

# 5. Arquitetura Conceitual

```text
                      USUÁRIO
                         │
                         ▼
               INTERFACE INVESTIGATIVA
                         │
                         ▼
                  ORQUESTRADOR LLM
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
        POLICY ENGINE  TOOL ROUTER  RAG LOCAL
              │          │
              │          ├── Profiling Engine
              │          ├── Normalization Engine
              │          ├── Temporal Engine
              │          ├── Deduplication Engine
              │          ├── Entity Resolution Engine
              │          ├── EDA Engine
              │          ├── Impact Analysis Engine
              │          └── Reporting Engine
              │
              ▼
        HUMAN APPROVAL GATES
              │
              ▼
         EXECUTION LAYER
              │
      ┌───────┼─────────┐
      ▼       ▼         ▼
    RAW     ANALYTICAL  PROVENANCE
   STORE       DB        GRAPH
```

---

# 6. Regra Arquitetural Fundamental

O LLM **nunca deve editar diretamente a base**.

Fluxo obrigatório:

```text
LLM sugere
      ↓
regra é explicitada
      ↓
impacto é simulado
      ↓
humano aprova
      ↓
serviço executa
      ↓
resultado é validado
      ↓
transformação é registrada
```

Isso deve existir em código, não apenas em manual.

---

# 7. Princípios Constitucionais do Sistema

## P1 — Raw Immutability
O dado bruto nunca é sobrescrito.

## P2 — Derived Data Separation
Todo valor derivado deve estar separado do original.

```text
cpf_raw
cpf_norm
```

## P3 — Uncertainty Preservation
Incerteza não pode ser automaticamente convertida em certeza. `possible_match` não pode silenciosamente tornar-se `same_entity=true`.

## P4 — Similarity Is Not Identity
Score de similaridade não é prova de identidade.

## P5 — Event Identity Is Explicit
Antes de deduplicar é obrigatório definir o que constitui um evento.

## P6 — Temporal Representation Is Not Temporal Truth
Converter timezone não valida relógio, timestamp ou momento real da ação.

## P7 — Provenance by Default
Toda transformação deve gerar registro de provenance/lineage.

## P8 — No Silent Inference
Nenhuma inferência gerada pelo LLM pode ser gravada como atributo factual sem classificação explícita.

## P9 — Human Authority
Decisões de alto impacto exigem aprovação humana.

## P10 — Reversibility
Deve ser possível reconstruir:

```text
resultado
→ regra
→ transformação
→ registro
→ valor raw
→ fonte
```

---

# 8. Modelo Epistemológico de Dados

O sistema deverá distinguir formalmente:

- **Raw Record** — registro tal como recebido;
- **Derived Record** — representação produzida por transformação;
- **Entity Candidate** — hipótese de que determinados registros representam a mesma entidade;
- **Event Candidate** — hipótese de que diferentes registros representam o mesmo evento;
- **Finding** — padrão identificado nos dados;
- **Hypothesis** — explicação possível para um ou mais achados;
- **Inference** — relação analítica produzida a partir de dados e hipóteses;
- **Conclusion** — afirmação que passou pelas etapas de validação definidas pelo procedimento.

---

# 9. Status Epistemológicos

Cada objeto relevante deverá possuir status explícito:

```text
OBSERVED
DERIVED
CANDIDATE
POSSIBLE
VALIDATED
VALIDATED_WITH_RESERVATIONS
DISPUTED
REJECTED
UNKNOWN
```

Exemplo:

```text
Carlos A ↔ @carlossilva_sp
status = POSSIBLE
```

E não:

```text
profile_owner = Carlos A
```

---

# 10. Módulo 1 — Ingestão

O TRACE-LM deverá importar localmente:

- CSV, TSV, XLS/XLSX;
- JSON, JSONL, XML;
- SQLite e bancos relacionais;
- TXT e logs;
- PDF e tabelas de PDF;
- documentos estruturados;
- posteriormente, formatos forenses específicos.

Cada arquivo recebe:

```text
source_id
file_id
hash
filename
mime_type
acquisition_datetime
ingestion_datetime
operator
case_id
```

---

# 11. Raw Data Vault

Todo dado original deve ser armazenado em repositório somente leitura, com:

- hashing;
- versionamento;
- controle de acesso;
- trilha de auditoria;
- criptografia em repouso;
- identificação da origem;
- preservação do arquivo original.

Nenhuma análise deve depender exclusivamente de planilha editável.

---

# 12. Módulo 2 — Data Profiling

Depois da ingestão, o sistema executa automaticamente:

## Estrutura
- linhas;
- colunas;
- tipos;
- encoding;
- tamanho.

## Cardinalidade
- únicos;
- repetidos;
- frequência.

## Missingness
- `NULL`;
- vazio;
- sentinelas;
- ausência estrutural.

## Domínio
- mínimos;
- máximos;
- ranges;
- padrões improváveis.

## Formatos
- telefones;
- CPF;
- CNPJ;
- e-mails;
- datas;
- moedas.

## Chaves
- possíveis identificadores;
- combinações únicas;
- campos discriminantes.

## Duplicidade
- registros idênticos;
- registros quase idênticos.

---

# 13. Produto do Profiling

Exemplo:

> **DATASET PROFILE — Nexus Transactions**
>
> 72 registros  
> 18 campos  
> 61 event_ids únicos  
> 2 CPFs distintos  
> 4 formatos de telefone  
> 3 padrões de timestamp  
> 8 registros com missing crítico  
> 11 pares de possíveis duplicatas  
> 6 inconsistências temporais  
> 2 potenciais colisões de identidade

Nenhuma transformação é executada nesta etapa.

---

# 14. Módulo 3 — Quality Analyzer

O sistema avalia:

- completude;
- acurácia potencial;
- consistência;
- validade;
- unicidade;
- atualidade;
- proveniência.

O sistema deve distinguir **erro provável** de **divergência legítima**.

Exemplo:

```text
Endereço A ≠ Endereço B
```

Saída:

> “Divergência detectada. Não há elementos suficientes para classificar um dos valores como erro. Verificar datas de referência e fontes.”

---

# 15. Módulo 4 — Missing Data Semantic Analyzer

Deverá detectar representações como:

```text
NULL
""
N/A
NI
não informado
não consta
0
-1
999999
01/01/1900
```

E perguntar:

> “O que significa esta representação nesta fonte?”

Nunca assumir automaticamente equivalência.

---

# 16. Normalization Engine

Transformações mecânicas devem ser executadas por serviços determinísticos.

Exemplo:

```text
PHONE_BR_V2
```

Input:

```text
(27) 99999-1234
```

Output:

```text
+5527999991234
```

Registro:

```text
rule = PHONE_BR_V2
version = 2.1
country = BR
confidence = high
operator = system
```

---

# 17. Transformation Preview

Antes de executar:

> **Transformação proposta**
>
> Regra: PHONE_BR_V2  
> Registros analisados: 72  
> Transformáveis automaticamente: 67  
> Ambíguos: 5  
> Valores alterados: 67  
> Valores originais preservados: SIM

Ações:

- **APROVAR**
- **REVISAR**
- **REJEITAR**

---

# 18. Módulo 5 — Temporal Engine

Esse componente deverá distinguir:

```text
timestamp_raw
parsed_datetime
offset
timezone
timezone_source
timestamp_utc
clock_quality
temporal_confidence
```

Exemplo:

```text
15/08/2024 11:20 -03:00
```

→

```text
2024-08-15T14:20:00Z
```

Mas o sistema deverá exibir:

> **Conversão de representação realizada. Isso não demonstra que o relógio de origem estava sincronizado.**

---

# 19. Temporal Quality

Cada timestamp pode receber:

```text
HIGH
MEDIUM
LOW
UNKNOWN
```

A classificação deve ser acompanhada de justificativa, por exemplo:

- timezone explícito, relógio não validado;
- timestamp sem timezone;
- relógio correlacionado com servidor NTP.

---

# 20. Módulo 6 — Deduplication Engine

O sistema não pergunta apenas “as linhas são iguais?”. Ele pergunta:

> **“Qual é a unidade de ocorrência?”**

Categorias:

```text
EXACT_DUPLICATE
TECHNICAL_DUPLICATE
LEGITIMATE_REPEATED_EVENT
ENTITY_REPRESENTATION
UNRESOLVED
```

---

# 21. Event Resolution

Separar formalmente:

### Entity Resolution
“É a mesma pessoa/empresa/dispositivo?”

### Event Resolution
“É a mesma transferência/acesso/chamada?”

Uma plataforma que mistura ambos tende a produzir erros metodológicos.

---

# 22. Módulo 7 — Entity Resolution Engine

Pipeline:

```text
Candidate Generation
        ↓
Blocking
        ↓
Attribute Comparison
        ↓
Similarity Features
        ↓
Probabilistic Scoring
        ↓
Decision Rules
        ↓
MATCH
POSSIBLE
NON-MATCH
```

---

# 23. Métricas Disponíveis

O motor poderá empregar:

- exact comparison;
- Levenshtein;
- Jaro;
- Jaro-Winkler;
- token similarity;
- Jaccard;
- phonetic keys;
- regras cadastrais;
- modelos probabilísticos no paradigma Fellegi-Sunter;
- modelos supervisionados quando existirem labels adequados.

O LLM não deve calcular essas métricas “mentalmente”. Ele chama ferramentas.

---

# 24. Matriz de Entity Resolution

| Atributo | A | B | Resultado |
|---|---|---|---|
| nome | Carlos Eduardo Silva | Carlos Eduardo Silva | igual |
| CPF | 111...44 | 999...66 | conflito |
| nascimento | 14/05/80 | 20/09/82 | conflito |
| telefone | ... | ... | diferente |

Conclusão:

```text
NON-MATCH
```

Explicação:

> O nome é idêntico, mas dois identificadores altamente discriminantes são incompatíveis.

---

# 25. High-Impact Merge Policy

Certos merges jamais poderão ocorrer automaticamente.

Se a fusão:

- aumenta patrimônio atribuído;
- conecta empresas antes desconectadas;
- atribui eventos de uma pessoa a outra;
- altera centralidade;
- conecta suspeito a crime;

O sistema deve classificá-la como:

> **HIGH IMPACT ENTITY DECISION**

E exigir revisão humana.

---

# 26. Impact Analysis Engine

Antes de aceitar um merge, o sistema deve simular o efeito.

### Antes

Carlos A:
- 14 eventos;
- Nexus;
- R$ 700 mil.

Carlos B:
- 5 eventos;
- Vanguarda;
- R$ 300 mil.

### Depois

Carlos AB:
- 19 eventos;
- Nexus + Vanguarda;
- R$ 1 milhão.

O TRACE-LM alerta:

> **Esta decisão altera significativamente a interpretação investigativa.**

E lista:

- +1 empresa vinculada;
- +5 eventos;
- +R$ 300 mil;
- +2 telefones;
- nova transferência intragrupo aparente.

---

# 27. Pergunta-chave do Impact Analysis

> **“Esta transformação apenas melhora a representação ou altera a narrativa analítica?”**

---

# 28. Módulo 8 — EDA Engine

O sistema poderá executar:

- frequências;
- frequências relativas;
- agregações;
- distribuições;
- histogramas;
- séries temporais;
- cruzamentos;
- coocorrências;
- concentração;
- dispersão;
- outliers;
- anomaly detection.

Mas deverá classificar o produto como:

```text
EXPLORATORY FINDING
```

E não:

```text
CONCLUSION
```

---

# 29. Escada Epistemológica

```text
DESCRIPTION
      ↓
PATTERN
      ↓
ASSOCIATION
      ↓
HYPOTHESIS
      ↓
INFERENCE
      ↓
CONCLUSION
```

O sistema não deve permitir salto silencioso entre níveis.

---

# 30. Outlier Policy

Quando detectar anomalia:

> “Registro R038 é estatisticamente atípico.”

Em seguida:

> “Possíveis explicações: erro; comportamento raro legítimo; diferença de fonte; transformação incorreta; comportamento investigativamente relevante.”

Nunca:

> “Registro suspeito de lavagem.”

---

# 31. Correlation Guardrail

Se o usuário perguntar:

> “A correlação de 0,88 demonstra que Carlos realizava as transferências?”

O sistema responde:

> “Não. A correlação demonstra associação quantitativa entre as variáveis definidas. A atribuição causal exige evidências adicionais.”

---

# 32. Pattern Provenance

Todo padrão deve possuir genealogia.

Exemplo:

```text
FINDING F023
“Concentração de eventos entre 00h e 02h”
```

Clicar abre:

```text
14 eventos
↓
11 eventos canônicos
↓
3 duplicatas removidas
↓
11 timestamps
↓
8 normalizados
↓
3 ambíguos
↓
2 convertidos para 00:00 pelo parser
```

Alerta:

> **Achado altamente sensível ao tratamento temporal.**

---

# 33. Pattern Stability

O sistema recalcula o padrão sob diferentes decisões metodológicas.

### Cenário A
Merge dos registros ambíguos: **31 eventos**.

### Cenário B
Sem merge: **19 eventos**.

### Cenário C
Pares possíveis excluídos: **17 eventos**.

Saída:

> **O achado não é robusto às decisões de Entity Resolution.**

---

# 34. Módulo 9 — Provenance Graph

Cada objeto pode ser representado como grafo:

```text
SOURCE
   ↓
RAW_RECORD
   ↓
TRANSFORMATION
   ↓
DERIVED_RECORD
   ↓
ENTITY
   ↓
EVENT
   ↓
AGGREGATION
   ↓
FINDING
   ↓
INFERENCE
```

---

# 35. Diário de Transformação

Tabela mínima:

```text
transformation_id
case_id
dataset_id
record_id
field
raw_value
rule
rule_version
parameters
derived_value
actor
tool
datetime
justification
approval
reversible
```

---

# 36. Criptografia e Integridade

Para ambientes de maior exigência:

- hashes;
- assinaturas;
- encadeamento de logs;
- append-only logs;
- event sourcing.

Objetivo: alterações posteriores na trilha tornam-se detectáveis.

---

# 37. Módulo 10 — LLM Orchestrator

O LLM terá quatro funções principais:

1. interpretar;
2. planejar;
3. explicar;
4. coordenar ferramentas.

Não deve ser autoridade factual.

---

# 38. Exemplo de Interação

Usuário:

> “Limpe esta base.”

TRACE-LM:

> “A solicitação envolve várias decisões semânticas. Antes de executar alterações, realizei profiling.
>
> Foram detectados:
>
> - 4 formatos de telefone;
> - 3 padrões temporais;
> - 11 possíveis duplicatas;
> - 9 pares candidatos de entidades;
> - 8 valores ausentes semanticamente ambíguos.
>
> Recomendo tratar separadamente normalização, missingness, deduplicação e Entity Resolution.”

Isso é muito diferente de:

> “Pronto, limpei a planilha.”

---

# 39. System Prompt Constitucional do LLM

Uma versão simplificada poderia começar assim:

> Você é um assistente local de preparação e análise investigativa de dados. Sua função não é determinar autoria, culpabilidade ou tipificação penal. Sua função é auxiliar o usuário a compreender, preparar, correlacionar e analisar dados preservando a distinção entre registro, entidade, evento, achado, inferência, hipótese e conclusão.
>
> Nunca sobrescreva dados brutos.
>
> Nunca trate similaridade como identidade.
>
> Nunca trate correlação como causalidade.
>
> Nunca trate ausência como inexistência sem fundamento.
>
> Nunca promova possible match a match sem a política exigida.
>
> Toda transformação relevante deve ser explícita, versionada, rastreável e reversível.
>
> Antes de operações de alto impacto, apresente efeito esperado e solicite aprovação.

---

# 40. Agentes Lógicos

Não é necessário criar vários modelos. O sistema pode apresentar papéis lógicos diferentes usando o mesmo LLM com prompts, ferramentas e políticas distintas:

- **Data Guardian** — preservação e integridade;
- **Profiler** — diagnóstico;
- **Transformation Planner** — sugestão de regras;
- **Entity Analyst** — Entity Resolution;
- **Temporal Analyst** — tempo;
- **EDA Analyst** — exploração;
- **Adversarial Auditor** — questionamento;
- **Report Synthesizer** — comunicação.

---

# 41. Adversarial Auditor

Para cada achado, o sistema pergunta:

> **“Como esse resultado poderia estar errado?”**

Ele procura:

- false merge;
- false split;
- duplicação;
- missingness;
- timezone;
- sampling bias;
- dependência entre fontes;
- regra de normalização;
- parser;
- outlier artificial;
- interpretação causal excessiva.

---

# 42. Modo Support × Challenge

Para hipóteses relevantes:

### SUPPORT
Que elementos são compatíveis com a hipótese?

### CHALLENGE
Que elementos a contradizem? Que explicações alternativas existem?

### SYNTHESIS
Qual conclusão é proporcional ao conjunto?

Isso evita que o LLM seja apenas um gerador de confirmação.

---

# 43. Human-in-the-Loop

Três níveis de decisão.

## Nível 1 — Automático
Operações reversíveis e de baixo risco, como remoção de pontuação de CPF.

## Nível 2 — Automático com revisão
Exemplo: normalização de telefone.

## Nível 3 — Aprovação obrigatória

- Entity merge;
- imputação de valor;
- exclusão de evento;
- alteração temporal relevante;
- conclusão investigativa;
- atribuição de identidade.

---

# 44. Interface do Usuário

Sugestão de nove áreas principais:

1. **CASE** — caso e fontes;
2. **DATA** — raw datasets;
3. **QUALITY** — profiling e qualidade;
4. **TRANSFORM** — transformações propostas/aplicadas;
5. **ENTITIES** — Entity Resolution;
6. **EVENTS** — Event Resolution;
7. **EXPLORE** — EDA;
8. **FINDINGS** — achados;
9. **AUDIT** — provenance e adversarial review.

---

# 45. Botão Conceitual Central

Todo resultado deve possuir:

## “COMO CHEGAMOS AQUI?”

Ao clicar:

```text
Conclusão
↓
Inferência
↓
Achado
↓
Query/EDA
↓
Dataset
↓
Entity Resolution
↓
Deduplicação
↓
Normalização
↓
Raw
↓
Fonte
```

---

# 46. Explainability Card

Cada afirmação relevante deveria apresentar:

- afirmação;
- status epistemológico;
- fonte;
- transformações envolvidas;
- evidência favorável;
- evidência contrária;
- dependências;
- confiança;
- limitações.

---

# 47. Local-first

Para dados investigativos, o desenho-base deve assumir:

> **zero exfiltration by default.**

O sistema poderá operar:

- air-gapped;
- LAN isolada;
- workstation;
- servidor institucional.

Nada deve depender obrigatoriamente de API externa.

---

# 48. Segurança

Requisitos recomendados:

- criptografia at rest;
- TLS interno;
- RBAC;
- autenticação multifator;
- segregação por caso;
- logs de acesso;
- logs append-only;
- gestão de secrets;
- sandbox de execução;
- controle de exportação;
- classificação de dados;
- timeout de sessão.

---

# 49. Modelo Local

Não treinar um LLM do zero inicialmente.

Estratégia inicial:

```text
modelo open-weight instruct competente
+
RAG local
+
tool calling
+
políticas
```

Isso entrega valor rapidamente.

---

# 50. Tamanho do Modelo

A arquitetura pode permitir diferentes tiers.

### Tier Workstation
Modelo relativamente compacto para classificação, explicação, geração de regras e tool calling.

### Tier Servidor
Modelo maior para raciocínio complexo, documentos extensos, síntese multi-fonte e adversarial analysis.

O projeto deve ser **model-agnostic**. Trocar o LLM não deve obrigar reescrever a plataforma.

---

# 51. RAG Local

Base de conhecimento pode conter:

- procedimentos institucionais;
- taxonomias;
- normas técnicas;
- dicionários de campos;
- manuais de sistemas;
- esquemas de bases;
- regras cadastrais;
- documentação de ferramentas;
- decisões metodológicas validadas.

O RAG serve para fornecer conhecimento de domínio, não para substituir os dados do caso.

---

# 52. Motor de Regras

Regras devem possuir IDs e versões.

Exemplo:

```text
CPF_NORMALIZE_V1
PHONE_BR_E164_V2
DATE_PARSE_BANK_A_V3
EVENT_DEDUP_BANK_V2
ENTITY_MATCH_PERSON_V4
```

Assim é possível responder:

> “Qual versão da regra produziu esse resultado?”

---

# 53. Execution Sandbox

Código gerado pelo LLM jamais roda diretamente no ambiente de evidência.

Fluxo:

```text
LLM generates code
↓
static inspection
↓
sandbox
↓
test dataset
↓
diff
↓
human approval
↓
production execution
```

---

# 54. Stack Possível

Sem impor dependência específica:

- **Backend:** Python;
- **Data processing:** Polars / Pandas / DuckDB;
- **Banco analítico:** PostgreSQL ou equivalente;
- **Raw store:** object store local;
- **Graph:** Neo4j ou equivalente;
- **Similarity:** RapidFuzz ou equivalente;
- **ER:** motor próprio ou biblioteca compatível com record linkage/Fellegi-Sunter;
- **API:** FastAPI / gRPC;
- **Frontend:** React ou interface web equivalente;
- **Containers:** Docker / Podman.

---

# 55. Esquema de Dados Principal

## RAW_RECORD

```text
record_id
dataset_id
source_id
original_payload
hash
ingested_at
```

## DERIVED_FIELD

```text
derived_id
record_id
field_name
raw_value
derived_value
transformation_id
```

## TRANSFORMATION

```text
transformation_id
rule_id
rule_version
parameters
actor
timestamp
approval
```

## ENTITY

```text
entity_id
entity_type
status
```

## ENTITY_MEMBERSHIP

```text
record_id
entity_id
match_score
decision
decision_actor
evidence
```

## EVENT

```text
event_id
event_type
timestamp
temporal_confidence
```

## FINDING

```text
finding_id
type
statement
status
query
dataset_version
confidence
```

---

# 56. Versionamento

Datasets:

```text
RAW_V1
PROCESSED_V1
ANALYTICAL_V1
ANALYTICAL_V2
```

Nunca:

```text
base_final.xlsx
```

---

# 57. Rollback

Toda transformação deve poder ser revertida.

Exemplo:

> “Desfaça ENTITY_MATCH_043.”

O sistema gera:

```text
Carlos AB
→
Carlos A
Carlos B
```

E recalcula análises dependentes.

---

# 58. Dependency Graph

Se um merge for revertido, o sistema precisa saber:

- quais eventos dependem da entidade;
- quais agregações mudam;
- quais gráficos mudam;
- quais achados mudam;
- quais relatórios ficam desatualizados.

---

# 59. Invalidação Automática

Exemplo:

Achado F17 depende de Entity Merge E7.

E7 é revertido.

F17 passa automaticamente a:

```text
STALE / REQUIRES_RECOMPUTATION
```

Em vez de continuar sendo apresentado como válido.

---

# 60. Resultados Esperados do Sistema

Ao término de uma análise, o TRACE-LM pode produzir um pacote com:

1. Inventário de fontes;
2. Relatório de profiling;
3. Relatório de qualidade;
4. Plano de transformação;
5. Dataset tratado versionado;
6. Diário de transformação;
7. Matriz de duplicidade;
8. Matriz de Entity Resolution;
9. Mapa de eventos;
10. Relatório temporal;
11. EDA;
12. Findings Registry;
13. Impact Analysis;
14. Adversarial Review;
15. Provenance Graph;
16. Relatório analítico exportável.

---

# 61. Produto Final não é “Base Limpa”

A expressão deveria ser evitada. Melhor:

> **Base Analítica Tratada — Versão N**

Porque “limpa” sugere inexistência de incerteza.

---

# 62. Métricas de Qualidade do Sistema

## Transformações
- taxa de sucesso;
- reversibilidade;
- erros;
- cobertura.

## Entity Resolution
- precision;
- recall;
- F1;
- false merge rate;
- false split rate;
- calibration.

## Provenance
- % de outputs rastreáveis.

Meta arquitetural:

> **100% dos achados relevantes devem possuir caminho até os registros de origem.**

---

# 63. Métrica Especial — Provenance Completeness

```text
PC =
nº de achados com lineage completo
/
nº total de achados
```

Alvo de produção:

```text
PC = 1.0
```

---

# 64. Métrica — Reproducibility Rate

Executar novamente:

```text
mesmo raw
+
mesmas regras
+
mesmos parâmetros
```

E comparar resultados. Operações determinísticas devem reproduzir exatamente.

---

# 65. Avaliação do LLM

O LLM deve ser avaliado separadamente dos motores analíticos.

Testes:

- hallucination;
- unsupported claims;
- tool-selection accuracy;
- instruction following;
- entity conflation;
- temporal reasoning;
- uncertainty preservation;
- refusal to overclaim;
- provenance citation accuracy.

---

# 66. Red Team Dataset

Construir datasets sintéticos com:

- homônimos;
- apelidos;
- CPFs semelhantes;
- telefones compartilhados;
- timestamps incompatíveis;
- duplicatas;
- eventos repetidos legítimos;
- `NULL`;
- zeros;
- dados contraditórios.

O sistema é avaliado pelo comportamento diante dessas armadilhas.

---

# 67. Gold Dataset

Será necessário criar conjunto de referência no qual se conhece:

- número verdadeiro de entidades;
- número verdadeiro de eventos;
- duplicatas;
- false pairs;
- timestamps;
- ground truth.

Isso permite avaliar ER e deduplicação objetivamente.

---

# 68. Desenvolvimento — Fase 0
## Requisitos e Threat Model

Definir:

- usuários;
- tipos de dados;
- classificações de sigilo;
- ameaças;
- ambiente;
- integrações;
- restrições legais.

**Produto:** Software Requirements Specification.

---

# 69. Fase 1 — Data Contracts e Ontology

Definir:

- Record;
- Entity;
- Event;
- Source;
- Transformation;
- Finding;
- Hypothesis.

**Produto:** modelo de domínio.

---

# 70. Fase 2 — Raw Vault + Ingestion

Construir:

- upload;
- hashing;
- storage;
- parsing;
- metadata.

**Aceitação:** nenhum dado raw pode ser alterado.

---

# 71. Fase 3 — Profiling e Quality

Construir profiling automático.

**Aceitação:** relatório reproduzível para todos os datasets suportados.

---

# 72. Fase 4 — Transformation Engine

Construir:

- rules;
- previews;
- diff;
- rollback;
- logs.

---

# 73. Fase 5 — Deduplication + Event Resolution

Criar:

- candidate pairs;
- classification;
- event canonicalization.

---

# 74. Fase 6 — Entity Resolution

Implementar:

- blocking;
- features;
- similarity;
- probabilistic matching;
- human review.

---

# 75. Fase 7 — Temporal Engine

Implementar:

- parsing;
- timezone;
- offsets;
- conversion;
- temporal quality.

---

# 76. Fase 8 — EDA + Finding Registry

Toda visualização relevante deve produzir objeto `Finding` com provenance.

---

# 77. Fase 9 — LLM Orchestration

Somente aqui o LLM ganha acesso aos módulos. Ele não substitui nenhum deles.

---

# 78. Fase 10 — Adversarial Auditor

Criar pipeline de contestação automática.

---

# 79. Fase 11 — Impact Analysis

Construir simulação `before vs after` para decisões de transformação.

---

# 80. Fase 12 — Validation

Usar:

- gold datasets;
- unit tests;
- integration tests;
- red-team cases;
- expert review.

---

# 81. MVP

Reduzir o primeiro MVP a sete capacidades:

1. ingestão;
2. raw preservation;
3. profiling;
4. normalização versionada;
5. deduplicação;
6. Entity Resolution assistida;
7. lineage.

Deixar anomaly detection, agentes adversariais complexos e geração avançada de relatórios para iterações posteriores.

---

# 82. MVP Demonstrador — Illicit Matrix

O caso da aula é adequado como benchmark inicial.

### Dataset
72 registros.

### Ground truth

- 2 Carlos distintos;
- duplicatas técnicas conhecidas;
- eventos repetidos legítimos;
- missingness;
- timestamps;
- anomalias artificiais.

---

# 83. Demonstração 1

Usuário importa dados.

TRACE-LM:

> 72 registros recebidos.
>
> Nenhuma transformação realizada.

---

# 84. Demonstração 2

Sistema:

> 11 candidatos a duplicata.
>
> 9 pares candidatos de entidades.
>
> 6 inconsistências temporais.

---

# 85. Demonstração 3

Carlos A × Carlos B.

```text
Name Similarity = 1.00
CPF = conflict
DOB = conflict
```

TRACE-LM:

> **NON-MATCH RECOMMENDED**
>
> High false-merge risk.

---

# 86. Demonstração 4

Sistema mostra:

> Se esses registros forem fundidos:
>
> eventos: 14 → 19  
> empresas: 1 → 2  
> valor associado: +R$ X  
> telefones: 2 → 3

---

# 87. Demonstração 5

Usuário rejeita merge. O sistema mantém as entidades separadas.

---

# 88. Demonstração 6

Deduplicação reduz:

```text
31 raw rows
→
19 canonical events
```

Sem eliminar eventos legítimos.

---

# 89. Demonstração 7

EDA inicialmente encontra:

> pico 00h–02h.

Pattern Provenance mostra que dois registros foram convertidos incorretamente para meia-noite.

Após correção:

> pico desaparece.

---

# 90. Demonstração Final

Sistema responde:

> O padrão temporal anteriormente identificado não é robusto. Ele dependia de uma regra inadequada de parsing.

---

# 91. O que o TRACE-LM Nunca Deve Fazer

Explicitamente fora do escopo:

- declarar culpabilidade;
- decidir prisão;
- determinar tipificação penal automaticamente;
- atribuir autoria exclusivamente por score;
- criar relações não sustentadas;
- sobrescrever raw;
- esconder uncertainty;
- executar código não validado sobre a base;
- enviar dados sigilosos para serviço externo sem política expressa.

---

# 92. Diferencial em Relação a um “Chat com Planilha”

Um chat comum responde:

> “Carlos Eduardo Silva realizou 31 transações.”

TRACE-LM responde:

> “A base contém 31 linhas atribuídas nominalmente a Carlos Eduardo Silva. Após resolução de eventos existem 19 eventos candidatos. Há pelo menos dois indivíduos homônimos. A atribuição consolidada das 31 linhas a uma pessoa única não é suportada.”

---

# 93. Diferencial em Relação a uma Ferramenta de Data Cleaning

Ferramenta tradicional:

```text
encontra inconsistência → corrige
```

TRACE-LM:

```text
encontra inconsistência
→ explica
→ simula
→ avalia impacto
→ solicita decisão
→ executa
→ registra
→ recalcula dependências
```

---

# 94. Diferencial em Relação a um Software de BI

BI começa normalmente no:

```text
dataset
```

TRACE-LM começa antes:

```text
fonte
→
raw
→
semântica
→
transformação
→
entidade
→
evento
→
dataset
```

---

# 95. Diferencial em Relação a um Software de Investigação

A proposta não é competir inicialmente com plataformas de link analysis.

É criar uma camada anterior:

> **epistemic data preparation**

Depois a base pode ser exportada para:

- BI;
- graph analysis;
- OSINT;
- ML;
- timeline;
- link analysis.

---

# 96. Ideia Central do Produto

Em software investigativo tradicional, a pergunta costuma ser:

> **“O que os dados mostram?”**

No TRACE-LM existe uma pergunta anterior:

> **“O que fizemos com os dados antes de eles mostrarem isso?”**

Essa é a principal inovação conceitual.

---

# 97. Visão de Longo Prazo

Em maturidade avançada, o TRACE-LM poderia tornar-se uma espécie de:

> **IDE investigativa para dados**

Assim como uma IDE acompanha código, dependências, versões, erros e execução, o TRACE-LM acompanharia:

- fontes;
- transformações;
- identidades;
- eventos;
- hipóteses;
- achados;
- dependências;
- conclusões.

---

# 98. Principal Função de Confiança

Qualquer investigador, supervisor, perito, promotor, magistrado ou defesa deveria poder perguntar:

> **“Por que este número está aqui?”**

E o sistema ser capaz de responder:

> “Porque estes 19 eventos foram derivados destes 24 registros, cinco dos quais foram consolidados conforme estas regras, aplicadas nesta versão, aprovadas por este usuário, sobre estes dados originais.”

Essa resposta vale mais, em contexto de alta consequência, do que simplesmente:

> “O modelo tem 95% de acurácia.”

---

# 99. Definição Final do Produto

> **Sistema local de inteligência artificial assistiva destinado à preparação, integração, resolução, exploração e auditoria de dados investigativos heterogêneos, projetado para preservar o conteúdo originário, representar explicitamente incerteza, registrar transformações e permitir rastreabilidade bidirecional entre fontes, entidades, eventos, achados, inferências e conclusões.**

---

# 100. Princípio de Design Mais Importante

> **O sistema não deve apenas mostrar o resultado de uma decisão analítica. Deve mostrar como a realidade analítica muda quando aquela decisão muda.**

No caso da Illicit Matrix, o grande recurso não seria o sistema dizer que existem dois Carlos. Seria mostrar que **fundir os dois faz surgir uma rede, um volume financeiro, uma centralidade e uma narrativa criminal que não existiam antes da decisão de matching**.

Esse é o núcleo intelectual e tecnológico do blueprint.
