# Deploy do TRACE-LM — demo público (Grau B: Supabase Auth + FastAPI)

Este guia coloca o TRACE-LM no ar como **demo público com dados sintéticos**,
na arquitetura **híbrida** aprovada:

- **Supabase** (free tier) → **Auth** (identidade / login por e-mail e senha).
- **FastAPI** (todo o código e as 14 capacidades) → deploy no **Fly.io** ou
  **Render** (free tier); mantém RBAC, segregação por caso e audit log (§48/§36).
- **React/Vite** → deploy no **Vercel** ou **Netlify**.

> ⚠️ **Só dados fictícios.** O caso `CASE-DEMO` é semeado com o dataset sintético
> *Illicit Matrix* (§82). Não ingira dados reais nesta instância — o disco é
> efêmero e a nuvem é gerenciada.

```
Navegador ──login──▶ Supabase Auth ──JWT──▶ Frontend (Vercel)
                                              │  POST /auth/supabase (JWT)
                                              ▼
                                        FastAPI (Fly.io)  ── valida JWT (HS256)
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

## 1. Supabase (Auth)

1. Crie um projeto grátis em <https://supabase.com>.
2. **Authentication → Providers → Email**: habilite. Para o demo, desligue
   "Confirm email" (Authentication → Sign In / Providers) para logar na hora.
3. **Authentication → Users → Add user**: crie o(s) usuário(s) do demo
   (ex.: `demo@tracelm.app` / senha forte).
4. Anote em **Project Settings → API**:
   - `Project URL` → `VITE_SUPABASE_URL`
   - `anon public` key → `VITE_SUPABASE_ANON_KEY`
   - **JWT Settings → JWT Secret** (legacy, HS256) → `SUPABASE_JWT_SECRET`

> O papel RBAC é `viewer` por padrão (menor privilégio). Para promover alguém a
> `investigator`/`admin`, use as allowlists por e-mail (abaixo) ou um claim
> `app_metadata.tracelm_role` no usuário do Supabase.

---

## 2. Backend FastAPI (Fly.io)

Pré-requisito: [`flyctl`](https://fly.io/docs/flyctl/install/) e uma conta.

```bash
# Na raiz do repositório (onde estão Dockerfile e fly.toml):
fly launch --no-deploy          # escolha um nome único; mantenha o Dockerfile
fly secrets set \
  SUPABASE_JWT_SECRET="<legacy jwt secret>" \
  TRACELM_SECRET="<segredo-forte-aleatorio>" \
  TRACELM_CORS_ORIGINS="https://SEU-FRONT.vercel.app" \
  TRACELM_SUPABASE_ADMINS="eduarcos@gmail.com"
fly deploy
```

`fly.toml` já define `TRACELM_DEMO_SEED=1` (semeia o Illicit Matrix no boot) e o
health check em `/health`. Confirme:

```bash
curl https://SEU-APP.fly.dev/health          # {"status":"ok",...}
curl https://SEU-APP.fly.dev/auth/config      # {"supabase_enabled":true,...}
```

**Alternativa Render:** conecte o repositório; o `render.yaml` já descreve o
serviço Docker. Defina `SUPABASE_JWT_SECRET`, `TRACELM_SECRET` e
`TRACELM_CORS_ORIGINS` no dashboard (marcados `sync:false`).

---

## 3. Frontend React (Vercel)

Importe o repositório no Vercel e configure o projeto:

- **Root Directory:** `frontend`
- **Framework preset:** Vite (o `vercel.json` já cobre o rewrite de SPA)
- **Environment Variables:**
  - `VITE_API_URL` = `https://SEU-APP.fly.dev` (sem barra final)
  - `VITE_SUPABASE_URL` = `https://xxxx.supabase.co`
  - `VITE_SUPABASE_ANON_KEY` = `<anon public key>`

Faça o deploy. Depois volte ao backend e ajuste o CORS para a URL final do
frontend:

```bash
fly secrets set TRACELM_CORS_ORIGINS="https://SEU-FRONT.vercel.app"
```

**Alternativa Netlify:** o `frontend/netlify.toml` já define base, build e o
redirect de SPA; basta cadastrar as mesmas `VITE_*`.

---

## 4. Validação de ponta a ponta

1. Abra a URL do frontend → a tela de login mostra **"Entrar com Supabase"**.
2. Entre com o usuário criado no passo 1 → o Supabase autentica e o FastAPI
   troca o JWT por uma sessão TRACE-LM.
3. Vá em **CASE**: o caso `CASE-DEMO` já traz o dataset *Illicit Matrix*.
4. Explore as abas (DATA, ENTITIES, EXPLORE, ASSISTANT, AUDIT…). Como `viewer`,
   é somente leitura; promova o seu e-mail a `investigator` para transformar.

O botão **"Usar usuário/senha local (admin)"** mantém o login clássico (§48)
para o `admin` semeado — útil para gestão de usuários e verificação de
integridade.

---

## Variáveis de ambiente (resumo)

| Onde | Variável | Papel |
|------|----------|-------|
| Backend | `SUPABASE_JWT_SECRET` | valida o JWT do Supabase (HS256). Liga a ponte. |
| Backend | `TRACELM_SECRET` | assina os tokens de sessão TRACE-LM (§48). |
| Backend | `TRACELM_CORS_ORIGINS` | origem(ns) do frontend liberada(s). |
| Backend | `TRACELM_SUPABASE_ADMINS` / `_INVESTIGATORS` | allowlists de papel por e-mail. |
| Backend | `TRACELM_DEMO_SEED` / `TRACELM_DEMO_CASE` | semeia o caso sintético. |
| Frontend | `VITE_API_URL` | URL do backend FastAPI. |
| Frontend | `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` | cliente Supabase (chave anônima). |

> Segurança: `VITE_*` vão para o bundle público — use só a **anon key**, nunca a
> `service_role`. O `SUPABASE_JWT_SECRET` fica **apenas no backend**.

---

## Limites conhecidos deste demo

- **Disco efêmero:** o SQLite é reconstruído a cada boot; o caso de demo é
  re-semeado. Nada persiste — é intencional para um showcase.
- **Cold start:** no free tier a primeira requisição após ociosidade pode
  demorar alguns segundos (a máquina "acorda").
- **Export (report.md / export.zip):** abrem por navegação direta e não enviam
  o header de sessão; num backend remoto podem exigir a sessão. Para o demo,
  use as demais abas; o pacote continua disponível localmente.

## Evolução para Grau C (Postgres gerenciado)

Trocar o SQLite pelo Postgres do Supabase exige reescrever `app/core/db.py` e o
acesso a dados dos módulos (placeholders `?`→`%s`, `AUTOINCREMENT`→`SERIAL`,
remover `PRAGMA`, pool de conexões). É um refactor grande e sem ganho para um
demo sintético; documentado aqui como caminho, não como pré-requisito.
