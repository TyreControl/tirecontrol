-- TireControl Web Migration V2
-- Goal: Add remaining operational RPCs for web flow.

BEGIN;

-- 1) Colocar pneu
CREATE OR REPLACE FUNCTION public.rpc_tirecontrol_colocar_pneu(
  p_cliente_id uuid,
  p_usuario_id uuid,
  p_marca_fogo text,
  p_caminhao_id uuid,
  p_posicao text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_pneu record;
  v_cam record;
  v_ocupado uuid;
  v_evento_id uuid;
  v_usuario_db uuid;
BEGIN
  SELECT id INTO v_usuario_db FROM public.usuarios WHERE id = p_usuario_id LIMIT 1;

  SELECT id, marca_fogo, status
  INTO v_pneu
  FROM public.pneus
  WHERE cliente_id = p_cliente_id
    AND UPPER(marca_fogo) = UPPER(p_marca_fogo)
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'pneu nao encontrado';
  END IF;

  IF v_pneu.status NOT IN ('ESTOQUE', 'RECAPAGEM') THEN
    RAISE EXCEPTION 'pneu nao disponivel para montagem';
  END IF;

  SELECT id, km_atual
  INTO v_cam
  FROM public.caminhoes
  WHERE id = p_caminhao_id
    AND cliente_id = p_cliente_id
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'caminhao invalido';
  END IF;

  SELECT id
  INTO v_ocupado
  FROM public.pneus
  WHERE caminhao_atual_id = p_caminhao_id
    AND posicao_atual = p_posicao
    AND status = 'MONTADO'
  LIMIT 1;

  IF v_ocupado IS NOT NULL THEN
    RAISE EXCEPTION 'posicao ocupada';
  END IF;

  UPDATE public.pneus
  SET status = 'MONTADO',
      caminhao_atual_id = p_caminhao_id,
      posicao_atual = p_posicao,
      data_status = now()
  WHERE id = v_pneu.id;

  INSERT INTO public.movimentacoes
    (pneu_id, tipo_movimento, destino_caminhao_id, destino_posicao, km_momento, usuario_responsavel)
  VALUES
    (v_pneu.id, 'MONTAGEM', p_caminhao_id, p_posicao, COALESCE(v_cam.km_atual, 0), v_usuario_db);

  INSERT INTO public.eventos_operacionais
    (cliente_id, tipo_evento, status, usuario_id, origem, confianca, operation_key, payload)
  VALUES
    (
      p_cliente_id,
      'COLOCAR_PNEU',
      'CONFIRMADO',
      v_usuario_db,
      'API',
      80,
      'web:coloca:' || v_pneu.id::text || ':' || EXTRACT(EPOCH FROM now())::bigint::text,
      jsonb_build_object('caminhao_id', p_caminhao_id, 'posicao', p_posicao)
    )
  RETURNING id INTO v_evento_id;

  INSERT INTO public.eventos_operacionais_itens
    (evento_id, pneu_id, destino_caminhao_id, destino_posicao, km_momento)
  VALUES
    (v_evento_id, v_pneu.id, p_caminhao_id, p_posicao, COALESCE(v_cam.km_atual, 0));

  RETURN jsonb_build_object('ok', true, 'evento_id', v_evento_id, 'marca_fogo', v_pneu.marca_fogo);
END;
$$;

REVOKE ALL ON FUNCTION public.rpc_tirecontrol_colocar_pneu(uuid, uuid, text, uuid, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.rpc_tirecontrol_colocar_pneu(uuid, uuid, text, uuid, text) TO authenticated;

-- 2) Trocar posicao
CREATE OR REPLACE FUNCTION public.rpc_tirecontrol_trocar_posicao(
  p_cliente_id uuid,
  p_usuario_id uuid,
  p_marca_fogo_a text,
  p_marca_fogo_b text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_a record;
  v_b record;
  v_evento_id uuid;
  v_usuario_db uuid;
BEGIN
  SELECT id INTO v_usuario_db FROM public.usuarios WHERE id = p_usuario_id LIMIT 1;

  SELECT id, marca_fogo, status, caminhao_atual_id, posicao_atual
  INTO v_a
  FROM public.pneus
  WHERE cliente_id = p_cliente_id AND UPPER(marca_fogo) = UPPER(p_marca_fogo_a)
  FOR UPDATE;

  SELECT id, marca_fogo, status, caminhao_atual_id, posicao_atual
  INTO v_b
  FROM public.pneus
  WHERE cliente_id = p_cliente_id AND UPPER(marca_fogo) = UPPER(p_marca_fogo_b)
  FOR UPDATE;

  IF v_a.id IS NULL OR v_b.id IS NULL THEN
    RAISE EXCEPTION 'pneus nao encontrados';
  END IF;
  IF v_a.status <> 'MONTADO' OR v_b.status <> 'MONTADO' THEN
    RAISE EXCEPTION 'os dois pneus devem estar montados';
  END IF;
  IF v_a.caminhao_atual_id <> v_b.caminhao_atual_id THEN
    RAISE EXCEPTION 'pneus em caminhoes diferentes';
  END IF;
  IF v_a.posicao_atual = v_b.posicao_atual THEN
    RAISE EXCEPTION 'pneus na mesma posicao';
  END IF;

  UPDATE public.pneus SET posicao_atual = 'TEMP' WHERE id = v_a.id;
  UPDATE public.pneus SET posicao_atual = v_a.posicao_atual WHERE id = v_b.id;
  UPDATE public.pneus SET posicao_atual = v_b.posicao_atual WHERE id = v_a.id;

  INSERT INTO public.movimentacoes
    (pneu_id, tipo_movimento, origem_caminhao_id, origem_posicao, destino_posicao, km_momento, usuario_responsavel)
  VALUES
    (v_a.id, 'RODIZIO', v_a.caminhao_atual_id, v_a.posicao_atual, v_b.posicao_atual, 0, v_usuario_db);

  INSERT INTO public.eventos_operacionais
    (cliente_id, tipo_evento, status, usuario_id, origem, confianca, operation_key, payload)
  VALUES
    (
      p_cliente_id,
      'TROCAR_POSICAO',
      'CONFIRMADO',
      v_usuario_db,
      'API',
      80,
      'web:troca:' || v_a.id::text || ':' || v_b.id::text || ':' || EXTRACT(EPOCH FROM now())::bigint::text,
      jsonb_build_object('caminhao_id', v_a.caminhao_atual_id)
    )
  RETURNING id INTO v_evento_id;

  INSERT INTO public.eventos_operacionais_itens
    (evento_id, pneu_id, origem_caminhao_id, origem_posicao, destino_caminhao_id, destino_posicao)
  VALUES
    (v_evento_id, v_a.id, v_a.caminhao_atual_id, v_a.posicao_atual, v_a.caminhao_atual_id, v_b.posicao_atual);

  INSERT INTO public.eventos_operacionais_itens
    (evento_id, pneu_id, origem_caminhao_id, origem_posicao, destino_caminhao_id, destino_posicao)
  VALUES
    (v_evento_id, v_b.id, v_b.caminhao_atual_id, v_b.posicao_atual, v_b.caminhao_atual_id, v_a.posicao_atual);

  RETURN jsonb_build_object('ok', true, 'evento_id', v_evento_id);
END;
$$;

REVOKE ALL ON FUNCTION public.rpc_tirecontrol_trocar_posicao(uuid, uuid, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.rpc_tirecontrol_trocar_posicao(uuid, uuid, text, text) TO authenticated;

-- 3) Enviar recapagem (lote)
CREATE OR REPLACE FUNCTION public.rpc_tirecontrol_enviar_recapagem(
  p_cliente_id uuid,
  p_usuario_id uuid,
  p_recapadora text,
  p_codigos text[]
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_usuario_db uuid;
  v_evento_id uuid;
  v_ordem_id text;
  v_codigo text;
  v_pneu record;
  v_count integer := 0;
BEGIN
  IF p_codigos IS NULL OR array_length(p_codigos, 1) IS NULL THEN
    RAISE EXCEPTION 'nenhum pneu informado';
  END IF;

  SELECT id INTO v_usuario_db FROM public.usuarios WHERE id = p_usuario_id LIMIT 1;
  v_ordem_id := 'REC_' || to_char(now(), 'YYYYMMDDHH24MISS');

  INSERT INTO public.ordens_recapagem
    (ordem_id, recapadora_nome, status, data_criacao, data_ultima_atualizacao, usuario_responsavel, cliente_id)
  VALUES
    (v_ordem_id, COALESCE(NULLIF(p_recapadora, ''), 'Recapadora'), 'enviado', now(), now(), v_usuario_db, p_cliente_id);

  INSERT INTO public.eventos_operacionais
    (cliente_id, tipo_evento, status, usuario_id, origem, confianca, operation_key, payload)
  VALUES
    (
      p_cliente_id,
      'ENVIAR_RECAPAGEM',
      'CONFIRMADO',
      v_usuario_db,
      'API',
      80,
      'web:recap:' || v_ordem_id,
      jsonb_build_object('ordem_id', v_ordem_id, 'recapadora', p_recapadora)
    )
  RETURNING id INTO v_evento_id;

  FOREACH v_codigo IN ARRAY p_codigos LOOP
    SELECT id, marca_fogo, status, caminhao_atual_id, posicao_atual
    INTO v_pneu
    FROM public.pneus
    WHERE cliente_id = p_cliente_id
      AND UPPER(marca_fogo) = UPPER(TRIM(v_codigo))
    FOR UPDATE;

    IF v_pneu.id IS NULL THEN
      CONTINUE;
    END IF;
    IF v_pneu.status = 'SUCATA' THEN
      CONTINUE;
    END IF;

    UPDATE public.pneus
    SET status = 'RECAPAGEM',
        caminhao_atual_id = NULL,
        posicao_atual = NULL,
        data_status = now()
    WHERE id = v_pneu.id;

    INSERT INTO public.ordens_recapagem_pneus (ordem_id, pneu_id, data_adicionada)
    VALUES (v_ordem_id, v_pneu.id, now());

    INSERT INTO public.eventos_operacionais_itens
      (evento_id, pneu_id, origem_caminhao_id, origem_posicao, motivo)
    VALUES
      (v_evento_id, v_pneu.id, v_pneu.caminhao_atual_id, v_pneu.posicao_atual, 'ENVIAR_RECAPAGEM');

    v_count := v_count + 1;
  END LOOP;

  IF v_count = 0 THEN
    RAISE EXCEPTION 'nenhum pneu valido para recapagem';
  END IF;

  RETURN jsonb_build_object('ok', true, 'evento_id', v_evento_id, 'ordem_id', v_ordem_id, 'quantidade', v_count);
END;
$$;

REVOKE ALL ON FUNCTION public.rpc_tirecontrol_enviar_recapagem(uuid, uuid, text, text[]) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.rpc_tirecontrol_enviar_recapagem(uuid, uuid, text, text[]) TO authenticated;

COMMIT;

