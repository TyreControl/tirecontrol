# TireControl Web (Next.js + Supabase)

Frontend web do TireControl, migrando o fluxo operacional do Streamlit para Supabase-first.

## Rotas atuais
- `/login`: login/signup com Supabase Auth
- `/`: hub principal por perfil (`role`)
- `/oficina`: fluxo borracharia (scan + acao operacional)
- `/trucks`: controle de frota (caminhoes)
- `/gestao`: painel resumido da gestao
- `/setup`: cadastro inicial e vinculo de empresa

## Variaveis de ambiente
Em `.env.local`:

```bash
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
```

## Banco / Migracoes necessarias
Aplicar no Supabase:
- `infra/supabase/migrations/2026-02-12_schema_alignment_v1.sql`
- `infra/supabase/migrations/2026-02-12_web_supabase_profiles_rpc_v1.sql`
- `infra/supabase/migrations/2026-02-12_web_supabase_rpc_v2.sql`
- `infra/supabase/migrations/2026-02-12_web_supabase_rpc_v3_retorno.sql`

Essa segunda migration cria:
- tabela `profiles` (id do `auth.users` + `cliente_id` + `role`)
- politicas RLS iniciais multi-tenant
- RPCs operacionais:
  - `rpc_tirecontrol_tirar_pneu(...)`
  - `rpc_tirecontrol_colocar_pneu(...)`
  - `rpc_tirecontrol_trocar_posicao(...)`
  - `rpc_tirecontrol_enviar_recapagem(...)`
  - `rpc_tirecontrol_retorno_recapagem(...)`

## Rodar local
```bash
npm install
npm run dev
```

## Status desta etapa
- Web app ja alinhado ao schema real (`clientes`, `caminhoes`, `pneus`)
- Navegacao por perfil ativa
- Scan por foto usando Edge Function `scan-pneu`
- Primeira acao transacional via RPC pronta (`tirar pneu`)
