-- TireControl Web Migration V1
-- Goal: Enable Supabase Auth profile model and first operational RPC for web app.

BEGIN;

-- 1) Profiles table tied to auth.users
CREATE TABLE IF NOT EXISTS public.profiles (
  id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  cliente_id uuid REFERENCES public.clientes(id),
  role text NOT NULL DEFAULT 'operador'
    CHECK (role IN ('admin', 'gerente', 'borracheiro', 'motorista', 'operador')),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_profiles_cliente_id ON public.profiles(cliente_id);

DROP TRIGGER IF EXISTS trg_profiles_updated_at ON public.profiles;
CREATE TRIGGER trg_profiles_updated_at
BEFORE UPDATE ON public.profiles
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at_now();

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS profiles_select_own ON public.profiles;
CREATE POLICY profiles_select_own
ON public.profiles
FOR SELECT
TO authenticated
USING (id = auth.uid());

DROP POLICY IF EXISTS profiles_insert_own ON public.profiles;
CREATE POLICY profiles_insert_own
ON public.profiles
FOR INSERT
TO authenticated
WITH CHECK (id = auth.uid());

DROP POLICY IF EXISTS profiles_update_own ON public.profiles;
CREATE POLICY profiles_update_own
ON public.profiles
FOR UPDATE
TO authenticated
USING (id = auth.uid())
WITH CHECK (id = auth.uid());

-- 2) Tenant isolation policies for key tables (read/write inside same cliente_id)
ALTER TABLE public.caminhoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pneus ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.movimentacoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.eventos_operacionais ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.eventos_operacionais_itens ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS caminhoes_by_profile ON public.caminhoes;
CREATE POLICY caminhoes_by_profile
ON public.caminhoes
FOR ALL
TO authenticated
USING (
  cliente_id = (SELECT p.cliente_id FROM public.profiles p WHERE p.id = auth.uid())
)
WITH CHECK (
  cliente_id = (SELECT p.cliente_id FROM public.profiles p WHERE p.id = auth.uid())
);

DROP POLICY IF EXISTS pneus_by_profile ON public.pneus;
CREATE POLICY pneus_by_profile
ON public.pneus
FOR ALL
TO authenticated
USING (
  cliente_id = (SELECT p.cliente_id FROM public.profiles p WHERE p.id = auth.uid())
)
WITH CHECK (
  cliente_id = (SELECT p.cliente_id FROM public.profiles p WHERE p.id = auth.uid())
);

DROP POLICY IF EXISTS eventos_by_profile ON public.eventos_operacionais;
CREATE POLICY eventos_by_profile
ON public.eventos_operacionais
FOR ALL
TO authenticated
USING (
  cliente_id = (SELECT p.cliente_id FROM public.profiles p WHERE p.id = auth.uid())
)
WITH CHECK (
  cliente_id = (SELECT p.cliente_id FROM public.profiles p WHERE p.id = auth.uid())
);

DROP POLICY IF EXISTS evento_itens_by_profile ON public.eventos_operacionais_itens;
CREATE POLICY evento_itens_by_profile
ON public.eventos_operacionais_itens
FOR ALL
TO authenticated
USING (
  EXISTS (
    SELECT 1
    FROM public.eventos_operacionais e
    JOIN public.profiles p ON p.id = auth.uid()
    WHERE e.id = evento_id
      AND e.cliente_id = p.cliente_id
  )
)
WITH CHECK (
  EXISTS (
    SELECT 1
    FROM public.eventos_operacionais e
    JOIN public.profiles p ON p.id = auth.uid()
    WHERE e.id = evento_id
      AND e.cliente_id = p.cliente_id
  )
);

DROP POLICY IF EXISTS movimentacoes_by_profile_read ON public.movimentacoes;
CREATE POLICY movimentacoes_by_profile_read
ON public.movimentacoes
FOR SELECT
TO authenticated
USING (
  EXISTS (
    SELECT 1
    FROM public.pneus t
    JOIN public.profiles p ON p.id = auth.uid()
    WHERE t.id = pneu_id
      AND t.cliente_id = p.cliente_id
  )
);

-- 3) First web operational RPC (tirar pneu)
CREATE OR REPLACE FUNCTION public.rpc_tirecontrol_tirar_pneu(
  p_cliente_id uuid,
  p_usuario_id uuid,
  p_marca_fogo text,
  p_motivo text,
  p_status_destino text DEFAULT 'RECAPAGEM'
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_pneu record;
  v_evento_id uuid;
  v_usuario_db uuid;
BEGIN
  IF p_status_destino NOT IN ('ESTOQUE', 'RECAPAGEM', 'SUCATA') THEN
    RAISE EXCEPTION 'status_destino invalido';
  END IF;

  SELECT id
  INTO v_usuario_db
  FROM public.usuarios
  WHERE id = p_usuario_id
  LIMIT 1;

  SELECT id, marca_fogo, status, caminhao_atual_id, posicao_atual
  INTO v_pneu
  FROM public.pneus
  WHERE cliente_id = p_cliente_id
    AND UPPER(marca_fogo) = UPPER(p_marca_fogo)
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'pneu nao encontrado';
  END IF;
  IF v_pneu.status <> 'MONTADO' THEN
    RAISE EXCEPTION 'pneu nao esta montado';
  END IF;

  UPDATE public.pneus
  SET status = p_status_destino,
      caminhao_atual_id = NULL,
      posicao_atual = NULL,
      data_status = now()
  WHERE id = v_pneu.id;

  INSERT INTO public.movimentacoes
    (pneu_id, tipo_movimento, origem_caminhao_id, origem_posicao, km_momento, usuario_responsavel, observacao)
  VALUES
    (v_pneu.id, 'DESMONTAGEM', v_pneu.caminhao_atual_id, v_pneu.posicao_atual, 0, v_usuario_db, p_motivo);

  INSERT INTO public.eventos_operacionais
    (cliente_id, tipo_evento, status, usuario_id, origem, confianca, operation_key, payload)
  VALUES
    (
      p_cliente_id,
      'TIRAR_PNEU',
      'CONFIRMADO',
      v_usuario_db,
      'API',
      80,
      'web:tira:' || v_pneu.id::text || ':' || EXTRACT(EPOCH FROM now())::bigint::text,
      jsonb_build_object('motivo', p_motivo, 'status_destino', p_status_destino)
    )
  RETURNING id INTO v_evento_id;

  INSERT INTO public.eventos_operacionais_itens
    (evento_id, pneu_id, origem_caminhao_id, origem_posicao, motivo)
  VALUES
    (v_evento_id, v_pneu.id, v_pneu.caminhao_atual_id, v_pneu.posicao_atual, p_motivo);

  RETURN jsonb_build_object(
    'ok', true,
    'evento_id', v_evento_id,
    'pneu_id', v_pneu.id,
    'marca_fogo', v_pneu.marca_fogo
  );
END;
$$;

REVOKE ALL ON FUNCTION public.rpc_tirecontrol_tirar_pneu(uuid, uuid, text, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.rpc_tirecontrol_tirar_pneu(uuid, uuid, text, text, text) TO authenticated;

COMMIT;

