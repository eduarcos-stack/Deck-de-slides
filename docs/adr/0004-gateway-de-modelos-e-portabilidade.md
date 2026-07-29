# ADR-0004 — Gateway de modelos próprio e portabilidade

- **Status**: Aceito
- **Data**: 29/07/2026
- **Decisor**: Tech Lead

## Contexto

A proposta trata dependência de fornecedor como risco explícito (§16.1) e exige evitar
lock-in "principalmente em embeddings, modelos, armazenamento e vetores" (§10.3). Ao
mesmo tempo, custo variável de inferência é apontado como risco de margem.

O mercado de modelos muda em ciclos de meses: preços caem, capacidades mudam,
disponibilidade regional varia, versões são descontinuadas. Um produto que espalhe
chamadas diretas a um provedor pelo código de domínio paga essa volatilidade em
refatoração.

Existem gateways prontos (LiteLLM e similares) que resolvem a normalização de API entre
provedores.

## Decisão

Construir um **gateway próprio, fino**, com quatro responsabilidades e nenhuma além
delas:

1. **Tiers lógicos** — o domínio pede `tier="extraction"`, nunca um nome de modelo. O
   mapeamento tier → provedor/modelo vive em configuração versionada por ambiente e
   por organização.
2. **Política de egresso** — verifica o nível de sigilo do conteúdo contra a política
   da organização antes de qualquer chamada externa
   ([07 §5](../especificacao-tecnica/07-seguranca-e-privacidade.md)).
3. **Governança de custo** — contabiliza tokens e custo por chamada, aplica cotas,
   limites e disjuntor de anomalia; grava `ai_run`.
4. **Confiabilidade e observabilidade** — timeout, retry com backoff, fallback entre
   provedores do mesmo tier, trace com prompt versionado.

Bibliotecas de cliente dos provedores são usadas normalmente **dentro** dos adaptadores.

## Justificativa

**Tier lógico é o que dá portabilidade real.** Normalizar a API entre provedores — o
que os gateways prontos fazem bem — resolve a parte fácil. A parte difícil é que o
código de domínio não deve saber qual modelo existe. Com tiers, trocar de fornecedor é
alterar uma linha de configuração e rodar o conjunto de avaliação.

**As responsabilidades 2 e 3 são específicas deste produto.** Nenhum gateway pronto
conhece nosso conceito de nível de sigilo por caso, política de egresso por organização
ou atribuição de custo por matter. Adotar um gateway pronto significaria envolvê-lo em
uma camada própria para isso — restando um gateway que só normaliza APIs, coisa que os
SDKs oficiais já fazem.

**Superfície de dependência.** O ponto por onde passa todo o conteúdo confidencial do
produto é o pior lugar para uma dependência grande, de evolução rápida e ampla árvore
transitiva.

**Tamanho real.** O gateway é pequeno: cerca de 800 a 1.200 linhas, incluindo
adaptadores. Estimativa de 1 a 1,5 pessoa-semana. O controle que ele dá sobre custo e
egresso vale muitas vezes isso.

## Consequências

**Positivas**: troca de fornecedor é configuração; política de egresso aplicada em um
único ponto auditável; custo atribuído por caso e organização desde o início; fallback
automático entre provedores; prompts e versões rastreados por execução.

**Negativas**: precisamos manter os adaptadores quando os provedores mudarem suas APIs;
recursos muito específicos de um provedor exigem extensão da interface — e a política é
usar apenas o que existe em pelo menos dois provedores, salvo justificativa registrada.

## Detalhes

```python
class LLMGateway(Protocol):
    async def complete(
        self,
        tier: Tier,
        messages: list[Message],
        schema: type[BaseModel] | None,
        ctx: AIContext,      # org, matter, user, purpose, sigilo
    ) -> LLMResult: ...      # saída validada + uso + custo + trace_id + model_id
```

Regras invariáveis:
- Nenhuma chamada sem `ctx`; sem contexto não há como verificar egresso nem atribuir custo
- Toda chamada grava `ai_run` ([03 §3.8](../especificacao-tecnica/03-modelo-de-dados.md))
- Bloqueio por política produz `outcome = policy_blocked`, não exceção genérica
- Prompt e versão vêm de arquivo versionado, nunca de string no código

## Gatilho de revisão

Reavaliar se: a manutenção dos adaptadores passar a consumir mais de 1 pessoa-semana
por trimestre; ou se surgir um gateway que ofereça política de egresso e atribuição de
custo por tenant com a granularidade que precisamos.

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| Chamadas diretas ao SDK no domínio | Espalha o fornecedor pelo código; impossibilita política central de egresso e custo |
| LiteLLM ou gateway equivalente | Resolve o problema fácil (normalização de API) e não o difícil (egresso, custo por tenant, tiers); exigiria camada própria por cima assim mesmo |
| Framework de orquestração completo | Assume o controle do fluxo, incluindo recuperação e citação — que é justamente onde precisamos de controle explícito ([02 §3](../especificacao-tecnica/02-stack-tecnologico.md)) |
| Fornecedor único com contrato | Melhor preço negociado, risco concentrado; contraria §10.3 |
