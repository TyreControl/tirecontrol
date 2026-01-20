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
    """Registra ação de auditoria no banco"""
    query = """
    INSERT INTO auditoria_log (usuario_id, acao, tabela, registro_id, detalhes, data_hora)
    VALUES (%s, %s, %s, %s, %s, %s)
    """
    params = (usuario_id, acao, tabela, registro_id, detalhes, datetime.now())
    return run_query(query, params)
