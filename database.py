import streamlit as st
import psycopg2
import psycopg2.extras
from psycopg2 import pool
from datetime import datetime, date
import uuid

# ============ CONEXÃO POOL ============

@st.cache_resource
def init_connection_pool():
    try:
        return psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=st.secrets["SUPABASE_URL"],
            cursor_factory=psycopg2.extras.RealDictCursor
        )
    except Exception as e:
        st.error(f"Erro crítico ao conectar no banco: {e}")
        return None

def get_connection():
    """Obtém uma conexão do pool"""
    pool = init_connection_pool()
    if pool:
        return pool.getconn()
    return None

def release_connection(conn):
    """Devolve a conexão ao pool"""
    pool = init_connection_pool()
    if pool and conn:
        pool.putconn(conn)

def run_query(query, params=None):
    """Executa uma query e retorna resultado"""
    conn = get_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            if query.strip().upper().startswith("SELECT"):
                return cur.fetchall()
            else:
                conn.commit()
                return True
    except Exception as e:
        st.error(f"Erro na query: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        release_connection(conn)

# ============ FLUXO 0: CLIENTES ============

def get_todos_clientes():
    """Retorna todos os clientes"""
    query = """
    SELECT id, razao_social, nome_fantasia, cnpj
    FROM public.clientes
    ORDER BY razao_social
    """
    return run_query(query)

def get_detalhes_cliente(cliente_id):
    """Retorna dados completos de um cliente"""
    query = """
    SELECT *
    FROM public.clientes
    WHERE id = %s
    """
    result = run_query(query, (cliente_id,))
    return result[0] if result else None

def atualizar_dados_cliente(cliente_id, dados: dict):
    """Atualiza dados cadastrais do cliente"""
    if not dados:
        return False

    campos = []
    valores = []
    for campo, valor in dados.items():
        campos.append(f"{campo} = %s")
        valores.append(valor)
    valores.append(cliente_id)

    query = f"""
    UPDATE public.clientes
    SET {', '.join(campos)}
    WHERE id = %s
    """
    return run_query(query, tuple(valores))

# ============ FLUXO 1: CADASTRO DE LOTE DE PNEUS ============

def criar_lote_pneus(cliente_id, marca, medida, modelo, fornecedor,
                     quantidade, preco_unitario, n_nota_fiscal, data_chegada):
    """Cria um novo lote de pneus e retorna o ID do lote"""
    try:
        numero_lote = f"LOT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        query = """
        INSERT INTO public.lote_pneus
        (cliente_id, numero_lote, marca, medida, modelo, fornecedor,
         quantidade_total, quantidade_disponivel, preco_unitario,
         n_nota_fiscal, data_chegada, data_criacao)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        RETURNING id, numero_lote
        """
        params = (cliente_id, numero_lote, marca, medida, modelo, fornecedor,
                  quantidade, quantidade, preco_unitario, n_nota_fiscal, data_chegada)
        result = run_query(query, params)
        if result:
            return {"lote_id": str(result[0]['id']), "numero_lote": result[0]['numero_lote']}
        return None
    except Exception as e:
        st.error(f"Erro ao criar lote: {e}")
        return None

def adicionar_pneus_ao_lote(cliente_id, lote_id, lista_marcas_fogo, marca, medida,
                            modelo, fornecedor, custo, data_compra, n_nota_fiscal):
    """Adiciona pneus individuais a um lote existente"""
    try:
        query = """
        INSERT INTO public.pneus
        (cliente_id, marca_fogo, marca, medida, modelo, status,
         ciclo_atual, km_vida_total, custo_aquisicao, n_nota_fiscal,
         fornecedor, data_compra, lote_id, data_status)
        VALUES (%s, %s, %s, %s, %s, 'ESTOQUE', 0, 0, %s, %s, %s, %s, %s, NOW())
        """
        sucesso_count = 0
        for marca_fogo in lista_marcas_fogo:
            params = (cliente_id, marca_fogo.upper(), marca, medida, modelo,
                      custo, n_nota_fiscal, fornecedor, data_compra, lote_id)
            if run_query(query, params):
                sucesso_count += 1
        return sucesso_count == len(lista_marcas_fogo)
    except Exception as e:
        st.error(f"Erro ao adicionar pneus: {e}")
        return False

def obter_lotes_cliente(cliente_id):
    """Retorna todos os lotes de um cliente"""
    query = """
    SELECT id, numero_lote, marca, medida, modelo, fornecedor,
           quantidade_total, quantidade_disponivel, preco_unitario,
           n_nota_fiscal, data_chegada, data_criacao
    FROM public.lote_pneus
    WHERE cliente_id = %s
    ORDER BY data_chegada DESC
    """
    return run_query(query, (cliente_id,))

def obter_pneus_lote(lote_id):
    """Retorna todos os pneus de um lote específico"""
    query = """
    SELECT id, marca_fogo, marca, medida, ciclo_atual, km_vida_total,
           status, caminhao_atual_id, posicao_atual
    FROM public.pneus
    WHERE lote_id = %s
    ORDER BY marca_fogo
    """
    return run_query(query, (lote_id,))

# ============ FLUXO 2: ATRIBUIR PNEUS A CAMINHÃO ============

def atribuir_pneu_posicao(pneu_id, veiculo_id, posicao_nova, usuario_id):
    """Atribui um pneu a uma posição específica de um caminhão"""
    try:
        # Obter posição anterior
        query_anterior = """
        SELECT posicao_atual, caminhao_atual_id
        FROM public.pneus WHERE id = %s
        """
        result_anterior = run_query(query_anterior, (pneu_id,))
        posicao_anterior = result_anterior[0]['posicao_atual'] if result_anterior else 'ESTOQUE'
        veiculo_anterior = result_anterior[0]['caminhao_atual_id'] if result_anterior else None

        # Atualizar posição do pneu
        query_update = """
        UPDATE public.pneus
        SET caminhao_atual_id = %s,
            posicao_atual = %s,
            status = 'MONTADO',
            data_status = NOW()
        WHERE id = %s
        """
        if not run_query(query_update, (veiculo_id, posicao_nova, pneu_id)):
            return False

        # Registrar movimento
        query_movimento = """
        INSERT INTO public.movimentacoes
        (pneu_id, tipo_movimento, origem_caminhao_id, destino_caminhao_id,
         posicao_de, posicao_para, usuario_responsavel, data_movimento)
        VALUES (%s, 'MONTAGEM', %s, %s, %s, %s, %s, NOW())
        """
        run_query(query_movimento, (pneu_id, veiculo_anterior, veiculo_id,
                                    posicao_anterior, posicao_nova, usuario_id))
        return True
    except Exception as e:
        st.error(f"Erro ao atribuir pneu: {e}")
        return False

def remover_pneu_posicao(pneu_id, usuario_id):
    """Remove um pneu de um caminhão (volta para estoque)"""
    try:
        # Obter info atual
        query_info = """
        SELECT caminhao_atual_id, posicao_atual
        FROM public.pneus WHERE id = %s
        """
        result = run_query(query_info, (pneu_id,))
        if not result:
            return False

        veiculo_id = result[0]['caminhao_atual_id']
        posicao_anterior = result[0]['posicao_atual']

        # Atualizar status
        query_update = """
        UPDATE public.pneus
        SET caminhao_atual_id = NULL,
            posicao_atual = NULL,
            status = 'ESTOQUE',
            data_status = NOW()
        WHERE id = %s
        """
        if not run_query(query_update, (pneu_id,)):
            return False

        # Registrar movimento
        query_movimento = """
        INSERT INTO public.movimentacoes
        (pneu_id, tipo_movimento, origem_caminhao_id, destino_caminhao_id,
         posicao_de, posicao_para, usuario_responsavel, data_movimento)
        VALUES (%s, 'DESMONTAGEM', %s, NULL, %s, 'ESTOQUE', %s, NOW())
        """
        run_query(query_movimento, (pneu_id, veiculo_id, posicao_anterior, usuario_id))
        return True
    except Exception as e:
        st.error(f"Erro ao remover pneu: {e}")
        return False

def obter_pneus_caminhao_por_posicao(veiculo_id):
    """Retorna MAPA: posicao -> pneu_dados para visualizar no chassi"""
    query = """
    SELECT id, marca_fogo, marca, medida, posicao_atual,
           ciclo_atual, km_vida_total, status
    FROM public.pneus
    WHERE caminhao_atual_id = %s AND status = 'MONTADO'
    ORDER BY posicao_atual
    """
    result = run_query(query, (veiculo_id,))
    mapa = {}
    if result:
        for pneu in result:
            posicao = pneu['posicao_atual']
            mapa[posicao] = pneu
    return mapa

def obter_pneus_estoque_disponiveis(cliente_id, filtro_medida=None):
    """Retorna pneus disponíveis no estoque para distribuir"""
    if filtro_medida:
        query = """
        SELECT id, marca_fogo, marca, medida, ciclo_atual,
               km_vida_total, custo_aquisicao,
               CASE WHEN ciclo_atual = 0 THEN 'Novo'
                    ELSE CONCAT('Recapado ', ciclo_atual, 'x') END as tipo_pneu,
               (70000 - km_vida_total) as km_restante
        FROM public.pneus
        WHERE cliente_id = %s AND status = 'ESTOQUE'
              AND caminhao_atual_id IS NULL AND medida = %s
        ORDER BY km_vida_total DESC
        """
        return run_query(query, (cliente_id, filtro_medida))
    else:
        query = """
        SELECT id, marca_fogo, marca, medida, ciclo_atual,
               km_vida_total, custo_aquisicao,
               CASE WHEN ciclo_atual = 0 THEN 'Novo'
                    ELSE CONCAT('Recapado ', ciclo_atual, 'x') END as tipo_pneu,
               (70000 - km_vida_total) as km_restante
        FROM public.pneus
        WHERE cliente_id = %s AND status = 'ESTOQUE'
              AND caminhao_atual_id IS NULL
        ORDER BY km_vida_total DESC
        """
        return run_query(query, (cliente_id,))

# ============ FLUXO 3: RECAPAGEM ============

def criar_ordem_recapagem(ordem_id, recapadora_nome, usuario_id):
    """Cria uma nova ordem de recapagem"""
    query = """
    INSERT INTO public.ordens_recapagem 
    (ordem_id, recapadora_nome, status, data_criacao, usuario_responsavel)
    VALUES (%s, %s, 'enviado', %s, %s)
    """
    params = (ordem_id, recapadora_nome, datetime.now(), usuario_id)
    return run_query(query, params)

def adicionar_pneu_ordem(ordem_id, pneu_id):
    """Adiciona um pneu a uma ordem de recapagem"""
    query = """
    INSERT INTO public.ordens_recapagem_pneus (ordem_id, pneu_id, data_adicionada)
    VALUES (%s, %s, %s)
    """
    params = (ordem_id, pneu_id, datetime.now())
    return run_query(query, params)

def atualizar_status_ordem(ordem_id, novo_status):
    """Atualiza status de uma ordem"""
    query = """
    UPDATE public.ordens_recapagem
    SET status = %s, data_ultima_atualizacao = %s
    WHERE ordem_id = %s
    """
    params = (novo_status, datetime.now(), ordem_id)
    return run_query(query, params)

def obter_ordem(ordem_id):
    """Obtém dados de uma ordem"""
    query = """
    SELECT * FROM public.ordens_recapagem
    WHERE ordem_id = %s
    """
    result = run_query(query, (ordem_id,))
    return result[0] if result else None

def get_ordens_recapagem(cliente_id):
    """Lista todas as ordens de recapagem de um cliente"""
    query = """
    SELECT or.* FROM public.ordens_recapagem or
    JOIN public.ordens_recapagem_pneus orp ON or.ordem_id = orp.ordem_id
    JOIN public.pneus p ON orp.pneu_id = p.id
    JOIN public.veiculos v ON p.caminhao_atual_id = v.id
    WHERE v.cliente_id = %s
    GROUP BY or.ordem_id
    ORDER BY or.data_criacao DESC
    """
    return run_query(query, (cliente_id,))

def receber_pneus_recapados(cliente_id, lista_pneus_recapados):
    """Recebe pneus recapados: {pneu_id, ciclo_novo, km_novo}"""
    try:
        sucesso = 0
        for pneu_info in lista_pneus_recapados:
            pneu_id = pneu_info['pneu_id']
            ciclo_novo = pneu_info['ciclo_novo']
            km_novo = pneu_info['km_novo']

            query = """
            UPDATE public.pneus
            SET ciclo_atual = %s,
                km_vida_total = %s,
                status = 'ESTOQUE',
                caminhao_atual_id = NULL,
                posicao_atual = NULL,
                data_status = NOW()
            WHERE id = %s
            """
            if run_query(query, (ciclo_novo, km_novo, pneu_id)):
                sucesso += 1

        return sucesso == len(lista_pneus_recapados)
    except Exception as e:
        st.error(f"Erro ao receber pneus recapados: {e}")
        return False

# ============ FLUXO 4: ALERTAS ============

def criar_alerta(alert_id, tipo, severidade, pneu_id, mensagem, acao, criado_por):
    """Cria um novo alerta"""
    query = """
    INSERT INTO public.alertas_log 
    (alert_id, tipo, severidade, pneu_id, mensagem, acao, data_criacao, criado_por, resolvido)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, FALSE)
    """
    params = (alert_id, tipo, severidade, pneu_id, mensagem, acao, datetime.now(), criado_por)
    return run_query(query, params)

def resolver_alerta(alert_id):
    """Marca um alerta como resolvido"""
    query = """
    UPDATE public.alertas_log
    SET resolvido = TRUE, data_resolucao = %s
    WHERE alert_id = %s
    """
    params = (datetime.now(), alert_id)
    return run_query(query, params)

def listar_alertas_ativos(cliente_id=None):
    """Lista todos os alertas não resolvidos"""
    if cliente_id:
        query = """
        SELECT al.* FROM public.alertas_log al
        JOIN public.pneus p ON al.pneu_id = p.id
        JOIN public.veiculos v ON p.caminhao_atual_id = v.id
        WHERE al.resolvido = FALSE AND v.cliente_id = %s
        ORDER BY
        CASE
            WHEN al.severidade = 'CRITICO' THEN 0
            WHEN al.severidade = 'ALTO' THEN 1
            WHEN al.severidade = 'MEDIO' THEN 2
            ELSE 3
        END,
        al.data_criacao DESC
        """
        return run_query(query, (cliente_id,))
    else:
        query = """
        SELECT * FROM public.alertas_log
        WHERE resolvido = FALSE
        ORDER BY
        CASE
            WHEN severidade = 'CRITICO' THEN 0
            WHEN severidade = 'ALTO' THEN 1
            WHEN severidade = 'MEDIO' THEN 2
            ELSE 3
        END,
        data_criacao DESC
        """
        return run_query(query)

def gerar_alertas_automaticos(cliente_id):
    """Gera alertas automáticos baseado em regras de negócio"""
    try:
        alertas_criados = []
        
        # Alerta 1: Pneus com desgaste crítico (>85%)
        query_desgaste = """
        SELECT p.id, p.marca_fogo, p.km_vida_total, p.ciclo_atual
        FROM public.pneus p
        JOIN public.veiculos v ON p.caminhao_atual_id = v.id
        WHERE v.cliente_id = %s AND p.status = 'MONTADO'
              AND p.km_vida_total > (
                  CASE WHEN p.ciclo_atual = 0 THEN 85000
                       ELSE 59500 END
              )
        """
        pneus_desgaste = run_query(query_desgaste, (cliente_id,))
        if pneus_desgaste:
            for pneu in pneus_desgaste:
                alert_id = str(uuid.uuid4())
                criar_alerta(
                    alert_id, 'DESGASTE', 'CRITICO', pneu['id'],
                    f"Pneu {pneu['marca_fogo']} atingiu desgaste crítico",
                    'SUBSTITUIR_URGENTE', 'SISTEMA_AUTO'
                )
                alertas_criados.append(alert_id)

        # Alerta 2: Rodízios atrasados (>30 dias)
        query_rodizio = """
        SELECT DISTINCT p.id, p.marca_fogo, MAX(m.data_movimento) as ultimo_rodizio
        FROM public.pneus p
        LEFT JOIN public.movimentacoes m ON p.id = m.pneu_id AND m.tipo_movimento = 'RODIZIO'
        JOIN public.veiculos v ON p.caminhao_atual_id = v.id
        WHERE v.cliente_id = %s AND p.status = 'MONTADO'
        GROUP BY p.id, p.marca_fogo
        HAVING MAX(m.data_movimento) < NOW() - INTERVAL '30 days' 
               OR MAX(m.data_movimento) IS NULL
        """
        pneus_rodizio = run_query(query_rodizio, (cliente_id,))
        if pneus_rodizio:
            for pneu in pneus_rodizio:
                alert_id = str(uuid.uuid4())
                criar_alerta(
                    alert_id, 'RODIZIO_ATRASADO', 'ALTO', pneu['id'],
                    f"Pneu {pneu['marca_fogo']} necessita rodízio",
                    'AGENDAR_RODIZIO', 'SISTEMA_AUTO'
                )
                alertas_criados.append(alert_id)

        return alertas_criados
    except Exception as e:
        st.error(f"Erro ao gerar alertas: {e}")
        return []

# ============ FLUXO 5: RODÍZIO DE PNEUS ============

def sugerir_rodizio_automatico(veiculo_id):
    """Sugere AUTOMATICAMENTE qual rodízio fazer baseado em desgaste"""
    try:
        # Obter pneus montados ORDENADOS por desgaste
        query_montados = """
        SELECT id, marca_fogo, posicao_atual, km_vida_total, ciclo_atual
        FROM public.pneus
        WHERE caminhao_atual_id = %s AND status = 'MONTADO'
        ORDER BY km_vida_total DESC
        """
        pneus_montados = run_query(query_montados, (veiculo_id,))

        if not pneus_montados or len(pneus_montados) < 2:
            return []

        # Obter pneus em estoque (com menos desgaste)
        query_estoque = """
        SELECT id, marca_fogo, km_vida_total, ciclo_atual
        FROM public.pneus
        WHERE status = 'ESTOQUE' AND caminhao_atual_id IS NULL
        ORDER BY km_vida_total ASC
        LIMIT 10
        """
        pneus_estoque = run_query(query_estoque)

        if not pneus_estoque:
            return []

        # Calcular sugestões
        sugestoes = []
        for idx, pneu_montado in enumerate(pneus_montados[:4]):  # Top 4 mais desgastados
            limite_vida = 100000 if pneu_montado['ciclo_atual'] == 0 else 70000
            desgaste_percentual = (pneu_montado['km_vida_total'] / limite_vida) * 100

            # Procurar pneu em estoque com menos desgaste
            for pneu_estoque in pneus_estoque:
                economia_km = pneu_montado['km_vida_total'] - pneu_estoque['km_vida_total']

                if economia_km > 5000:  # Mínimo 5000 km de economia
                    sugestoes.append({
                        'id_sugestao': idx,
                        'trocar_de': {
                            'id': str(pneu_montado['id']),
                            'marca_fogo': pneu_montado['marca_fogo'],
                            'posicao': pneu_montado['posicao_atual'],
                            'km_vida': pneu_montado['km_vida_total'],
                            'desgaste_pct': round(desgaste_percentual, 1)
                        },
                        'trocar_para': {
                            'id': str(pneu_estoque['id']),
                            'marca_fogo': pneu_estoque['marca_fogo'],
                            'km_vida': pneu_estoque['km_vida_total']
                        },
                        'economia_km': economia_km
                    })
                    break

        return sugestoes
    except Exception as e:
        st.error(f"Erro ao sugerir rodízio: {e}")
        return []

def executar_rodizio(veiculo_id, sugestoes, usuario_id, km_veiculo, motivo="Rodízio rotina"):
    """Executa o rodízio aprovado e registra TODOS os movimentos"""
    try:
        # Criar registro de rodízio
        rodizio_id = str(uuid.uuid4())

        # Obter cliente_id
        query_veiculo = "SELECT cliente_id FROM public.veiculos WHERE id = %s"
        result_veiculo = run_query(query_veiculo, (veiculo_id,))

        if not result_veiculo:
            st.error("Veículo não encontrado")
            return False

        cliente_id = result_veiculo[0]['cliente_id']

        # Inserir registro de rodízio
        query_rodizio = """
        INSERT INTO public.rodizio_registro
        (id, cliente_id, veiculo_id, data_rodizio, km_veiculo,
         status, motivo, usuario_responsavel)
        VALUES (%s, %s, %s, NOW(), %s, 'completo', %s, %s)
        """

        if not run_query(query_rodizio, (rodizio_id, cliente_id, veiculo_id,
                                        km_veiculo, motivo, usuario_id)):
            st.error("Erro ao registrar rodízio")
            return False

        # Executar cada troca
        trocas_realizadas = 0
        for sugestao in sugestoes:
            pneu_de_id = sugestao['trocar_de']['id']
            pneu_para_id = sugestao['trocar_para']['id']
            posicao = sugestao['trocar_de']['posicao']

            # Tirar o pneu da posição
            query_remove = """
            UPDATE public.pneus
            SET posicao_atual = NULL, caminhao_atual_id = NULL, status = 'ESTOQUE'
            WHERE id = %s
            """

            # Colocar o novo pneu na posição
            query_instala = """
            UPDATE public.pneus
            SET posicao_atual = %s, caminhao_atual_id = %s, status = 'MONTADO'
            WHERE id = %s
            """

            # Registrar movimentos
            if (run_query(query_remove, (pneu_de_id,)) and
                run_query(query_instala, (posicao, veiculo_id, pneu_para_id))):

                # Registrar movimento do pneu que sai
                run_query("""
                INSERT INTO public.movimentacoes
                (pneu_id, tipo_movimento, origem_caminhao_id, destino_caminhao_id,
                 posicao_de, posicao_para, usuario_responsavel, data_movimento)
                VALUES (%s, 'RODIZIO', %s, NULL, %s, 'ESTOQUE', %s, NOW())
                """, (pneu_de_id, veiculo_id, posicao, usuario_id))

                # Registrar movimento do pneu que entra
                run_query("""
                INSERT INTO public.movimentacoes
                (pneu_id, tipo_movimento, origem_caminhao_id, destino_caminhao_id,
                 posicao_de, posicao_para, usuario_responsavel, data_movimento)
                VALUES (%s, 'RODIZIO', NULL, %s, 'ESTOQUE', %s, %s, NOW())
                """, (pneu_para_id, veiculo_id, posicao, usuario_id))

                trocas_realizadas += 1

        if trocas_realizadas > 0:
            st.success(f"✅ Rodízio executado! {trocas_realizadas} pneus trocados")
            return True

        return False
    except Exception as e:
        st.error(f"Erro ao executar rodízio: {e}")
        return False

def obter_historico_rodizio_veiculo(veiculo_id, limite=10):
    """Retorna histórico de rodízios de um veículo"""
    query = """
    SELECT id, data_rodizio, km_veiculo, motivo, usuario_responsavel
    FROM public.rodizio_registro
    WHERE veiculo_id = %s
    ORDER BY data_rodizio DESC
    LIMIT %s
    """
    return run_query(query, (veiculo_id, limite))

# ============ FLUXO 6: CPK (Cálculo de Capacidade) ============

def calcular_cpk_pneus(cliente_id, limite_min_km=5000, limite_max_km=70000):
    """Calcula CPK (Capability Process) de todos os pneus do cliente"""
    try:
        query = """
        SELECT km_vida_total
        FROM public.pneus
        WHERE cliente_id = %s AND status IN ('MONTADO', 'ESTOQUE')
        """
        pneus = run_query(query, (cliente_id,))

        if not pneus or len(pneus) < 2:
            return None

        valores = [p['km_vida_total'] for p in pneus]
        n = len(valores)
        media = sum(valores) / n
        variancia = sum((x - media) ** 2 for x in valores) / n
        desvio_padrao = variancia ** 0.5

        # Calcular CPK: min((limite_max - media) / (3 * desvio), (media - limite_min) / (3 * desvio))
        cpk_upper = (limite_max_km - media) / (3 * desvio_padrao) if desvio_padrao > 0 else 0
        cpk_lower = (media - limite_min_km) / (3 * desvio_padrao) if desvio_padrao > 0 else 0
        cpk_valor = min(cpk_upper, cpk_lower)

        # Determinar status
        if cpk_valor >= 1.33:
            status = "EXCELENTE"
        elif cpk_valor >= 1.0:
            status = "BOM"
        elif cpk_valor >= 0.67:
            status = "ACEITÁVEL"
        else:
            status = "CRÍTICO"

        # Recomendação
        if status == "CRÍTICO":
            recomendacao = "Implementar ações corretivas urgentes"
        elif status == "ACEITÁVEL":
            recomendacao = "Monitorar de perto e otimizar processos"
        else:
            recomendacao = "Processo sob controle"

        resultado = {
            'cpk': round(cpk_valor, 3),
            'media': round(media, 1),
            'desvio_padrao': round(desvio_padrao, 1),
            'quantidade_pneus': n,
            'status': status,
            'recomendacao': recomendacao
        }

        # Registrar no histórico
        registrar_cpk_historico(
            resultado['cpk'],
            resultado['media'],
            resultado['desvio_padrao'],
            resultado['quantidade_pneus'],
            resultado['status'],
            resultado['recomendacao']
        )

        return resultado
    except Exception as e:
        st.error(f"Erro ao calcular CPK: {e}")
        return None

def registrar_cpk_historico(cpk_valor, media, desvio, quantidade_pneus, status, recomendacao):
    """Registra cálculo de CPK no histórico"""
    query = """
    INSERT INTO public.cpk_historico 
    (data_calculo, cpk_valor, media, desvio, quantidade_pneus, status, recomendacao)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    params = (datetime.now(), cpk_valor, media, desvio, quantidade_pneus, status, recomendacao)
    return run_query(query, params)

def obter_historico_cpk(cliente_id=None, limite=10):
    """Obtém histórico recente de CPK"""
    if cliente_id:
        query = """
        SELECT ch.* FROM public.cpk_historico ch
        WHERE cliente_id = %s
        ORDER BY ch.data_calculo DESC
        LIMIT %s
        """
        return run_query(query, (cliente_id, limite))
    else:
        query = """
        SELECT * FROM public.cpk_historico
        ORDER BY data_calculo DESC
        LIMIT %s
        """
        return run_query(query, (limite,))

# ============ VEÍCULOS ============

def get_todos_veiculos(cliente_id):
    """Retorna todos os veículos de um cliente"""
    query = """
    SELECT * FROM public.veiculos
    WHERE cliente_id = %s
    ORDER BY placa
    """
    return run_query(query, (cliente_id,))

def get_veiculo_by_id(veiculo_id):
    """Retorna dados de um veículo específico"""
    query = "SELECT * FROM public.veiculos WHERE id = %s"
    result = run_query(query, (veiculo_id,))
    return result[0] if result else None

def atualizar_km_veiculo(veiculo_id, km_novo):
    """Atualiza quilometragem atual do veículo"""
    query = """
    UPDATE public.veiculos
    SET km_atual = %s, data_ultima_atualizacao = NOW()
    WHERE id = %s
    """
    return run_query(query, (km_novo, veiculo_id))

# ============ PNEUS ============

def get_pneu_by_id(pneu_id):
    """Retorna dados completos de um pneu"""
    query = """
    SELECT id, marca_fogo, marca, medida, status, ciclo_atual, km_vida_total,
           caminhao_atual_id, posicao_atual, data_status, custo_aquisicao
    FROM public.pneus
    WHERE id = %s
    """
    result = run_query(query, (pneu_id,))
    return result[0] if result else None

def get_pneus_by_veiculo(veiculo_id, status=None):
    """Retorna todos os pneus de um veículo"""
    if status:
        query = """
        SELECT * FROM public.pneus
        WHERE caminhao_atual_id = %s AND status = %s
        ORDER BY posicao_atual
        """
        return run_query(query, (veiculo_id, status))
    else:
        query = """
        SELECT * FROM public.pneus
        WHERE caminhao_atual_id = %s
        ORDER BY posicao_atual
        """
        return run_query(query, (veiculo_id,))

def get_todos_pneus(cliente_id):
    """Retorna todos os pneus de um cliente"""
    query = """
    SELECT p.* FROM public.pneus p
    JOIN public.veiculos v ON p.caminhao_atual_id = v.id
    WHERE v.cliente_id = %s
    ORDER BY p.marca_fogo
    """
    return run_query(query, (cliente_id,))

def atualizar_posicao_pneu(pneu_id, nova_posicao, veiculo_id=None):
    """Atualiza posição de um pneu"""
    query = """
    UPDATE public.pneus
    SET posicao_atual = %s, caminhao_atual_id = %s, data_status = %s
    WHERE id = %s
    """
    params = (nova_posicao, veiculo_id, datetime.now(), pneu_id)
    return run_query(query, params)

def atualizar_status_pneu(pneu_id, novo_status):
    """Atualiza status de um pneu"""
    query = """
    UPDATE public.pneus
    SET status = %s, data_status = %s
    WHERE id = %s
    """
    params = (novo_status, datetime.now(), pneu_id)
    return run_query(query, params)

# ============ AUDITORIA ============

def registrar_log_auditoria(usuario_id, acao, tabela, registro_id, detalhes=None):
    """Registra ação de auditoria no banco"""
    query = """
    INSERT INTO public.auditoria_log 
    (usuario_id, acao, tabela, registro_id, detalhes, data_hora)
    VALUES (%s, %s, %s, %s, %s, %s)
    """
    params = (usuario_id, acao, tabela, registro_id, detalhes, datetime.now())
    return run_query(query, params)

# ============ VALIDAÇÕES ============

def validar_cadastro_pneu(dados):
    """Valida dados antes de cadastrar um pneu"""
    required_fields = ['pneu_id', 'tamanho', 'veiculo_id']
    for field in required_fields:
        if field not in dados or dados[field] is None:
            raise ValueError(f"Campo obrigatório faltando: {field}")

    tamanhos_validos = ['295/80R22.5', '275/80R22.5', '11.00R22', '12R22.5', 
                       '185/65R15', '195/60R15', '225/70R15', '235/75R17']
    if dados['tamanho'] not in tamanhos_validos:
        raise ValueError(f"Tamanho inválido. Válidos: {tamanhos_validos}")

    existing = run_query("SELECT id FROM public.pneus WHERE marca_fogo = %s", (dados['pneu_id'],))
    if existing:
        raise ValueError(f"Pneu ID {dados['pneu_id']} já existe")

    return True

def validar_movimento(dados):
    """Valida dados de movimento de pneu"""
    required = ['pneu_id', 'acao', 'posicao_nova']
    for field in required:
        if field not in dados:
            raise ValueError(f"Campo faltando: {field}")

    acoes_validas = ['montar', 'desmontar', 'mover_repouso', 'mover_recapagem']
    if dados['acao'] not in acoes_validas:
        raise ValueError(f"Ação inválida: {dados['acao']}")

    posicoes_validas = ['FL', 'FR', 'TL_OUT', 'TL_IN', 'TR_IN', 'TR_OUT', 
                       'RL_OUT', 'RL_IN', 'RR_IN', 'RR_OUT', 'REPOUSO', 'RECAPAGEM']
    if dados['posicao_nova'] not in posicoes_validas:
        raise ValueError(f"Posição inválida: {dados['posicao_nova']}")

    tire = run_query("SELECT id FROM public.pneus WHERE marca_fogo = %s", (dados['pneu_id'],))
    if not tire:
        raise ValueError(f"Pneu não encontrado: {dados['pneu_id']}")

    return True

# ============ VISUALIZAÇÕES COMUNS ============

def obter_status_pneu_visual(pneu):
    """Retorna cor e status baseado em desgaste"""
    km_vida = pneu['km_vida_total']
    ciclo = pneu.get('ciclo_atual', 0)
    limite = 100000 if ciclo == 0 else 70000
    percentual = (km_vida / limite) * 100

    if percentual >= 90:
        return "🔴", "CRÍTICO", "#ffcccc"
    elif percentual >= 70:
        return "🟡", "ATENÇÃO", "#fff4cc"
    else:
        return "🟢", "OK", "#ccffcc"

def obter_dashboard_resumo(cliente_id):
    """Retorna resumo do dashboard para o cliente"""
    try:
        # Total de pneus
        query_total = """
        SELECT COUNT(*) as total FROM public.pneus WHERE cliente_id = %s
        """
        total = run_query(query_total, (cliente_id,))
        total_pneus = total[0]['total'] if total else 0

        # Pneus em uso
        query_uso = """
        SELECT COUNT(*) as em_uso FROM public.pneus 
        WHERE cliente_id = %s AND status = 'MONTADO'
        """
        em_uso = run_query(query_uso, (cliente_id,))
        pneus_em_uso = em_uso[0]['em_uso'] if em_uso else 0

        # Pneus em estoque
        query_estoque = """
        SELECT COUNT(*) as estoque FROM public.pneus 
        WHERE cliente_id = %s AND status = 'ESTOQUE'
        """
        estoque = run_query(query_estoque, (cliente_id,))
        pneus_estoque = estoque[0]['estoque'] if estoque else 0

        # Alertas ativos
        alertas = listar_alertas_ativos(cliente_id)
        num_alertas = len(alertas) if alertas else 0

        return {
            'total_pneus': total_pneus,
            'pneus_em_uso': pneus_em_uso,
            'pneus_estoque': pneus_estoque,
            'alertas_ativos': num_alertas,
            'saude': 'EXCELENTE' if num_alertas == 0 else 'COM_ALERTAS'
        }
    except Exception as e:
        st.error(f"Erro ao obter resumo: {e}")
        return None
