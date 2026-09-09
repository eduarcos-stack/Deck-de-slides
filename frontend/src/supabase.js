// Cliente do Supabase Auth (deploy Grau B). A identidade é gerida pelo
// Supabase; a AUTORIZAÇÃO (RBAC, segregação, auditoria) continua no FastAPI,
// que valida o JWT e emite a sessão TRACE-LM. Ver docs/DEPLOY.md.
//
// A ponte só liga quando as duas variáveis estão presentes no build. Sem elas,
// o app opera apenas com o login clássico (§48) — modo local-first padrão.
import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const supabaseEnabled = Boolean(url && anonKey);
export const supabase = supabaseEnabled ? createClient(url, anonKey) : null;
