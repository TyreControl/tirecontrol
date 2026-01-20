"""
NOVA VERSÃO - database.py
Adicionadas funções para os 5 fluxos críticos
"""

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

# ============ FLUXO 1: CADASTRO DE LOTE DE PNEUS ============

def criar_lote_pneus(cliente_id, marca, medida, modelo, fornecedor, 
                     quantidade, preco_unitario, n_nota_fiscal, data_chegada):
    """
    Cria um novo lote de pneus e retorna o ID do lote
    Usado quando pneus chegam do fornecedor (sem números individuais ainda)
    """
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
    """
    Adiciona pneus individuais a um lote existente
    """
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
    """
    Atribui um pneu a uma posição específica de um caminhão
    Fluxo: Gestor clica em posição do chassi → seleciona pneu estoque → confirma
    """
    try:
        # Obter posição anterior (se existe)
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
    """
    Remove um pneu de um caminhão (volta para estoque)
    """
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
    
    # Converter para dicionário {posicao: pneu_dados}
    mapa = {}
    if result:
        for pneu in result:
            posicao = pneu['posicao_atual']
            mapa[posicao] = pneu
    
    return mapa

def obter_pneus_estoque_disponiveis(cliente_id, filtro_medida=None):
    """
    Retorna pneus disponíveis no estoque para distribuir
    Ordenados por vida útil restante (piores primeiro)
    """
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

# ============ FLUXO 5: RODÍZIO DE PNEUS ============

def sugerir_rodizio_automatico(veiculo_id):
    """
    Sugere AUTOMATICAMENTE qual rodízio fazer baseado em desgaste
    Retorna lista de sugestões de troca
    """
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
        # Query: obter pneus em boas condições
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
    """
    Executa o rodízio aprovado
    Registra TODOS os movimentos dos pneus
    """
    try:
        # Criar registro de rodízio
        rodizio_id = str(uuid.uuid4())
        
        # Obter cliente_id
        query_veiculo = "SELECT cliente_id FROM public.caminhoes WHERE id = %s"
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
