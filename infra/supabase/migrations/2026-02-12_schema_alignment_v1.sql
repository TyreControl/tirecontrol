-- TireControl Schema Alignment V1
-- Date: 2026-02-12
-- Goal: Align DB schema with current Python/FastAPI code and prepare event-driven model.

BEGIN;

-- 1) Add missing tenant keys used by current code
ALTER TABLE public.clientes
  ADD COLUMN IF NOT EXISTS nome_fantasia text,
  ADD COLUMN IF NOT EXISTS nome_responsavel text,
  ADD COLUMN IF NOT EXISTS contato_responsavel text,
  ADD COLUMN IF NOT EXISTS data_cadastro timestamp with time zone DEFAULT now();

ALTER TABLE public.ordens_recapagem
  ADD COLUMN IF NOT EXISTS cliente_id uuid;

ALTER TABLE public.cpk_historico
  ADD COLUMN IF NOT EXISTS cliente_id uuid;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'ordens_recapagem_cliente_id_fkey'
  ) THEN
    ALTER TABLE public.ordens_recapagem
      ADD CONSTRAINT ordens_recapagem_cliente_id_fkey
      FOREIGN KEY (cliente_id) REFERENCES public.clientes(id);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'cpk_historico_cliente_id_fkey'
  ) THEN
    ALTER TABLE public.cpk_historico
      ADD CONSTRAINT cpk_historico_cliente_id_fkey
      FOREIGN KEY (cliente_id) REFERENCES public.clientes(id);
  END IF;
END $$;

-- 2) Add missing movement columns used by Streamlit app
ALTER TABLE public.movimentacoes
  ADD COLUMN IF NOT EXISTS origem_posicao text,
  ADD COLUMN IF NOT EXISTS destino_posicao text,
  ADD COLUMN IF NOT EXISTS km_momento integer,
  ADD COLUMN IF NOT EXISTS observacao text;

-- 3) Alert log compatibility for API code (alerta_id vs alert_id)
ALTER TABLE public.alertas_log
  ADD COLUMN IF NOT EXISTS alerta_id character varying;

UPDATE public.alertas_log
SET alerta_id = alert_id
WHERE alerta_id IS NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'alertas_log_alerta_id_key'
  ) THEN
    ALTER TABLE public.alertas_log
      ADD CONSTRAINT alertas_log_alerta_id_key UNIQUE (alerta_id);
  END IF;
END $$;

-- Keep both fields in sync during transition
CREATE OR REPLACE FUNCTION public.sync_alert_id_columns()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.alerta_id IS NULL AND NEW.alert_id IS NOT NULL THEN
    NEW.alerta_id := NEW.alert_id;
  ELSIF NEW.alert_id IS NULL AND NEW.alerta_id IS NOT NULL THEN
    NEW.alert_id := NEW.alerta_id;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_sync_alert_id_columns ON public.alertas_log;
CREATE TRIGGER trg_sync_alert_id_columns
BEFORE INSERT OR UPDATE ON public.alertas_log
FOR EACH ROW
EXECUTE FUNCTION public.sync_alert_id_columns();

-- 4) Data consistency: one mounted tire per (truck, position)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_indexes
    WHERE schemaname = 'public'
      AND indexname = 'ux_pneus_montado_posicao'
  ) THEN
    CREATE UNIQUE INDEX ux_pneus_montado_posicao
      ON public.pneus (caminhao_atual_id, posicao_atual)
      WHERE status = 'MONTADO';
  END IF;
END $$;

-- 5) Multi-tenant uniqueness migration (safe introduction)
-- NOTE: Keep old global uniques for now; create new tenant-aware indexes first.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname = 'public' AND indexname = 'ux_caminhoes_cliente_placa'
  ) THEN
    CREATE UNIQUE INDEX ux_caminhoes_cliente_placa
      ON public.caminhoes (cliente_id, placa);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname = 'public' AND indexname = 'ux_pneus_cliente_marca_fogo'
  ) THEN
    CREATE UNIQUE INDEX ux_pneus_cliente_marca_fogo
      ON public.pneus (cliente_id, marca_fogo);
  END IF;
END $$;

-- 6) Operational events model (new canonical write model)
CREATE TABLE IF NOT EXISTS public.eventos_operacionais (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  cliente_id uuid NOT NULL REFERENCES public.clientes(id),
  tipo_evento text NOT NULL CHECK (
    tipo_evento IN (
      'TIRAR_PNEU',
      'COLOCAR_PNEU',
      'TROCAR_POSICAO',
      'ENVIAR_RECAPAGEM',
      'RETORNO_RECAPAGEM',
      'AJUSTE_GESTOR'
    )
  ),
  status text NOT NULL DEFAULT 'CONFIRMADO' CHECK (status IN ('PENDENTE', 'CONFIRMADO', 'CANCELADO')),
  usuario_id uuid REFERENCES public.usuarios(id),
  origem text NOT NULL DEFAULT 'SISTEMA' CHECK (origem IN ('MOTORISTA', 'OFICINA', 'GESTOR', 'SISTEMA', 'API')),
  confianca smallint NOT NULL DEFAULT 50 CHECK (confianca BETWEEN 0 AND 100),
  operation_key text,
  payload jsonb,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_eventos_operation_key
  ON public.eventos_operacionais (operation_key)
  WHERE operation_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_eventos_cliente_data
  ON public.eventos_operacionais (cliente_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_eventos_tipo
  ON public.eventos_operacionais (tipo_evento, created_at DESC);

CREATE TABLE IF NOT EXISTS public.eventos_operacionais_itens (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  evento_id uuid NOT NULL REFERENCES public.eventos_operacionais(id) ON DELETE CASCADE,
  pneu_id uuid REFERENCES public.pneus(id),
  origem_caminhao_id uuid REFERENCES public.caminhoes(id),
  origem_posicao text,
  destino_caminhao_id uuid REFERENCES public.caminhoes(id),
  destino_posicao text,
  km_momento integer,
  motivo text,
  observacao text,
  created_at timestamp with time zone NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_evento_itens_evento
  ON public.eventos_operacionais_itens (evento_id);

CREATE INDEX IF NOT EXISTS ix_evento_itens_pneu
  ON public.eventos_operacionais_itens (pneu_id, created_at DESC);

-- 7) Updated-at trigger helper
CREATE OR REPLACE FUNCTION public.set_updated_at_now()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_eventos_operacionais_updated_at ON public.eventos_operacionais;
CREATE TRIGGER trg_eventos_operacionais_updated_at
BEFORE UPDATE ON public.eventos_operacionais
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at_now();

COMMIT;
