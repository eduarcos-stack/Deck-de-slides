# 07 — Segurança e privacidade

## 1. Modelo de ameaças

Threat model resumido, no formato ativo → ameaça → controle. A ordem reflete impacto,
não probabilidade: o pior evento possível neste produto é vazamento de conteúdo entre
clientes, porque atinge sigilo profissional e é irreversível.

| # | Ativo | Ameaça | Controles |
|---|---|---|---|
| T1 | Documentos de um cliente | Recuperação cruzada entre organizações ou casos | Filtro pré-busca, RLS forçada, chave de tenant no índice, suíte adversarial em CI |
| T2 | Documentos sigilosos | Envio a serviço externo não autorizado | Política por organização, lista de permissão de egresso, redação, registro por chamada |
| T3 | Credenciais e chaves de API | Vazamento por log, código ou trace | Secrets Manager, redação estruturada, varredura de segredos no CI |
| T4 | Trilha de auditoria | Alteração para ocultar ação | Append-only, `REVOKE UPDATE/DELETE`, encadeamento de hash, exportação WORM |
| T5 | Contexto do modelo | Injeção via documento ingerido | Separação instrução/dados, saída estruturada, verificador, ausência de ferramentas destrutivas |
| T6 | Base institucional | Contaminação com conteúdo não aprovado | Promoção humana explícita, curadoria, validade, retirada imediata |
| T7 | Sessões de usuário | Sequestro de sessão, escalonamento de papel | OIDC com PKCE, tokens curtos, MFA, verificação de papel no servidor |
| T8 | Object storage | Acesso direto indevido | Bucket privado, URLs assinadas de curta duração, SSE-KMS, sem listagem pública |
| T9 | Barreiras éticas | Acesso por membro em conflito | Negação explícita que vence concessão, aplicada em ABAC e RLS |
| T10 | Dados pessoais em decisões coletadas | Tratamento sem base legal | Minimização, anonimização conforme política, exclusão de segredo de justiça, parecer do DPO |
| T11 | Backups | Restauração com dados de outra organização | Backup criptografado, teste de restauração, verificação de isolamento pós-restore |
| T12 | Custo de inferência | Abuso ou laço infinito consumindo orçamento | Cotas por organização, limite por job, disjuntor, alerta de anomalia |

## 2. Autenticação

| Item | Decisão |
|---|---|
| Protocolo | OIDC (Authorization Code + PKCE) |
| Provedor | Keycloak autogerenciado ([ADR-0008](../adr/0008-identidade-com-keycloak-oidc.md)) |
| MFA | Obrigatório para papéis `socio`, `revisor` e `admin`; recomendado para os demais |
| SSO corporativo | SAML/OIDC federado, por organização |
| Sessão | Access token de 15 min; refresh rotativo com detecção de reuso |
| Sessão administrativa | 30 min de inatividade; reautenticação para operações críticas |
| Serviço a serviço | mTLS interno + tokens de curta duração |

## 3. Autorização

### 3.1 Modelo ABAC

Papel sozinho não resolve: a permissão depende do papel **e** do vínculo com o caso,
do nível de sigilo, do estado do recurso e das barreiras éticas. Daí ABAC e não RBAC
puro.

```python
@dataclass(frozen=True)
class AccessRequest:
    subject: UserContext      # org, id, papel, grupos
    action: str               # 'thesis.approve', 'draft.export', ...
    resource: ResourceRef     # tipo, id, org, matter, sigilo, estado
    context: RequestContext   # ip, hora, mfa_verificado

def authorize(req: AccessRequest) -> Decision:
    """Ordem de avaliação:
       1. negações explícitas (barreiras éticas)  -> DENY, definitivo
       2. isolamento organizacional               -> DENY se divergir
       3. pertencimento ao caso                   -> DENY se ausente e o recurso for do caso
       4. capacidade do papel para a ação         -> DENY se ausente
       5. condições de estado do recurso          -> DENY se incompatível
       6. condições de contexto (MFA em ação crítica)
       -> ALLOW somente se todas passarem
    """
```

Negação vem primeiro e é definitiva. Nenhuma concessão posterior a reverte.

### 3.2 Matriz de permissões

Implementação do Anexo A da proposta. "Config." indica comportamento configurável por
organização, com o padrão indicado entre parênteses.

| Ação | Sócio | Associado | Assistente | Revisor | Admin |
|---|---|---|---|---|---|
| Criar caso | Sim | Sim | Config. (não) | Não | Não |
| Ver caso autorizado | Sim | Sim | Sim | Sim | Sim¹ |
| Enviar documentos | Sim | Sim | Sim | Config. (sim) | Não |
| Confirmar fatos | Sim | Sim | Limitado² | Sim | Não |
| Aprovar tese | Sim | Config. (não) | Não | Sim | Não |
| Gerar minuta | Sim | Sim | Limitado³ | Sim | Não |
| Aprovar peça final | Sim | Não | Não | Sim | Não |
| Exportar peça | Sim | Config. (não) | Não | Config. (sim) | Não |
| Promover ativo interno | Sim | Config. (não) | Não | Config. (não) | Não |
| Administrar usuários | Não | Não | Não | Não | Sim |
| Consultar auditoria | Config. (sim) | Não | Não | Config. (não) | Sim |
| Configurar fontes e prompts | Config. (não) | Não | Não | Não | Sim |

¹ O administrador vê a **existência** e os metadados do caso para gerenciar acesso; o
conteúdo exige pertencimento explícito. Separar administração de acesso do acesso ao
conteúdo é o que impede que a conta administrativa seja um bypass universal do sigilo.

² Fatos de baixa criticidade; fatos que sustentam tese exigem papel superior.

³ Pode disparar geração em rascunho, não pode submeter para revisão.

## 4. Criptografia

| Camada | Controle |
|---|---|
| Em trânsito (externo) | TLS 1.3, HSTS, certificados gerenciados |
| Em trânsito (interno) | mTLS entre serviços |
| Em repouso — banco | Criptografia de volume + KMS |
| Em repouso — objetos | SSE-KMS; chave por organização no tier dedicado |
| Backups | Criptografados com chave distinta da de produção |
| Segredos | Secrets Manager, rotação automática, injeção em runtime |
| Campos sensíveis | Criptografia em nível de aplicação para credenciais de integração |

Chave por organização não é apenas defesa criptográfica: viabiliza *crypto-shredding*
— destruir a chave torna os dados irrecuperáveis — o que simplifica enormemente a
comprovação de eliminação ao término de um contrato.

## 5. Política de saída de conteúdo

O controle mais específico deste produto e o que responde diretamente a "proteção
contra envio de conteúdo confidencial a serviços não autorizados" (§10.1).

```python
class EgressPolicy(BaseModel):
    org_id: UUID
    allow_external_llm: bool = False
    allowed_providers: list[str] = []
    allowed_regions: list[str] = []
    require_zero_retention: bool = True
    max_confidentiality_level: Literal["standard", "restricted"] = "standard"
    allow_external_ocr: bool = False
    allow_external_rerank: bool = False
```

Toda chamada que atravesse o perímetro passa por `check_egress()`, que avalia o nível
de sigilo do conteúdo contra a política da organização. Bloqueio gera
`outcome = policy_blocked` no `ai_run`, evento de auditoria e mensagem clara ao
usuário — nunca falha silenciosa.

Complementos:

- Nível de rede: workers só alcançam destinos em lista de permissão; sem rota para a
  internet aberta
- Contratos com provedores devem prever retenção zero e não uso para treinamento
- Casos marcados como `ethical_wall` ou `restricted` operam apenas com modelos
  autogerenciados, salvo autorização expressa e registrada da organização

## 6. Privacidade e LGPD

### 6.1 Mapeamento

| Categoria | Titulares | Finalidade | Base legal (a confirmar pelo DPO) |
|---|---|---|---|
| Dados de usuários da plataforma | Advogados e equipe | Operação do serviço | Execução de contrato |
| Conteúdo de documentos de casos | Clientes e terceiros mencionados | Prestação de serviço jurídico pelo escritório | Escritório é controlador; PROJUR é operador |
| Decisões coletadas | Partes dos processos | Análise jurimétrica | Requer análise específica: publicidade dos atos, legítimo interesse, minimização |
| Telemetria e logs | Usuários | Segurança e operação | Legítimo interesse |

**Papel de cada parte.** O escritório é controlador do conteúdo dos casos; o PROJUR é
operador. Isso precisa estar no contrato e tem consequências técnicas: capacidade de
exportar, eliminar e comprovar eliminação a pedido do controlador, e proibição de uso
do conteúdo para qualquer finalidade própria.

A base jurimétrica é o ponto que mais exige parecer. Decisões judiciais são públicas em
regra, o que não converte automaticamente qualquer tratamento em lícito — sobretudo
tratamento massivo, com enriquecimento e retenção. A recomendação técnica é
**minimização agressiva**: armazenar o que os indicadores exigem, pseudonimizar
identificadores de pessoas físicas nas camadas analíticas, e manter inteiro teor apenas
onde o drill-down é necessário, sob controle de acesso.

### 6.2 Controles

| Controle | Implementação |
|---|---|
| Minimização | Coleta apenas do necessário; análise de necessidade por campo |
| Retenção | Política por organização e por tipo ([03 §7](03-modelo-de-dados.md)) |
| Eliminação | Job dedicado, com registro do que foi eliminado |
| Portabilidade | Exportação completa dos dados da organização em formato aberto |
| Segregação de ambientes | Dados reais **nunca** em desenvolvimento ou homologação |
| Massa de teste | Sintética ou anonimizada irreversivelmente |
| Uso para treinamento | Proibido por padrão; exige autorização explícita e governança |
| Subprocessadores | Registro público, notificação de alteração, avaliação prévia |
| Transferência internacional | Avaliada por fornecedor; preferência por região brasileira |

## 7. Trilha de auditoria

Ações que **sempre** geram evento: autenticação e falha de autenticação; criação e
alteração de caso; concessão e revogação de acesso; criação de barreira ética; upload,
visualização, download e exclusão de documento; execução de IA; aprovação e rejeição
de tese; criação de versão de minuta; transição de estado; exportação; promoção e
retirada de ativo; alteração de configuração, prompt ou modelo; consulta jurimétrica;
consulta à própria auditoria.

Propriedades: append-only com privilégios revogados; encadeamento de hash detectando
alteração retroativa; emissão na mesma transação da mutação; retenção de 5 anos
configurável; exportação diária para storage com Object Lock; consulta restrita a
papéis autorizados e ela própria auditada.

Detalhes em [ADR-0007](../adr/0007-auditoria-append-only-com-encadeamento-de-hash.md).

## 8. Segurança no ciclo de desenvolvimento

| Fase | Controle |
|---|---|
| Design | ADR de mudança estrutural passa por revisão de segurança |
| Código | Revisão obrigatória; `authz`, `retrieval` e `audit` exigem revisor designado |
| CI | SAST, varredura de segredos, verificação de dependências, licenças |
| Testes | Suíte adversarial de isolamento; testes de autorização negativa |
| Dependências | Renovate; severidade alta bloqueia merge |
| Imagens | Base mínima, scan, assinatura, SBOM |
| Ambientes | Sem dados reais fora de produção |
| Pré-produção | Pentest antes do piloto com dados reais e antes do GA |
| Operação | Alertas de anomalia; runbook de incidente; simulação semestral |

### 8.1 Suíte adversarial de isolamento

O teste que protege a invariante I-1. Roda em cada PR e **bloqueia o merge**:

```python
def test_cross_org_retrieval_is_impossible(seeded_two_orgs):
    org_a, org_b = seeded_two_orgs
    for query in ADVERSARIAL_QUERIES:      # inclui termos exclusivos de org_b
        results = retrieve(ctx=user_ctx(org_a), query=query, k=50)
        assert all(r.org_id == org_a.id for r in results)
        assert not any(r.chunk_id in org_b.chunk_ids for r in results)

def test_ethical_wall_blocks_member(seeded_matter_with_wall):
    ...

def test_rls_blocks_direct_query_without_context(db_session_without_context):
    with pytest.raises(NoRowsReturned):
        db_session_without_context.execute(select(Matter)).one()
```

O terceiro teste é o mais valioso: verifica que a proteção do banco funciona **sem**
que a aplicação faça nada certo. É a definição operacional de defesa em profundidade.

## 9. Resposta a incidentes

| Fase | Ação |
|---|---|
| Detecção | Alertas de anomalia de acesso, egresso bloqueado, falha de integridade da auditoria |
| Classificação | Severidade por impacto sobre sigilo e dados pessoais |
| Contenção | Revogação de sessões, rotação de segredos, isolamento de organização afetada |
| Investigação | Trilha de auditoria + traces; preservação de evidências |
| Notificação | Ao escritório afetado e, quando aplicável, à ANPD, nos prazos legais |
| Correção | Causa raiz, correção, teste de regressão que impeça recorrência |
| Aprendizado | Post-mortem sem culpabilização, com ação registrada |

Vazamento entre organizações é severidade máxima por definição, independentemente do
volume: uma linha de outro cliente já é violação de sigilo profissional.

---

**Anterior**: [06 — Jurimetria](06-jurimetria.md) · **Próximo**: [08 — Integrações](08-integracoes.md)
