# 09 — Observabilidade, custos e avaliação

## 1. Por que os três juntos

Em um sistema de IA, qualidade, custo e latência são a mesma decisão vista de ângulos
diferentes. Trocar o modelo do tier de verificação melhora a fidelidade e piora o
custo; reduzir o `k` da recuperação melhora latência e piora cobertura. Separar essas
métricas em painéis distintos leva a otimizar uma às custas das outras sem perceber.
Aqui elas compartilham a mesma instrumentação e o mesmo painel.

## 2. Telemetria

### 2.1 Camadas

| Camada | Ferramenta | Conteúdo |
|---|---|---|
| Traces distribuídos | OpenTelemetry | Requisição → autorização → recuperação → geração → verificação |
| Traces de LLM | Langfuse autogerenciado | Prompt, versão, modelo, tokens, custo, latência, saída, avaliação |
| Métricas | Prometheus + Grafana | RED por endpoint, filas, taxas de erro, métricas de negócio |
| Logs | Loki, estruturados em JSON | Eventos de aplicação com redação de conteúdo sensível |
| Auditoria | PostgreSQL append-only | Trilha jurídica — **não** é log ([ADR-0007](../adr/0007-auditoria-append-only-com-encadeamento-de-hash.md)) |

A distinção entre log e auditoria é intencional e costuma ser confundida: log é
operacional, retido por semanas, pode ser perdido em um incidente de infraestrutura;
auditoria é jurídica, retida por anos, íntegra e verificável. Misturar os dois resulta
em auditoria frágil e log caro.

### 2.2 Atributos padronizados

Todo span carrega: `org_id`, `matter_id` (quando aplicável), `user_id`, `purpose`,
`tier`, `model_id`, `prompt_version`, `trace_id`. Isso permite responder perguntas
operacionais que importam ao negócio: quanto custa um caso, qual organização consome
mais, qual finalidade tem pior latência, qual versão de prompt regrediu.

**Conteúdo de documento nunca vai para logs.** Traces de LLM contêm conteúdo por
necessidade — é o que permite depurar uma resposta ruim — e por isso o Langfuse é
autogerenciado, dentro do perímetro, com retenção de 90 dias e redação configurável
por organização.

## 3. Painéis

| Painel | Público | Indicadores |
|---|---|---|
| Saúde do sistema | Engenharia | Latência p50/p95/p99, taxa de erro, profundidade de fila, saturação |
| Qualidade da IA | Eng. de IA + jurídico | Atribuição, abstenção, fidelidade, achados por gate, feedback negativo |
| Custo | Tech lead + gestão | Custo por organização, caso, finalidade, tier, modelo; tendência e projeção |
| Adoção | Produto | Usuários ativos, casos processados, conclusão de fluxo, uso de ativos, abandono |
| Valor | Sponsor | Tempo até primeira minuta, ciclos de revisão, reaproveitamento — sempre contra baseline |
| Segurança | Segurança | Egressos bloqueados, negações de autorização, anomalias, integridade da auditoria |

Alertas seguem a regra: **todo alerta tem runbook**. Alerta sem procedimento de
resposta vira ruído e treina a equipe a ignorar alertas.

## 4. Avaliação de IA e RAG

### 4.1 Conjuntos de avaliação

| Conjunto | Tamanho inicial | Origem | Uso |
|---|---|---|---|
| Recuperação anotada | 150–250 consultas com trechos relevantes marcados | Casos reais autorizados do design partner | Recall@k, Precision@k, nDCG |
| Extração de fatos | 60–100 documentos com gabarito | Anotação por especialista jurídico | Precisão e recall de entidades, datas, valores |
| Geração de blocos | 40–80 casos com peças aprovadas de referência | Acervo do escritório | Fidelidade, completude, atribuição |
| Abstenção | 50–80 perguntas **sem** resposta na base | Construído deliberadamente | Taxa de abstenção correta |
| Adversarial de isolamento | 100+ consultas cruzando organizações | Sintético | Zero vazamentos — gate absoluto |
| Injeção de prompt | 40+ documentos com instruções embutidas | Sintético | Taxa de resistência |
| Classificação jurimétrica | 300+ decisões por variável | Anotação dupla | Kappa, F1 por classe |

O conjunto de abstenção merece nota: é o mais fácil de esquecer e o mais revelador.
Um sistema que nunca abstém não é confiável, é apenas otimista. Perguntas
deliberadamente sem resposta na base medem exatamente a propriedade que a proposta
mais valoriza.

Construir esses conjuntos exige tempo de especialista jurídico — está previsto no plano
de sprints e é a principal dependência não técnica do MVP.

### 4.2 Métricas e limiares

| Métrica | Limiar inicial | Bloqueia o merge? |
|---|---|---|
| Recall@10 (recuperação) | ≥ 0,85 | Sim, se regredir > 3 pontos |
| Precision@5 | ≥ 0,70 | Sim, se regredir > 3 pontos |
| Fidelidade (afirmações sustentadas) | ≥ 0,95 | Sim |
| Atribuição (afirmações materiais com âncora) | ≥ 0,98 | Sim |
| Abstenção correta | ≥ 0,90 | Sim |
| Vazamento cross-tenant | **0** | Sim, absoluto |
| Resistência a injeção | ≥ 0,95 | Sim |
| Extração de datas e valores | ≥ 0,95 | Sim |

Limiares iniciais, a serem recalibrados após a primeira medição real na Sprint 2.
Definir limiar antes de medir é útil como declaração de ambição e inútil como gate —
por isso o gate entra a partir da Sprint 3, quando há baseline.

### 4.3 Avaliação no CI

```yaml
# Executado quando muda prompt, recuperação, modelo, chunking ou verificador
eval:
  steps:
    - restaura snapshot de avaliação (dados sintéticos + amostra autorizada)
    - indexa com a configuração do PR
    - executa os sete conjuntos
    - compara com o baseline da branch principal
    - falha se qualquer gate regredir além do limiar
    - publica relatório comparativo no PR
```

Custo: cada execução completa consome inferência. Mitigação — conjunto reduzido
(*smoke*) em cada PR, conjunto completo no merge para a branch principal e
diariamente. Modelos autogerenciados nos tiers de alto volume reduzem
substancialmente o custo de avaliação, o que é um argumento adicional em favor da
escolha feita em [02 §5.2](02-stack-tecnologico.md).

### 4.4 Bake-off de modelos (Sprint 0–1)

Antes de fixar o mapeamento tier → modelo, uma comparação metódica:

| Etapa | Descrição |
|---|---|
| 1 | Selecionar 3–4 candidatos por tier (comerciais e abertos) |
| 2 | Rodar os conjuntos de avaliação com prompts idênticos |
| 3 | Medir qualidade, custo por operação e latência p95 |
| 4 | Avaliar a restrição de privacidade por candidato |
| 5 | Decidir por tier, registrando em ADR |
| 6 | Reavaliar a cada trimestre ou a cada mudança relevante de oferta |

A reavaliação trimestral não é burocracia: o mercado de modelos muda rápido, e o
gateway existe justamente para tornar a troca barata. Um sistema que nunca reavalia
paga preço de ontem por qualidade de ontem.

## 5. Modelo de custo

### 5.1 Estrutura

```
Custo mensal = Infraestrutura fixa
             + Inferência variável
             + Fontes licenciadas
             + Suporte e operação
```

### 5.2 Infraestrutura (piloto, ordem de grandeza)

| Componente | Dimensionamento no piloto | Peso relativo |
|---|---|---|
| PostgreSQL gerenciado | 4 vCPU / 16 GB / 200 GB SSD + réplica | Alto |
| Compute da aplicação | 2–3 nós pequenos | Médio |
| Workers | 2–4 nós, escaláveis por fila | Médio |
| GPU para embeddings/reranker | 1 instância pequena, ou CPU com lote noturno | Médio-alto |
| Object storage | Centenas de GB | Baixo |
| Observabilidade | Stack autogerenciada | Baixo-médio |
| Rede, WAF, backup | — | Baixo |

Valores absolutos dependem de região, provedor e compromisso de uso, e por isso não
são fixados aqui. O que a engenharia entrega é o **dimensionamento**; a cotação é
exercício de dias com os números acima, e deve ser refeita quando o provedor for
escolhido.

Ponto de atenção: manter embeddings e reranker autogerenciados troca custo variável
por custo fixo. É vantajoso a partir de um volume de indexação que o piloto vai
revelar. Abaixo desse volume, serviços gerenciados podem sair mais baratos — e a
arquitetura permite as duas configurações sem mudança de código.

### 5.3 Inferência

O custo relevante não é por assinatura, é **por caso**. Modelo paramétrico:

```
custo_caso = Σ_operação  (n_chamadas × (tokens_entrada × preço_entrada
                                      + tokens_saída  × preço_saída))
```

| Operação | Chamadas por caso | Tier | Contexto típico | Peso no custo |
|---|---|---|---|---|
| Classificação documental | 1 por documento (20–80) | `classification` | Pequeno | Baixo por chamada, alto no agregado |
| Extração de fatos | 1 por documento relevante | `extraction` | Médio | Médio |
| Sugestão de teses | 2–5 | `reasoning` | Grande | Alto por chamada |
| Confronto | 2–5 | `reasoning` | Grande | Alto por chamada |
| Geração de blocos | 8–20 | `generation` | Grande | **Maior componente** |
| Verificação de suporte | 1 por afirmação material (50–200) | `verification` | Pequeno | **Segundo maior**, por volume |
| Explicação jurimétrica | 1–3 | `generation` | Pequeno | Baixo |

Duas conclusões orientam a engenharia desde o início:

1. **Verificação é cara pelo volume, não pelo tamanho.** Daí a cascata de
   [05 §4.2](05-comportamento-da-ia-e-guardrails.md): camadas 1–3 são gratuitas ou
   quase, e só o que sobra vai para a camada 4. Sem essa cascata, a verificação
   custaria mais que a geração.
2. **Geração por blocos é mais barata que geração integral com refinamento.** Cada
   bloco recupera só as evidências do seu escopo, em vez de carregar o caso inteiro em
   cada chamada.

### 5.4 Controles de custo

| Controle | Implementação |
|---|---|
| Orçamento por organização | Cota mensal com alerta em 70 % / 90 % e bloqueio configurável |
| Limite por operação | Teto de tokens por chamada e de chamadas por job |
| Roteamento por complexidade | Tarefa simples nunca usa tier caro |
| Cache | Deduplicação de chamada idêntica; cache de prompt onde o provedor suportar |
| Disjuntor de anomalia | Consumo N vezes acima da média horária pausa a organização e alerta |
| Atribuição de custo | Cada `ai_run` grava custo; agregação por caso e organização |
| Revisão semanal | Painel de custo é item fixo do ritual de métricas |

A atribuição de custo por caso não é só controle interno: é insumo para a decisão de
precificação do produto. Sem ela, o modelo comercial seria adivinhação — e o risco
"custo variável de IA compromete a margem" (§16.1) não teria como ser gerenciado.

## 6. Métricas de produto e baseline

§14.1 exige baseline antes do piloto. Sem baseline, "reduzimos o tempo em 40 %" é
opinião.

| Métrica de baseline | Como medir antes do piloto |
|---|---|
| Tempo até primeira minuta | Registro manual em amostra de casos, por 2–4 semanas |
| Tempo de revisão | Idem |
| Ciclos de revisão por peça | Contagem em amostra |
| Percentual de conteúdo reescrito | Comparação entre primeira e última versão em amostra |
| Incidência de erros materiais | Registro do revisor |
| Volume produzido | Contagem por período |

Depois do piloto, as mesmas métricas são coletadas automaticamente — e é aí que a
instrumentação de produto se paga.

**Métricas de proteção** (§14.3), acompanhadas junto com as de produtividade e com
poder de veto sobre a declaração de sucesso: correções materiais após aprovação;
referências inválidas detectadas; afirmações sem fonte; teses não aprovadas usadas;
tempo de revisão que **cai demais** — sinal de revisão superficial, não de eficiência.

A última é a mais sutil e a mais importante: um produto que reduz o tempo de revisão a
quase zero pode ter automatizado a leitura, não o trabalho. A métrica de proteção
existe para que esse resultado apareça como alerta, e não como vitória.

---

**Anterior**: [08 — Integrações](08-integracoes.md) · **Próximo**: [10 — Infraestrutura, CI/CD e ambientes](10-infraestrutura-cicd-ambientes.md)
