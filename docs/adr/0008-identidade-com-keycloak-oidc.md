# ADR-0008 — Identidade com Keycloak (OIDC) autogerenciado

- **Status**: Aceito, com revisão prevista
- **Data**: 29/07/2026
- **Decisor**: Tech Lead + Segurança

## Contexto

O PROJUR precisa de: autenticação multi-organização, MFA obrigatório para papéis
críticos, sessões curtas com refresh rotativo, e — em vendas B2B para escritórios de
médio e grande porte — **SSO corporativo via SAML ou OIDC federado**, que costuma ser
requisito de compra, não diferencial.

Há três caminhos: implementar autenticação própria, usar um IdP gerenciado
(Auth0, Clerk, WorkOS, Cognito) ou autogerenciar um IdP de código aberto.

## Decisão

**Keycloak autogerenciado**, na mesma região da aplicação, como provedor OIDC, com
federação SAML/OIDC por organização para SSO corporativo.

## Justificativa

**Autenticação própria está fora de questão.** Implementar OIDC, MFA, rotação de
refresh token com detecção de reuso e federação SAML corretamente é trabalho
especializado, com consequências graves quando malfeito. Não é onde este time deve
gastar sprints.

**Residência de dados.** Identidades de advogados e a associação usuário-organização
são dados pessoais de clientes B2B. Mantê-los na mesma região e sob o mesmo perímetro
simplifica a análise de LGPD e a avaliação de subprocessadores — que é exatamente o que
§10.2 pede.

**SSO corporativo sem custo por conector.** Provedores gerenciados costumam cobrar
significativamente por conexão SAML empresarial. Como SSO tende a ser requisito nas
contas que mais pagam, esse custo cresce junto com a receita — no pior lugar possível.
Keycloak faz federação SAML sem custo marginal por conexão.

**Portabilidade.** Padrões abertos, sem lock-in de fornecedor de identidade.
Migrar identidades entre IdPs é notoriamente doloroso; começar em padrão aberto reduz o
risco.

## Consequências

**Positivas**: sem custo por usuário ou por conexão SAML; dados de identidade no
perímetro; padrões abertos; federação flexível por organização; MFA, políticas de senha
e temas configuráveis.

**Negativas**: **é mais um sistema para operar** — atualizar, monitorar, fazer backup,
manter alta disponibilidade. Keycloak tem curva de aprendizado real e configuração
extensa. Uma indisponibilidade dele derruba o login de todos.

**Custo estimado**: 1 a 1,5 pessoa-semana de configuração inicial, mais operação
contínua. Requer runbook próprio e alta disponibilidade desde o piloto.

## Mitigações

- Keycloak em alta disponibilidade com ao menos duas réplicas
- Banco próprio, com backup e teste de restauração
- Configuração via IaC (realms, clientes, papéis, fluxos) — nunca por console manual
- Sessões de 15 minutos com refresh rotativo, para que uma indisponibilidade curta não
  derrube quem já está trabalhando
- Runbook de indisponibilidade do IdP
- Atualização de versão tratada como release, com ensaio em homologação

## Gatilho de revisão

Reavaliar se: a operação do Keycloak consumir mais de meia pessoa-semana por mês; ou se
uma indisponibilidade dele causar incidente relevante no piloto; ou se o produto
precisar de recursos de identidade B2B (organizações, convites, diretório) que sejam
caros de construir sobre o Keycloak e prontos em provedores especializados.

O custo da reversão é moderado: as identidades federadas por SSO continuam no IdP do
cliente; apenas as contas locais precisariam migrar.

## Alternativas consideradas

| Alternativa | Por que não agora |
|---|---|
| Auth0 / Okta | Excelente experiência de desenvolvimento; custo cresce com usuários e com conexões enterprise; dados fora do perímetro |
| WorkOS | Muito bom especificamente em SSO B2B; ainda assim, identidades fora do perímetro e custo por conexão |
| Clerk | Ótimo para SaaS B2C e times pequenos; recursos B2B e SAML menos maduros para este caso |
| Cognito | Barato e integrado à nuvem; ergonomia limitada, federação SAML trabalhosa, forte lock-in |
| Autenticação própria | Risco de segurança desproporcional; sem SSO corporativo sem esforço grande |
