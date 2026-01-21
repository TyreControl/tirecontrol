import streamlit as st
import psycopg2
import psycopg2.extras
from psycopg2 import pool
from datetime import datetime

# Configuração do Pool de Conexões
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
    """Executa uma query simples e retorna resultado"""
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

# ============ VALIDAÇÕES ============

def validar_cadastro_pneu(dados):
    """Valida dados antes de cadastrar um pneu"""
    required_fields = ['pneu_id', 'tamanho', 'veiculo_id']
    
    for field in required_fields:
        if field not in dados or dados[field] is None:
            raise ValueError(f"Campo obrigatório faltando: {field}")
    
    tamanhos_validos = ['295/80R22.5', '275/80R22.5', '11.00R22', '12R22.5', '185/65R15', '195/60R15', '225/70R15', '235/75R17']
    if dados['tamanho'] not in tamanhos_validos:
        raise ValueError(f"Tamanho inválido. Válidos: {tamanhos_validos}")
    
    existing = run_query("SELECT id FROM pneus WHERE marca_fogo = %s", (dados['pneu_id'],))
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
    
    posicoes_validas = ['FL', 'FR', 'TL_OUT', 'TL_IN', 'TR_IN', 'TR_OUT', 'RL_OUT', 'RL_IN', 'RR_IN', 'RR_OUT', 'REPOUSO', 'RECAPAGEM']
    if dados['posicao_nova'] not in posicoes_validas:
        raise ValueError(f"Posição inválida: {dados['posicao_nova']}")
    
    tire = run_query("SELECT id FROM pneus WHERE marca_fogo = %s", (dados['pneu_id'],))
    if not tire:
        raise ValueError(f"Pneu não encontrado: {dados['pneu_id']}")
    
    return True

# ============ LOGS E AUDITORIA ============

def registrar_log_auditoria(usuario_id, acao, tabela, registro_id, detalhes=None):
    """Registra ação de auditoria no banco (usuario_id deve ser UUID)"""
    query = """
    INSERT INTO auditoria_log (usuario_id, acao, tabela, registro_id, detalhes, data_hora)
    VALUES (%s, %s, %s, %s, %s, %s)
    """
    params = (usuario_id, acao, tabela, registro_id, detalhes, datetime.now())
    return run_query(query, params)

# ============ OPERAÇÕES DE PNEUS ============

def get_pneu_by_id(pneu_id):
    """Retorna dados completos de um pneu"""
    query = """
    SELECT id, marca_fogo, marca, medida, status, ciclo_atual, km_vida_total, 
           months_alive, caminhao_atual_id, posicao_atual, ciclos_sem_rodizio, 
           data_status, custo_aquisicao
    FROM pneus 
    WHERE id = %s
    """
    result = run_query(query, (pneu_id,))
    return result[0] if result else None

def get_pneus_by_veiculo(veiculo_id, status=None):
    """Retorna todos os pneus de um veículo"""
    if status:
        query = """
        SELECT * FROM pneus 
        WHERE caminhao_atual_id = %s AND status = %s
        ORDER BY posicao_atual
        """
        return run_query(query, (veiculo_id, status))
    else:
        query = """
        SELECT * FROM pneus 
        WHERE caminhao_atual_id = %s
        ORDER BY posicao_atual
        """
        return run_query(query, (veiculo_id,))

def atualizar_posicao_pneu(pneu_id, nova_posicao, veiculo_id=None):
    """Atualiza posição de um pneu"""
    query = """
    UPDATE pneus 
    SET posicao_atual = %s, caminhao_atual_id = %s, data_status = %s
    WHERE id = %s
    """
    params = (nova_posicao, veiculo_id, datetime.now(), pneu_id)
    return run_query(query, params)

def atualizar_status_pneu(pneu_id, novo_status):
    """Atualiza status de um pneu"""
    query = """
    UPDATE pneus 
    SET status = %s, data_status = %s
    WHERE id = %s
    """
    params = (novo_status, datetime.now(), pneu_id)
    return run_query(query, params)

# ============ OPERAÇÕES DE ALERTAS ============

def criar_alerta(alert_id, tipo, severidade, pneu_id, mensagem, acao, criado_por):
    """Cria um novo alerta"""
    query = """
    INSERT INTO alertas_log (alert_id, tipo, severidade, pneu_id, mensagem, acao, data_criacao, criado_por, resolvido)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, FALSE)
    """
    params = (alert_id, tipo, severidade, pneu_id, mensagem, acao, datetime.now(), criado_por)
    return run_query(query, params)

def resolver_alerta(alert_id):
    """Marca um alerta como resolvido"""
    query = """
    UPDATE alertas_log 
    SET resolvido = TRUE, data_resolucao = %s
    WHERE alert_id = %s
    """
    params = (datetime.now(), alert_id)
    return run_query(query, params)

def listar_alertas_ativos():
    """Lista todos os alertas não resolvidos"""
    query = """
    SELECT * FROM alertas_log 
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

# ============ OPERAÇÕES DE ORDENS ============

def criar_ordem_recapagem(ordem_id, recapadora_nome, usuario_id):
    """Cria uma nova ordem de recapagem"""
    query = """
    INSERT INTO ordens_recapagem (ordem_id, recapadora_nome, status, data_criacao, usuario_responsavel)
    VALUES (%s, %s, 'enviado', %s, %s)
    """
    params = (ordem_id, recapadora_nome, datetime.now(), usuario_id)
    return run_query(query, params)

def adicionar_pneu_ordem(ordem_id, pneu_id):
    """Adiciona um pneu a uma ordem de recapagem"""
    query = """
    INSERT INTO ordens_recapagem_pneus (ordem_id, pneu_id, data_adicionada)
    VALUES (%s, %s, %s)
    """
    params = (ordem_id, pneu_id, datetime.now())
    return run_query(query, params)

def atualizar_status_ordem(ordem_id, novo_status):
    """Atualiza status de uma ordem"""
    query = """
    UPDATE ordens_recapagem 
    SET status = %s, data_ultima_atualizacao = %s
    WHERE ordem_id = %s
    """
    params = (novo_status, datetime.now(), ordem_id)
    return run_query(query, params)

def obter_ordem(ordem_id):
    """Obtém dados de uma ordem"""
    query = """
    SELECT * FROM ordens_recapagem 
    WHERE ordem_id = %s
    """
    result = run_query(query, (ordem_id,))
    return result[0] if result else None

# ============ OPERAÇÕES CPK ============

def registrar_cpk_historico(cpk_valor, media, desvio, quantidade_pneus, status, recomendacao):
    """Registra cálculo de CPK no histórico"""
    query = """
    INSERT INTO cpk_historico (data_calculo, cpk_valor, media, desvio, quantidade_pneus, status, recomendacao)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    params = (datetime.now(), cpk_valor, media, desvio, quantidade_pneus, status, recomendacao)
    return run_query(query, params)

def obter_historico_cpk(limite=10):
    """Obtém histórico recente de CPK"""
    query = """
    SELECT * FROM cpk_historico 
    ORDER BY data_calculo DESC 
    LIMIT %s
    """
    return run_query(query, (limite,))

# ============ VIEWS ============

def obter_alertas_ativos_view():
    """Consulta view de alertas ativos (ordenados por prioridade)"""
    query = "SELECT * FROM alertas_ativos"
    return run_query(query)

def obter_pneus_em_risco_view():
    """Consulta view de pneus em risco"""
    query = "SELECT * FROM pneus_em_risco"
    return run_query(query)

def get_todos_clientes():
    """Retorna lista de todos os clientes para o Admin selecionar"""
    return run_query("SELECT id, nome_empresa, nome_fantasia FROM clientes ORDER BY nome_empresa")

def get_detalhes_cliente(cliente_id):
    """Busca dados completos de um cliente específico"""
    query = """
        SELECT id, nome_empresa, nome_fantasia, nome_responsavel, 
               contato_responsavel, data_cadastro
        FROM clientes 
        WHERE id = %s
    """
    res = run_query(query, (cliente_id,))
    return res[0] if res else None

def atualizar_dados_cliente(cliente_id, dados):
    """Atualiza cadastro da empresa"""
    try:
        query = """
            UPDATE clientes 
            SET nome_empresa=%s, nome_fantasia=%s, nome_responsavel=%s, contato_responsavel=%s
            WHERE id = %s
        """
        params = (
            dados['nome_empresa'], 
            dados['nome_fantasia'], 
            dados['nome_responsavel'], 
            dados['contato_responsavel'], 
            cliente_id
        )
        return run_query(query, params)
    except Exception as e:
        st.error(f"Erro ao atualizar cliente: {e}")
        return False