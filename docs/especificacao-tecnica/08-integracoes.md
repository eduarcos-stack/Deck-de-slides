# 08 — Integrações

## 1. Princípio: adaptador, nunca acoplamento

Toda integração externa entra pelo mesmo padrão: uma **porta** definida pelo domínio e
um **adaptador** por fornecedor. O domínio conhece a porta; nunca o fornecedor. Isso
não é purismo arquitetural — é o que torna trocar de base jurídica ou de provedor de
assinatura uma tarefa de dias e não de sprints, e é a exigência de portabilidade de
§10.3.

```python
class LegalSourcePort(Protocol):
    source_id: str
    def search(self, q: LegalQuery, scope: AuthorizedScope) -> list[LegalResult]: ...
    def fetch(self, ref: LegalRef) -> LegalDocument: ...
    def citation(self, ref: LegalRef) -> Citation: ...   # identificador oficial
    def license_terms(self) -> LicenseTerms: ...
```

`license_terms()` é obrigatório na interface porque a licença determina o que pode ser
indexado, armazenado, citado e exibido. Uma base licenciada que permita consulta mas
proíba armazenamento do inteiro teor exige comportamento diferente no RAG — e essa
diferença precisa ser dado do sistema, não conhecimento tácito de quem integrou.

## 2. Mapa de integrações

| Categoria | Papel | Prioridade | Fase |
|---|---|---|---|
| Provedores de LLM | Geração, extração, classificação, verificação | Essencial | MVP |
| Embeddings e reranking | Indexação e recuperação | Essencial | MVP |
| Object storage + KMS | Documentos, derivados, exportações, auditoria WORM | Essencial | MVP |
| Identidade (IdP do escritório) | SSO corporativo | Alta | Fase 2 |
| Fontes jurídicas licenciadas | Legislação, jurisprudência, doutrina | Alta | Fase 2 (MVP: base interna) |
| Fontes públicas de decisões | Insumo jurimétrico | Alta | MVP restrito |
| Armazenamento documental do escritório | Ingestão a partir do acervo | Média | Fase 2 |
| Software de gestão jurídica | Sincronização de casos e prazos | Média | Fase 3 |
| Assinatura eletrônica | Assinatura da peça aprovada | Média | Fase 3 |
| E-mail e calendário | Prazos e comunicação | Baixa | Fase 3 |
| Peticionamento eletrônico | Protocolo | Fora de escopo | Explicitamente adiado (v0.1 §12.3) |

## 3. Fontes jurídicas externas

### 3.1 Modelo de integração

Duas estratégias, escolhidas conforme a licença permitir:

| Estratégia | Quando usar | Comportamento |
|---|---|---|
| **Indexação local** | Licença permite armazenar e indexar | Conteúdo entra como `scope='external_source'` no índice; recuperação híbrida normal |
| **Federada** | Licença permite consultar, não armazenar | Busca em tempo real na API do fornecedor; trechos usados no contexto sem persistência; citação persistida |

A estratégia federada tem latência maior e recuperação pior (não há reranking sobre o
corpus completo), e é a única possível com boa parte das bases comerciais. O sistema
suporta as duas simultaneamente, por fonte.

### 3.2 Requisitos de citação

Toda fonte externa deve produzir citação com identificador **verificável** — número
único do processo, identificador da publicação, referência normativa canônica. Fonte
que não consegue produzir identificador estável não é integrada: violaria CA-001 e o
princípio de transparência de origem.

```python
class Citation(BaseModel):
    source_id: str
    official_id: str            # obrigatório
    title: str
    court_or_authority: str | None
    decided_or_published_on: date | None
    url: HttpUrl | None
    retrieved_at: datetime
    excerpt_anchor: ExcerptAnchor | None
```

### 3.3 Atualidade

Fontes jurídicas mudam: normas são revogadas, súmulas são canceladas, precedentes são
superados. Controles:

- `valid_until` e `superseded_by` nos registros de fonte, quando o fornecedor informar
- Reindexação periódica com detecção de alteração por hash
- Alerta de "possivelmente desatualizado" quando a fonte não é revalidada há mais de N
  dias, com N configurável por tipo
- Métrica de atualidade no conjunto de avaliação ([04 §10](04-pipeline-rag.md))

O sistema **não** afirma que uma norma está vigente. Ele informa data de coleta e
última verificação, e sinaliza incerteza. Afirmar vigência exigiria uma fonte
autoritativa de vigência que o produto não tem — e uma afirmação errada nesse campo é
exatamente o tipo de erro jurídico que a proposta busca evitar.

## 4. Fontes públicas para jurimetria

Tratadas em [06 §3](06-jurimetria.md). Do ponto de vista de integração:

- Coletores respeitam limites de taxa e termos de uso, com backoff
- Falha de fonte não derruba o pipeline; entra no relatório de cobertura
- Toda requisição é registrada para reprodutibilidade
- Mudança de contrato da API é detectada por teste de contrato agendado, não por falha
  em produção

## 5. Armazenamento documental do escritório

Escritórios já mantêm acervo em SharePoint, Google Drive, sistemas de gestão ou
servidores de arquivo. Ingestão a partir dessas origens é o caminho mais rápido para
popular a base institucional — e o mais perigoso, porque traz junto material que não
deveria ser indexado.

Requisitos:

1. **Seleção explícita de escopo**: pastas específicas, nunca "toda a unidade"
2. **Prévia antes de importar**: quantos arquivos, quais tipos, quais serão ignorados
3. **Respeito às permissões de origem**, quando o conector as expuser
4. **Importação incremental** com marca-d'água, sem reprocessar o já ingerido
5. **Rastreabilidade da origem** no metadado do documento
6. **Sem gravação de volta** na origem: a integração é de leitura

## 6. Assinatura eletrônica

Fase 3. Requisitos já definidos para não fechar portas na arquitetura de exportação:

- Assinatura ocorre **após** o estado `ready_to_file` — nunca antes dos gates
- O documento assinado é armazenado como novo artefato imutável, vinculado à versão
- Evento de auditoria registra quem assinou, quando e com qual certificado
- Suporte a certificado ICP-Brasil conforme exigência do escritório

## 7. Webhooks e API pública

Não estão no MVP, mas a decisão de projeto é relevante agora: quando existirem, a API
pública será um **conjunto separado de endpoints**, com autenticação própria
(client credentials), escopos por organização, limites de taxa e versionamento
explícito. Não será a mesma superfície usada pelo frontend.

A razão é a invariante I-1: a API interna assume um contexto de sessão de usuário
estabelecido pelo IdP. Reaproveitá-la para integrações máquina-a-máquina exigiria
flexibilizar essa suposição em todos os endpoints — multiplicando a chance de erro no
lugar exatamente errado.

## 8. Resiliência de integrações

| Padrão | Aplicação |
|---|---|
| Timeout explícito | Toda chamada externa; nunca timeout padrão da biblioteca |
| Retry com backoff e jitter | Apenas para erros transitórios e operações idempotentes |
| Disjuntor | Abre após N falhas; evita esgotar workers contra serviço indisponível |
| Bulkhead | Pools separados por integração; uma fonte lenta não trava as demais |
| Cache | Consultas idempotentes a fontes externas, com TTL por tipo |
| Degradação | Fonte indisponível é sinalizada ao usuário; o sistema não simula resultado |
| Teste de contrato | Agendado, contra sandbox do fornecedor quando existir |

A linha de degradação repete um princípio já estabelecido e vale porque é onde
sistemas costumam falhar: quando uma fonte externa está fora, o resultado é uma
recuperação **incompleta e declarada**, nunca uma resposta que finge completude. É
CA-012 aplicado a integrações.

---

**Anterior**: [07 — Segurança e privacidade](07-seguranca-e-privacidade.md) · **Próximo**: [09 — Observabilidade, custos e avaliação](09-observabilidade-custos-e-avaliacao.md)
