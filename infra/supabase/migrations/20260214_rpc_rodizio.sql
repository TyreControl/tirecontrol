-- 20260214_rpc_rodizio.sql
-- RPC to execute tire rotation suggestions (batch)

CREATE OR REPLACE FUNCTION public.rpc_tirecontrol_executar_rodizio(
  p_veiculo_id uuid,
  p_usuario_id uuid,
  p_trocas jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_troca jsonb;
    v_pneu_de_id uuid;
    v_pneu_para_id uuid;
    v_pneu_de record;
    v_pneu_para record;
    v_usuario_db uuid;
    v_rodizio_id text;
    v_evento_id uuid;
    v_count integer := 0;
BEGIN
    -- 1. Get internal user ID
    SELECT id INTO v_usuario_db FROM public.usuarios WHERE id = p_usuario_id LIMIT 1;
    IF v_usuario_db IS NULL THEN
        RAISE EXCEPTION 'usuario nao encontrado';
    END IF;

    -- 2. Generate Rotation ID
    v_rodizio_id := 'ROD-' || to_char(now(), 'YYYYMMDDHH24MISS');

    -- 3. Iterate over swaps
    -- Expected JSON format: [{ "trocar_de": { "id": "uuid", "posicao_atual": "pos" }, "trocar_para": { "id": "uuid" } }]
    
    IF p_trocas IS NULL OR jsonb_array_length(p_trocas) = 0 THEN
         RAISE EXCEPTION 'nenhuma troca informada';
    END IF;

    -- Create operational event for the whole batch
    INSERT INTO public.eventos_operacionais
    (cliente_id, tipo_evento, status, usuario_id, origem, confianca, operation_key, payload)
    VALUES
    (
        (SELECT cliente_id FROM public.usuarios WHERE id = v_usuario_db),
        'RODIZIO_AUTOMATICO',
        'CONFIRMADO',
        v_usuario_db,
        'API',
        90,
        'web:rodizio:' || v_rodizio_id,
        jsonb_build_object('rodizio_id', v_rodizio_id, 'veiculo_id', p_veiculo_id, 'qtd_trocas', jsonb_array_length(p_trocas))
    )
    RETURNING id INTO v_evento_id;

    FOR v_troca IN SELECT * FROM jsonb_array_elements(p_trocas) LOOP
        v_pneu_de_id := (v_troca->'trocar_de'->>'id')::uuid;
        v_pneu_para_id := (v_troca->'trocar_para'->>'id')::uuid;

        -- Lock tires
        SELECT * INTO v_pneu_de FROM public.pneus WHERE id = v_pneu_de_id FOR UPDATE;
        SELECT * INTO v_pneu_para FROM public.pneus WHERE id = v_pneu_para_id FOR UPDATE;

        IF v_pneu_de.id IS NULL OR v_pneu_para.id IS NULL THEN
            RAISE EXCEPTION 'pneu nao encontrado durante rodizio';
        END IF;

        -- Validation
        IF v_pneu_de.caminhao_atual_id IS DISTINCT FROM p_veiculo_id THEN
             RAISE EXCEPTION 'pneu de origem nao esta no caminhao correto';
        END IF;
        
        -- Execution: Swap Logic
        -- 1. Remove 'Active' tire -> Stock
        UPDATE public.pneus 
        SET status = 'ESTOQUE', caminhao_atual_id = NULL, posicao_atual = NULL, data_status = now()
        WHERE id = v_pneu_de_id;

        -- 2. Install 'Stock' tire -> Active (same position)
        UPDATE public.pneus 
        SET status = 'MONTADO', caminhao_atual_id = p_veiculo_id, posicao_atual = v_pneu_de.posicao_atual, data_status = now()
        WHERE id = v_pneu_para_id;

        -- 3. Record Movement
        -- Active -> Stock
         INSERT INTO public.movimentacoes
        (pneu_id, tipo_movimento, origem_caminhao_id, origem_posicao, destino_posicao, km_momento, usuario_responsavel)
        VALUES
        (v_pneu_de_id, 'RODIZIO_SAIDA', p_veiculo_id, v_pneu_de.posicao_atual, 'ESTOQUE', 0, v_usuario_db);

        -- Stock -> Active
         INSERT INTO public.movimentacoes
        (pneu_id, tipo_movimento, origem_posicao, destino_caminhao_id, destino_posicao, km_momento, usuario_responsavel)
        VALUES
        (v_pneu_para_id, 'RODIZIO_ENTRADA', 'ESTOQUE', p_veiculo_id, v_pneu_de.posicao_atual, 0, v_usuario_db);
        
        -- 4. Event Items
        INSERT INTO public.eventos_operacionais_itens
        (evento_id, pneu_id, origem_caminhao_id, origem_posicao, destino_posicao)
        VALUES
        (v_evento_id, v_pneu_de_id, p_veiculo_id, v_pneu_de.posicao_atual, 'ESTOQUE');

        INSERT INTO public.eventos_operacionais_itens
        (evento_id, pneu_id, origem_posicao, destino_caminhao_id, destino_posicao)
        VALUES
        (v_evento_id, v_pneu_para_id, 'ESTOQUE', p_veiculo_id, v_pneu_de.posicao_atual);

        v_count := v_count + 1;
    END LOOP;

    RETURN jsonb_build_object('ok', true, 'rodizio_id', v_rodizio_id, 'trocas_realizadas', v_count);
END;
$$;

REVOKE ALL ON FUNCTION public.rpc_tirecontrol_executar_rodizio(uuid, uuid, jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.rpc_tirecontrol_executar_rodizio(uuid, uuid, jsonb) TO authenticated;
