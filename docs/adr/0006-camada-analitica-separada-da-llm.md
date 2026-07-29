# ADR-0006 — Cálculo jurimétrico em camada analítica isolada da LLM

- **Status**: Aceito
- **Data**: 29/07/2026
- **Decisor**: Tech Lead + Cientista de dados
- **Relacionado**: [06 — Jurimetria](../especificacao-tecnica/06-jurimetria.md)

## Contexto

A proposta estabelece uma regra crítica (§7.5): a LLM pode explicar um indicador, mas
não pode inventar percentuais nem calcular estatísticas a partir de recuperação
ocasional de documentos.

A implementação ingênua — e comum — seria recuperar decisões por RAG e pedir ao modelo
que "analise os padrões". Isso produz números que parecem indicadores e não são: a
amostra é o que a busca retornou, não a população; a contagem é aproximada; o resultado
não é reprodutível; e a resposta soa igualmente confiante em ambos os casos.

Em um produto jurídico, um percentual errado apresentado como evidência empírica é um
erro de categoria pior que uma citação errada — porque parece objetivo.

## Decisão

Separação arquitetural estrita:

1. **Camada analítica**: pipeline de dados versionado (`raw` → `staging` → `classified`
   → `marts`), transformações dbt testadas, indicadores calculados em SQL parametrizado,
   sempre filtrando por `dataset_version_id`.
2. **LLM restrita a dois papéis**: classificar decisões (com validação humana medida
   por kappa e F1) e explicar em linguagem natural resultados **já calculados**.
3. **A LLM não recebe os dados brutos** na etapa de explicação. Recebe o resultado
   agregado e o envelope de metodologia. Sem os dados, não há o que contar.
4. **Perguntas quantitativas em linguagem natural** são traduzidas para consultas de um
   **catálogo fechado** de indicadores. Sem correspondência, a resposta é "indicador não
   disponível neste recorte" — nunca uma estimativa.
5. **A base jurimétrica não participa do índice de RAG.**

## Justificativa

**Reprodutibilidade é requisito (CA-009).** A mesma consulta sobre o mesmo dataset com
a mesma versão de método deve produzir o mesmo número, bit a bit. Nenhum modelo
generativo oferece isso; SQL sobre dataset versionado oferece trivialmente.

**Amostra precisa ser definida, não emergente.** Um indicador exige população,
critérios de inclusão e exclusão, deduplicação e tratamento de ausentes explícitos.
Recuperação semântica define a amostra pelo que ficou parecido com a consulta — o que é
enviesamento por construção, e invisível ao usuário.

**A qualidade da classificação precisa ser mensurável.** Separando classificação de
cálculo, é possível medir kappa e F1 por variável e impedir que variável mal
classificada chegue à produção. Se a LLM calculasse direto, não haveria onde medir.

**O envelope de metodologia é obrigatório (CA-008).** Sendo o cálculo determinístico, o
envelope é produzido pelo mesmo processo, com números reais de amostra, cobertura e
dados ausentes. Um número gerado por modelo não tem envelope verdadeiro.

**Impedir por construção é melhor que instruir.** Um prompt dizendo "não calcule
estatísticas" é uma instrução probabilística. Não entregar os dados é uma garantia.

## Consequências

**Positivas**: indicadores reprodutíveis e auditáveis; qualidade da classificação
mensurável; envelope sempre verdadeiro; a LLM contribui onde é boa (classificar
linguagem, explicar resultado) e não onde é ruim (contar, calcular); a jurimetria pode
ser removida do MVP sem afetar o restante.

**Negativas**: catálogo fechado de indicadores é menos flexível que perguntar qualquer
coisa em linguagem natural — o usuário encontrará perguntas que o sistema não responde;
adicionar indicador exige trabalho de engenharia de dados; o pipeline exige
competências que o engenheiro de IA sozinho não cobre, o que tem consequência de
composição de time ([11 §1](../especificacao-tecnica/11-estimativa-esforco-e-sprints.md)).

A primeira consequência negativa é uma escolha consciente: **é preferível responder
"não sei" do que responder um número inventado**. Essa é a tese do produto inteiro
aplicada à jurimetria.

## Verificação

- Teste de reprodutibilidade: consulta versionada reexecutada produz resultado idêntico
- Teste de contrato: nenhum endpoint de indicador retorna sem envelope de metodologia
- Revisão de código: a etapa de explicação não recebe linhas de decisão, apenas
  agregados — verificada por teste do contexto montado
- Métrica de classificação por variável, com limiar de publicação

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| RAG sobre decisões com contagem pela LLM | Amostra emergente, não reprodutível, sem envelope verdadeiro; viola §7.5 diretamente |
| LLM com ferramenta de execução de SQL livre | Reprodutibilidade e controle de qualidade dependeriam do SQL gerado a cada vez; superfície de erro e de injeção ampla |
| Texto-para-SQL com validação | Mais flexível; risco de consulta sutilmente errada que produz número plausível. Reavaliar quando houver catálogo maduro e validação forte |
| Warehouse dedicado desde o MVP | Volume não justifica; schema separado no mesmo Postgres com dbt entrega versionamento e testes agora |
