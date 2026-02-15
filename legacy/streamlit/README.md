# TireControl Python

## Estado atual
- App principal em Streamlit (`main.py`) no modelo de acoes operacionais.
- API em FastAPI (`api.py`).
- Banco em Supabase/PostgreSQL.

## Migracao de schema
Arquivo:
- `migrations/2026-02-12_schema_alignment_v1.sql`

A migracao alinha schema com codigo atual e cria o modelo canonico de eventos.

## Modelo de acoes (eventos)
Tabelas:
- `eventos_operacionais`
- `eventos_operacionais_itens`

Eventos em uso:
- `COLOCAR_PNEU`
- `TIRAR_PNEU`
- `TROCAR_POSICAO`
- `ENVIAR_RECAPAGEM`
- `RETORNO_RECAPAGEM`
- `AJUSTE_GESTOR`

## Consistencia automatica
Implementado no backend:
- bloqueio de estados invalidos nas acoes transacionais
- reconciliacao segura de inconsistencias deterministicas
- trilha de auditoria para ajustes de gestor

## Observacoes
- Mantida compatibilidade legada com `movimentacoes`.
- Escrita canonica em eventos habilitada em paralelo.
- Fluxo de scan por foto integrado no app (`camera_input`/upload + API).

## Configuracao do scan por foto
Edge Function Supabase:
- caminho: `supabase/functions/scan-pneu/index.ts`
- deploy: `supabase functions deploy scan-pneu`
- variaveis da function:
  - `OPENAI_API_KEY`
  - `OPENAI_VISION_MODEL` (opcional, default `gpt-4o-mini`)

App Streamlit (`acoes_operacionais.py`):
- `SUPABASE_SCAN_FUNCTION_URL`: URL da edge function (ex: `https://<project-ref>.supabase.co/functions/v1/scan-pneu`)
- `SUPABASE_ANON_KEY`: anon key para autenticar chamada na function
- fallback legado opcional: `TYRECONTROL_SCAN_API_URL` / `TYRECONTROL_SCAN_API_KEY`

## Fluxo claro de uso (app)
Entrada unica:
1. Abrir app e fazer login.
2. Selecionar cliente (admin) ou usar cliente vinculado (demais perfis).
3. Na tela `Sistema de Acoes`, escolher a area:
   - `Operacao` para executar acoes de campo
   - `Gestao` para consistencia e perguntas (admin/gerente)
4. Escanear/identificar pneu.
5. Confirmar a acao.

Acoes principais:
1. `Tirar pneu`: motivo -> confirmar.
2. `Colocar pneu`: veiculo/posicao -> confirmar.
3. `Trocar posicao`: pneu A e B -> confirmar.
4. `Enviar recapagem`: lote -> confirmar.
5. `Ver frota`: consulta visual.

Regras de uso:
1. Fluxo orientado por reconhecimento: escanear antes de confirmar acao.
2. Troca de posicao exige leitura previa dos dois pneus.
3. Acoes exibidas mudam por perfil (`motorista`, `borracheiro`, `gerente`, `admin`).
4. Modo rapido para `motorista/operador`: foco em `escanear -> confirmar`.
5. A tela de scan mostra `proximo passo recomendado` com atalho de execucao.

Para gestor:
1. Entrar na area `Gestao`.
2. Ver painel `Saude dos dados operacionais`.
3. Aplicar `correcao segura` quando necessario.
4. Consultar respostas prontas em `Respostas para gestor`.
