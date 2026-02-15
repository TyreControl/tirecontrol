-- TireControl Web Migration V3
-- Goal: Add retorno de recapagem RPC to complete web operational cycle.

BEGIN;

CREATE OR REPLACE FUNCTION public.rpc_tirecontrol_retorno_recapagem(
  p_cliente_id uuid,
  p_usuario_id uuid,
  p_codigos text[],
  p_observacao text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_usuario_db uuid;
  v_evento_id uuid;
  v_codigo text;
  v_pneu record;
  v_count integer := 0;
BEGIN
  IF p_codigos IS NULL OR array_length(p_codigos, 1) IS NULL THEN
    RAISE EXCEPTION 'nenhum pneu informado';
  END IF;

  SELECT id INTO v_usuario_db FROM public.usuarios WHERE id = p_usuario_id LIMIT 1;

  INSERT INTO public.eventos_operacionais
    (cliente_id, tipo_evento, status, usuario_id, origem, confianca, operation_key, payload)
  VALUES
    (
      p_cliente_id,
      'RETORNO_RECAPAGEM',
      'CONFIRMADO',
      v_usuario_db,
      'API',
      80,
      'web:retorno_recap:' || EXTRACT(EPOCH FROM now())::bigint::text,
      jsonb_build_object('observacao', p_observacao)
    )
  RETURNING id INTO v_evento_id;

  FOREACH v_codigo IN ARRAY p_codigos LOOP
    SELECT id, marca_fogo, status
    INTO v_pneu
    FROM public.pneus
    WHERE cliente_id = p_cliente_id
      AND UPPER(marca_fogo) = UPPER(TRIM(v_codigo))
    FOR UPDATE;

    IF v_pneu.id IS NULL THEN
      CONTINUE;
    END IF;

    -- retorno sempre volta para estoque
    UPDATE public.pneus
    SET status = 'ESTOQUE',
        caminhao_atual_id = NULL,
        posicao_atual = NULL,
        data_status = now()
    WHERE id = v_pneu.id;

    INSERT INTO public.movimentacoes
      (pneu_id, tipo_movimento, km_momento, usuario_responsavel, observacao)
    VALUES
      (v_pneu.id, 'RETORNO_RECAPAGEM', 0, v_usuario_db, p_observacao);

    INSERT INTO public.eventos_operacionais_itens
      (evento_id, pneu_id, motivo, observacao)
    VALUES
      (v_evento_id, v_pneu.id, 'RETORNO_RECAPAGEM', p_observacao);

    v_count := v_count + 1;
  END LOOP;

  IF v_count = 0 THEN
    RAISE EXCEPTION 'nenhum pneu valido para retorno';
  END IF;

  RETURN jsonb_build_object('ok', true, 'evento_id', v_evento_id, 'quantidade', v_count);
END;
$$;

REVOKE ALL ON FUNCTION public.rpc_tirecontrol_retorno_recapagem(uuid, uuid, text[], text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.rpc_tirecontrol_retorno_recapagem(uuid, uuid, text[], text) TO authenticated;

COMMIT;

