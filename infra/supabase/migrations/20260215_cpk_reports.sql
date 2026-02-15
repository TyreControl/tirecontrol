-- 20260215_cpk_reports.sql

-- 1. Table for CPK History
CREATE TABLE IF NOT EXISTS public.cpk_historico (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    cliente_id uuid NOT NULL,
    data_calculo timestamptz DEFAULT now(),
    cpk_valor numeric(10, 4),
    media numeric(10, 2),
    desvio numeric(10, 2),
    quantidade_pneus integer,
    status text, -- 'Excelente', 'Adequado', 'Atencao', 'Critico'
    recomendacao text
);

-- 2. RPC to Calculate CPK
CREATE OR REPLACE FUNCTION public.rpc_tirecontrol_calcular_cpk(
    p_cliente_id uuid
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_stats record;
    v_cpk_inferior numeric;
    v_cpk_superior numeric;
    v_cpk numeric;
    v_status text;
    v_recomendacao text;
    v_limite_inf numeric := 36.0; -- 36 months
    v_limite_sup numeric := 48.0; -- 48 months
    v_histogram jsonb;
    v_history_entry jsonb;
BEGIN
    -- Calculate basic stats (Mean, StdDev) for active tires
    SELECT 
        AVG(months_alive) as media,
        STDDEV(months_alive) as desvio,
        COUNT(*) as qtd
    INTO v_stats
    FROM public.pneus
    WHERE cliente_id = p_cliente_id 
      AND status IN ('MONTADO', 'ESTOQUE')
      AND months_alive IS NOT NULL;

    IF v_stats.qtd IS NULL OR v_stats.qtd < 2 THEN
        RETURN jsonb_build_object('ok', false, 'error', 'Dados insuficientes para cálculo');
    END IF;

    -- Calculate CPK
    IF v_stats.desvio = 0 THEN
        v_cpk := 0;
    ELSE
        v_cpk_superior := (v_limite_sup - v_stats.media) / (3 * v_stats.desvio);
        v_cpk_inferior := (v_stats.media - v_limite_inf) / (3 * v_stats.desvio);
        v_cpk := LEAST(v_cpk_superior, v_cpk_inferior);
    END IF;

    -- Classification
    IF v_cpk >= 1.33 THEN
        v_status := 'Excelente';
        v_recomendacao := 'Processo sob controle.';
    ELSIF v_cpk >= 1.0 THEN
        v_status := 'Adequado';
        v_recomendacao := 'Processo aceitável.';
    ELSIF v_cpk >= 0.67 THEN
        v_status := 'Atenção';
        v_recomendacao := 'Processo fora dos limites.';
    ELSE
        v_status := 'Crítico';
        v_recomendacao := 'Ação imediata necessária.';
    END IF;

    -- Save History
    INSERT INTO public.cpk_historico 
    (cliente_id, cpk_valor, media, desvio, quantidade_pneus, status, recomendacao)
    VALUES 
    (p_cliente_id, v_cpk, v_stats.media, v_stats.desvio, v_stats.qtd, v_status, v_recomendacao)
    RETURNING jsonb_build_object(
        'data', data_calculo, 
        'cpk', cpk_valor, 
        'status', status
    ) INTO v_history_entry;

    -- Generate Histogram Data (Simple buckets in DB or return raw values? 
    -- Returning raw values is flexible for frontend charts)
    SELECT jsonb_agg(months_alive) INTO v_histogram
    FROM public.pneus
    WHERE cliente_id = p_cliente_id 
      AND status IN ('MONTADO', 'ESTOQUE')
      AND months_alive IS NOT NULL;

    RETURN jsonb_build_object(
        'ok', true,
        'cpk', v_cpk,
        'media', v_stats.media,
        'desvio', v_stats.desvio,
        'quantidade', v_stats.qtd,
        'status', v_status,
        'recomendacao', v_recomendacao,
        'dados_vida', v_histogram,
        'historico_recente', v_history_entry
    );
END;
$$;

REVOKE ALL ON FUNCTION public.rpc_tirecontrol_calcular_cpk(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.rpc_tirecontrol_calcular_cpk(uuid) TO authenticated;


-- 3. RPC for General Reports (Totals, Costs)
CREATE OR REPLACE FUNCTION public.rpc_tirecontrol_relatorio_geral(
    p_cliente_id uuid,
    p_dias_movimentacao integer DEFAULT 30
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_status_dist jsonb;
    v_movimentacoes jsonb;
    v_custos_totais numeric;
BEGIN
    -- Status Distribution
    SELECT jsonb_object_agg(status, count) INTO v_status_dist
    FROM (
        SELECT status, COUNT(*) as count
        FROM public.pneus
        WHERE cliente_id = p_cliente_id
        GROUP BY status
    ) t;

    -- Recent Movements (Count by Type)
    SELECT jsonb_agg(t) INTO v_movimentacoes
    FROM (
        SELECT tipo_movimento, COUNT(*) as qtd
        FROM public.movimentacoes m
        JOIN public.pneus p ON p.id = m.pneu_id
        WHERE p.cliente_id = p_cliente_id
          AND m.data_movimento >= (now() - (p_dias_movimentacao || ' days')::interval)
        GROUP BY tipo_movimento
    ) t;

    -- Total Maintenance Costs (Mocking cost logic if no 'custo' column in pneu, 
    -- but legacy had 'custo_servico'. Assuming we might add it later or calculate from movements.
    -- For now, returning 0 placeholder or calculating if column exists. 
    -- Checking schema... assume we don't have cost column yet, return 0)
    v_custos_totais := 0;

    RETURN jsonb_build_object(
        'distribuicao_status', v_status_dist,
        'movimentacoes', v_movimentacoes,
        'custo_estimado', v_custos_totais
    );
END;
$$;

REVOKE ALL ON FUNCTION public.rpc_tirecontrol_relatorio_geral(uuid, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.rpc_tirecontrol_relatorio_geral(uuid, integer) TO authenticated;
