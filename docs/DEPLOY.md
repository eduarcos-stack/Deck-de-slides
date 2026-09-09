# Deploy do TRACE-LM — demo público (Grau B: Supabase Auth + FastAPI)

Este guia coloca o TRACE-LM no ar como **demo público com dados sintéticos**,
na arquitetura **híbrida** aprovada:

- **Supabase** (free tier) → **Auth** (identidade / login por e-mail e senha).
- **FastAPI** (todo o código e as 14 capacidades) → deploy no **Render**
  (free tier); mantém RBAC, segregação por caso e audit log (§48/§36).
- **React/Vite** → deploy no **Vercel**.

> Este documento reflete um deploy **real** já executado: Render (web-UI) para o
> backend, Vercel para o frontend, e um projeto Supabase com o **sistema novo de
> chaves** (assinatura **ES256** via JWKS). O deploy alternativo por CLI (Fly.io)
> e por Netlify continua suportado pelos arquivos `fly.toml` / `netlify.toml`,
> descrito ao final.

> ⚠️ **Só dados fictícios.** O caso `CASE-DEMO` é semeado com o dataset sintético
> *Illicit Matrix* (§82). Não ingira dados reais nesta instância — o disco é
> efêmero e a nuvem é gerenciada.

```
Navegador ──login──▶ Supabase Auth ──JWT(ES256)──▶ Frontend (Vercel)
                                                     │  POST /auth/supabase (JWT)
                                                     ▼
                                        FastAPI (Render) ── valida JWT
                                          │   HS256 (segredo legado)  ou
                                          │   ES256/RS256 via JWKS (chave pública)
                                          │  emite sessão TRACE-LM (HMAC)
                                          ▼
                                   RBAC · segregação · audit · SQLite (efêmero)
```

**Por que híbrido e não Postgres do Supabase?** O núcleo é fortemente acoplado
ao SQLite; para um demo sintético, reescrever a camada de dados não traz ganho.
O Supabase entra como **Auth gerenciado**; o FastAPI segue como autoridade de
autorização. Migrar para o Postgres do Supabase fica documentado como evolução
(Grau C) no fim deste arquivo.

---

## 0. Como o backend valida o token (HS256 × ES256)

O Supabase pode assinar os tokens de usuário de dois jeitos, e o backend
suporta **os dois** (`app/modules/supabase_auth.py`):

- **HS256 (segredo compartilhado legado)** — projetos antigos, ou novos com as
  chaves legadas ativas. Validação com a stdlib pura; exige `SUPABASE_JWT_SECRET`.
- **ES256 / RS256 / EdDSA (JWT Signing Keys, sistema novo)** — projetos recentes
  do Supabase. Validação pela **chave pública** do projeto, obtida do **JWKS**;
  exige `SUPABASE_URL` (o backend monta `…/auth/v1/.well-known/jwks.json`).

O algoritmo é escolhido automaticamente pelo header do token. **Na dúvida,
defina as duas variáveis** (`SUPABASE_JWT_SECRET` **e** `SUPABASE_URL`) — o
backend usa a que o token exigir. Se você vir no login o erro
`algoritmo não suportado: ES256`, falta o `SUPABASE_URL`.

> Como saber qual o seu caso? Se a página de API Keys do seu projeto mostra
> chaves **`publishable`/`secret`** (formato `sb_publishable_…`), é o sistema
> novo → seus tokens de usuário são **ES256** → **`SUPABASE_URL` é obrigatório**.

---

## 1. Supabase (Auth)

1. Crie um projeto grátis em <https://supabase.com> (região mais próxima).
2. **Authentication → Providers → Email**: habilite. Para o demo, desligue
   **"Confirm email"** para logar na hora.
3. **Authentication → Users → Add user**: crie o(s) usuário(s) do demo
   (e-mail + senha forte).
4. Colete, em **Project Settings → API** e **API Keys**:
   - `Project URL` → vira `VITE_SUPABASE_URL` **e** `SUPABASE_URL`.
   - Chave pública do cliente → vira `VITE_SUPABASE_ANON_KEY`. Serve tanto a
     **`publishable key`** nova (`sb_publishable_…`) quanto a **`anon`** legada.
   - **JWT Secret (HS256 legado)** → `SUPABASE_JWT_SECRET`. Fica em
     **Project Settings → JWT Keys** (ou `.../settings/jwt`), botão **Reveal**.
     É uma **string curta sem pontos** — **não** é um token `eyJ…` nem um UUID.

> Como conferir se o `SUPABASE_JWT_SECRET` está certo sem subir nada: a chave
> `service_role` legada é um JWT HS256 assinado com esse segredo. Recalcule a
> assinatura HMAC-SHA256 do `service_role` com o segredo candidato e compare —
> se bater, é o segredo correto. (No sistema novo, mesmo com o segredo certo, os
> tokens de **usuário** ainda são ES256; por isso o `SUPABASE_URL` é o que faz o
> login funcionar.)

> O papel RBAC é `viewer` por padrão (menor privilégio). Para promover alguém a
> `investigator`/`admin`, use as allowlists por e-mail (abaixo) ou um claim
> `app_metadata.tracelm_role` no usuário do Supabase.

---

## 2. Backend FastAPI no Render (interface web)

Sem instalar nada — tudo pelo site.

1. <https://render.com> → **Sign in with GitHub** (conta que tem o repositório).
2. **New + → Blueprint** → selecione o repo e a branch **`main`**. O Render lê o
   **`render.yaml`** e propõe o serviço Docker **`tracelm-api`**.
3. Preencha os valores dos segredos (os campos `sync:false` do blueprint):
   - `SUPABASE_JWT_SECRET` = *(o JWT Secret legado)*
   - `TRACELM_SECRET` = *(um segredo forte, ex.: `python -c "import secrets;print(secrets.token_urlsafe(48))"`)*
   - `TRACELM_CORS_ORIGINS` = *(deixe vazio agora; preenche na Fase 4)*
4. **Apply**. O primeiro build leva alguns minutos (instala polars, pyjwt etc.).
5. **Adicione a variável do JWKS** (não vem no blueprint) — serviço → **Environment**
   → **Add**:
   - `SUPABASE_URL` = `https://SEU-PROJETO.supabase.co`
   - (opcional) `TRACELM_SUPABASE_INVESTIGATORS` = e-mail do seu usuário, para
     entrar como *investigator* em vez de *viewer*.
   - Salve com **"Save, rebuild, and deploy"**.

`render.yaml` já define `TRACELM_DEMO_SEED=1` (semeia o Illicit Matrix no boot),
`TRACELM_DEMO_CASE=CASE-DEMO` e o health check em `/health`. Confirme no navegador:

```
https://SEU-APP.onrender.com/health        # {"status":"ok","principle":"provenance-first"}
https://SEU-APP.onrender.com/auth/config   # {"supabase_enabled":true,"demo_case":"CASE-DEMO"}
```

---

## 3. Frontend React no Vercel (interface web)

1. <https://vercel.com> → **Sign in with GitHub** → **Add New… → Project** →
   **Import** o repositório.
2. Na configuração:
   - **Root Directory:** **`frontend`** ← essencial (senão builda a raiz).
   - **Framework Preset:** **Vite** (detectado; o `vercel.json` cobre o SPA).
3. **Environment Variables** (as `VITE_*` são "assadas" no build, então precisam
   existir **antes** do deploy — adicione em **Settings → Environments → Production**):
   - `VITE_API_URL` = `https://SEU-APP.onrender.com` (sem barra final)
   - `VITE_SUPABASE_URL` = `https://SEU-PROJETO.supabase.co`
   - `VITE_SUPABASE_ANON_KEY` = `sb_publishable_…` (ou a `anon` legada)
4. **Deploy**. Se você adicionar/alterar variáveis depois, refaça o build:
   **Deployments → ⋯ → Redeploy** (o Vite só as lê num build novo).

> Sinal de que as `VITE_*` entraram: a tela de login mostra
> **"Acesso restrito · provenance-first · Supabase Auth"**, o campo **E-mail** e
> o botão **"Entrar com Supabase"**. Se aparecer só "Usuário/Senha", as variáveis
> não entraram no build — adicione-as e **Redeploy**.

---

## 4. Validação de ponta a ponta e fechamento do CORS

1. Abra a URL do Vercel → login com o usuário do Supabase (**Entrar com Supabase**).
   - `algoritmo não suportado: ES256` → falta `SUPABASE_URL` no Render.
   - `Invalid login credentials` → e-mail/senha do Supabase (ou "Confirm email" ligado).
2. Após entrar (papel `viewer`), na aba **CASE** troque o `case_id` para
   **`CASE-DEMO`** (ou vá em **DATA**) para ver o dataset *Illicit Matrix*.
3. **Feche o CORS:** Render → **Environment** →
   `TRACELM_CORS_ORIGINS` = `https://SEU-FRONT.vercel.app` → **Save, rebuild, and deploy**.
   (Com a variável vazia, o backend libera `*` — bom só para o teste inicial.)

O botão **"Usar usuário/senha local (admin)"** mantém o login clássico (§48)
para o `admin` semeado — útil para gestão de usuários e verificação de integridade.

---

## Variáveis de ambiente (resumo)

| Onde | Variável | Papel |
|------|----------|-------|
| Backend | `SUPABASE_URL` | localiza o JWKS para validar tokens **ES256/RS256** (sistema novo). |
| Backend | `SUPABASE_JWT_SECRET` | valida tokens **HS256** (segredo legado). |
| Backend | `TRACELM_SECRET` | assina os tokens de sessão TRACE-LM (§48). |
| Backend | `TRACELM_CORS_ORIGINS` | origem(ns) do frontend liberada(s). Vazio = `*`. |
| Backend | `TRACELM_SUPABASE_ADMINS` / `_INVESTIGATORS` | allowlists de papel por e-mail. |
| Backend | `TRACELM_DEMO_SEED` / `TRACELM_DEMO_CASE` | semeia o caso sintético (do `render.yaml`). |
| Frontend | `VITE_API_URL` | URL do backend FastAPI. |
| Frontend | `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` | cliente Supabase (chave pública). |

> Segurança: `VITE_*` vão para o bundle público — use só a **publishable/anon
> key**, nunca a **`secret`/`service_role`**. `SUPABASE_JWT_SECRET` fica **apenas
> no backend**. Se algum segredo circular por um canal não confiável (chat,
> e-mail), **rotacione o JWT Secret** no Supabase (Settings → JWT) ao final — o
> login ES256/JWKS nem depende dele.

---

## Limites conhecidos deste demo

- **Disco efêmero:** o SQLite é reconstruído a cada boot; o caso de demo é
  re-semeado. Nada persiste — é intencional para um showcase.
- **Cold start:** no free tier a primeira requisição após ociosidade pode
  demorar alguns segundos (a máquina "acorda").
- **JWKS exige rede:** a validação ES256 busca a chave pública do Supabase uma
  vez (com cache). É a única saída de rede na autenticação; só chaves **públicas**
  trafegam, nenhum segredo sai (compatível com o espírito §47).
- **Export (report.md / export.zip):** abrem por navegação direta e não enviam
  o header de sessão; num backend remoto podem exigir a sessão. Para o demo,
  use as demais abas; o pacote continua disponível localmente.

---

## Deploy alternativo (Fly.io por CLI / Netlify)

Os arquivos `fly.toml` e `frontend/netlify.toml` continuam no repositório.

**Backend no Fly.io** (na raiz do repo):

```bash
fly launch --no-deploy          # escolha um nome único; mantenha o Dockerfile
fly secrets set \
  SUPABASE_URL="https://SEU-PROJETO.supabase.co" \
  SUPABASE_JWT_SECRET="<jwt secret legado>" \
  TRACELM_SECRET="<segredo-forte>" \
  TRACELM_CORS_ORIGINS="https://SEU-FRONT.vercel.app"
fly deploy
```

**Frontend no Netlify:** o `frontend/netlify.toml` já define base (`frontend`),
build e o redirect de SPA; basta cadastrar as mesmas `VITE_*`.

---

## Evolução para Grau C (Postgres gerenciado)

Trocar o SQLite pelo Postgres do Supabase exige reescrever `app/core/db.py` e o
acesso a dados dos módulos (placeholders `?`→`%s`, `AUTOINCREMENT`→`SERIAL`,
remover `PRAGMA`, pool de conexões). É um refactor grande e sem ganho para um
demo sintético; documentado aqui como caminho, não como pré-requisito.
