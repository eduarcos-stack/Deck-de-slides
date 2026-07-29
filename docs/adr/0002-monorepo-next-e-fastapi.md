# ADR-0002 — Monorepo com Next.js e FastAPI

- **Status**: Aceito
- **Data**: 29/07/2026
- **Decisor**: Tech Lead

## Contexto

O PROJUR precisa de uma interface rica — editor jurídico com marcas de evidência
persistentes, streaming de geração, estados de incerteza, acessibilidade — e de um
backend cujo trabalho central é processamento documental, RAG e avaliação de IA.

A tentação em cada extremo é conhecida: unificar tudo em TypeScript (um só runtime) ou
tudo em Python (um só ecossistema). Ambas custam caro no extremo oposto.

## Decisão

**Monorepo** com:
- `apps/web` — Next.js (App Router) + TypeScript
- `apps/api` — FastAPI + Python 3.12, incluindo os workers Celery
- `packages/contracts` — OpenAPI do backend e tipos TypeScript gerados a partir dele
- Serviços de IA (`llm-gateway`, embeddings, reranker) em Python

## Justificativa

**Python no backend é decorrência do domínio.** Extração de documentos, OCR,
manipulação de PDF, avaliação de RAG, ciência de dados para jurimetria, clientes de
provedores de modelos — o ferramental maduro está em Python. Escolher Node ou Go
obrigaria a manter um segundo runtime só para IA, com a fronteira entre eles
atravessando exatamente o fluxo mais crítico do produto.

**TypeScript no frontend é decorrência da interface.** O editor com marcas de evidência
é o componente mais complexo do produto e depende do ecossistema ProseMirror. Streaming
por SSE com renderização progressiva é natural em React Server Components.

**Monorepo é decorrência do contrato.** O acoplamento real entre front e back é a
forma dos dados. Gerar tipos TypeScript a partir do OpenAPI do FastAPI, no mesmo
repositório e com verificação no CI, elimina a classe inteira de bugs de contrato
divergente. Em repositórios separados, isso exigiria publicação e versionamento de
pacote — cerimônia que um time de 6 pessoas não deveria pagar.

**Monólito modular, não microsserviços.** Cada serviço adicional é mais uma fronteira
onde a autorização precisa ser reaplicada, e a invariante I-1 não tolera isso. Os
módulos têm fronteiras explícitas com lint de import; extrair um serviço depois é
possível quando houver razão concreta (escala independente, isolamento de falha).

## Consequências

**Positivas**: cada camada usa a linguagem certa; contratos verificados no CI; um só
PR atravessa a stack inteira; refatoração entre camadas é atômica.

**Negativas**: duas cadeias de ferramentas (pnpm/Turborepo e uv); o time precisa ser
confortável nas duas linguagens; CI mais elaborado; risco de acoplamento indevido entre
módulos, mitigado por lint arquitetural.

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| Tudo em TypeScript | Ferramental de documentos, avaliação e ciência de dados imaturo ou ausente; forçaria reimplementação |
| Tudo em Python (com HTMX ou similar) | Inviabilizaria o editor rico, que é requisito central |
| Repositórios separados | Cerimônia de versionamento de contrato desproporcional ao tamanho do time |
| Microsserviços desde o início | Multiplica a superfície de autorização sem necessidade de escala |
| Django em vez de FastAPI | Admin pronto é atraente, mas o ORM e o middleware dificultam o controle fino de sessão exigido pela RLS e o SQL explícito da busca híbrida |
