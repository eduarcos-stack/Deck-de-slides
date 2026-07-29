# ADR-0001 — PostgreSQL + pgvector como banco vetorial

- **Status**: Aceito
- **Data**: 29/07/2026
- **Decisor**: Tech Lead
- **Relacionado**: [ADR-0003](0003-isolamento-multitenant-em-duas-camadas.md), [ADR-0005](0005-busca-hibrida-rrf-e-reranking.md)

## Contexto

O PROJUR indexa três corpora com regras de acesso distintas: documentos de casos
(isolados por caso e por organização), ativos institucionais (isolados por organização,
com validade e escopo) e fontes externas (licenciadas por organização). O pior defeito
possível do produto é recuperar conteúdo de um cliente ao trabalhar em outro
(CA-003, invariante I-1).

A escolha convencional em projetos de RAG é um banco vetorial dedicado — Qdrant,
Pinecone, Weaviate, Milvus. Eles oferecem melhor desempenho em escala de vetores e
recursos específicos de busca aproximada.

## Decisão

Usar **PostgreSQL 16 com a extensão pgvector** como único armazenamento de vetores no
MVP e na Fase 2, com índice HNSW e busca léxica nativa na mesma tabela.

## Justificativa

**1. A fronteira de autorização não é duplicada.**
Com banco vetorial separado, a regra de quem pode ver o quê passa a existir em dois
lugares: nas políticas do PostgreSQL e nos filtros de metadados do vector DB. Os dois
precisam concordar sempre, inclusive durante reindexações, migrações e falhas
parciais. Divergência entre eles é vazamento silencioso — não gera erro, apenas retorna
o documento errado. Com pgvector, a RLS que protege `matter` protege `chunk` pelo mesmo
mecanismo, na mesma transação.

**2. Consistência transacional.**
Retirar um ativo institucional precisa remover o chunk do índice **na mesma
transação** ([04 §7](../especificacao-tecnica/04-pipeline-rag.md)). Com dois
armazenamentos, isso vira consistência eventual e exige *outbox*, reconciliação e
tratamento de falha parcial — complexidade que só se justifica se houver ganho
proporcional.

**3. Busca híbrida sem federação.**
Denso e léxico na mesma query, sobre a mesma tabela, com o mesmo filtro de autorização
aplicado uma vez ([ADR-0005](0005-busca-hibrida-rrf-e-reranking.md)). Com bancos
separados, o filtro é aplicado duas vezes, em linguagens diferentes.

**4. O volume do MVP não exige mais.**
Estimativa: 10–50 mil chunks por escritório de porte médio; 1–5 milhões no agregado de
dezenas de organizações. pgvector com HNSW opera confortavelmente nessa faixa. A
vantagem de desempenho dos bancos dedicados aparece uma ou duas ordens de grandeza
acima.

**5. Menos operação.**
Um sistema a monitorar, fazer backup, restaurar, atualizar e proteger. Para um time de
6 pessoas, isso é capacidade de engenharia recuperada.

## Consequências

**Positivas**: isolamento verificável em um só lugar; transações reais; menos
infraestrutura; menos custo; backup e restauração unificados.

**Negativas**: desempenho inferior em escala muito grande; ausência de recursos
avançados de alguns vector DBs (quantização sofisticada, sharding nativo); o banco
transacional passa a carregar carga de busca vetorial, exigindo atenção ao
dimensionamento e possivelmente réplicas de leitura dedicadas.

**Riscos aceitos**: filtro muito seletivo pode degradar a recuperação aproximada no
HNSW ([12 R12](../especificacao-tecnica/12-riscos-tecnicos.md)). Mitigação: teste de
carga na Sprint 3, ajuste de `ef_search`, varredura exata para casos pequenos,
particionamento se necessário.

## Gatilho de revisão

Reavaliar se: latência de busca p95 > 1,5 s após ajustes; ou volume ultrapassar
~20 milhões de chunks; ou o teste de carga mostrar degradação de recall com filtro
estreito que o particionamento não resolva.

Se a decisão for revertida, o custo é conhecido: replicar a fronteira de autorização
no vector DB e implementar sincronização confiável. O modelo de dados já carrega
`org_id`, `matter_id` e `scope` em `chunk`, o que torna a migração mecânica.

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| Qdrant / Weaviate autogerenciado | Duplica a fronteira de autorização; ganho de desempenho desnecessário na escala do MVP |
| Pinecone gerenciado | Idem, com o agravante de enviar embeddings de conteúdo confidencial para fora do perímetro |
| Elasticsearch com vetores | Bom em híbrida, mas mais um sistema a operar, sem resolver a duplicação de autorização |
| pgvector + pg_search (BM25) | Considerado; adiciona dependência de extensão de terceiros. O full-text nativo do PostgreSQL é suficiente com RRF. Reavaliar se a qualidade léxica se mostrar insuficiente |
