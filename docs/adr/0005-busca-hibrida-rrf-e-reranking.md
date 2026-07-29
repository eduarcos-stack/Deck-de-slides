# ADR-0005 — Busca híbrida com RRF e reranking cross-encoder

- **Status**: Aceito
- **Data**: 29/07/2026
- **Decisor**: Tech Lead
- **Relacionado**: [ADR-0001](0001-postgres-pgvector-como-banco-vetorial.md)

## Contexto

Consultas no PROJUR têm duas naturezas que exigem mecanismos diferentes:

- **Léxicas exatas**: "art. 373, II, CPC", "Súmula 7 do STJ", "processo
  1234567-89.2024.8.26.0100", nome de uma parte com grafia específica. Aqui, o termo
  literal importa e a similaridade semântica atrapalha — um embedding trata "art. 373"
  e "art. 375" como quase idênticos.
- **Semânticas**: "o contrato previa exclusividade?", "há indício de má-fé na conduta
  do réu?". Aqui, a paráfrase é a regra e a busca literal falha.

Busca puramente densa erra a primeira classe. Busca puramente léxica erra a segunda.
Em documentos jurídicos, as duas aparecem na mesma sessão de trabalho.

## Decisão

Pipeline de recuperação em quatro etapas:

1. **Recuperação dupla** sobre a mesma tabela, com o mesmo filtro de autorização:
   denso (pgvector, cosseno, HNSW, top-50) e léxico (`tsvector` em português com
   `unaccent`, `websearch_to_tsquery`, top-50).
2. **Fusão por Reciprocal Rank Fusion**, `k = 60`, produzindo 30 candidatos.
3. **Reranking** por cross-encoder autogerenciado sobre os 30.
4. **Expansão small-to-big**: os melhores filhos são substituídos por seus chunks pais.

Complementos: busca trigram para grafias divergentes de nomes; reescrita de consulta
limitada, com a consulta original sempre participando da fusão.

## Justificativa

**RRF em vez de soma ponderada de pontuações.** Pontuação de similaridade de cosseno e
pontuação de `ts_rank_cd` vivem em escalas diferentes, com distribuições diferentes que
variam por consulta. Combiná-las exige normalização e um peso — e não temos dados
rotulados para ajustar esse peso, nem ele seria estável entre tipos de consulta. RRF
usa apenas a **posição** no ranking, o que é invariante a escala e notoriamente robusto
sem ajuste. A constante 60 é o valor padrão da literatura e funciona bem sem calibração.

**Reranking depois, não antes.** O cross-encoder lê consulta e trecho juntos e captura
relevância que nenhum dos dois canais isolados percebe. É caro por par, o que o torna
inviável sobre o corpus inteiro e adequado sobre 30 candidatos.

**Reranker autogerenciado.** Ele vê o conteúdo dos trechos do caso. Enviá-lo a um
serviço externo submeteria todo o material recuperado à política de egresso, a cada
consulta.

**Small-to-big no fim.** Busca-se sobre o filho pequeno (precisão semântica) e
entrega-se o pai maior (contexto). As âncoras de citação apontam para o filho, de modo
que o destaque mostrado ao revisor seja preciso e não uma seção inteira.

**Filtro de autorização aplicado uma vez, antes das duas buscas.** É o benefício direto
de ambos os canais viverem na mesma tabela ([ADR-0001](0001-postgres-pgvector-como-banco-vetorial.md)).

## Consequências

**Positivas**: cobre as duas naturezas de consulta; sem hiperparâmetro sensível na
fusão; degradação graciosa (sem reranker, usa RRF; sem embeddings, usa léxico); um
único filtro de autorização.

**Negativas**: duas buscas por consulta, com custo de latência; o reranker exige GPU ou
CPU dimensionada; mais partes móveis para instrumentar e depurar.

**Alvo de latência**: p95 < 1,5 s para top-20, medido em [01 §8](../especificacao-tecnica/01-arquitetura-de-referencia.md).

## Verificação

O conjunto de recuperação anotado ([09 §4.1](../especificacao-tecnica/09-observabilidade-custos-e-avaliacao.md))
mede Recall@k, Precision@k e nDCG para quatro configurações: só denso, só léxico,
híbrido sem rerank, híbrido com rerank. A decisão será confirmada ou revista com
números na Sprint 3 — o pipeline completo só se justifica se o ganho sobre híbrido sem
rerank for material.

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| Só busca densa | Falha em citações normativas, números de processo e nomes — classe frequente e de alto impacto |
| Só busca léxica | Falha em paráfrase, que é como advogados formulam perguntas |
| Soma ponderada normalizada | Exige calibração sem dados rotulados; instável entre tipos de consulta |
| Embedding esparso + denso (SPLADE, BGE-M3 esparso) | Promissor e possivelmente superior; adiciona complexidade de indexação. Reavaliar após o bake-off, agora que BGE-M3 já produz representação esparsa |
| Rerank por LLM (listwise) | Qualidade potencialmente melhor, custo e latência muito superiores; inviável em cada recuperação de bloco |
