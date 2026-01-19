import streamlit as st
import psycopg2
import psycopg2.extras  # <--- ADICIONE ESTA LINHA AQUI
from psycopg2 import pool

# Configuração do Pool de Conexões
# Isso permite que o sistema aguente vários usuários sem travar o banco
@st.cache_resource
def init_connection_pool():
    try:
        return psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=st.secrets["SUPABASE_URL"], # Usaremos a URL completa do Supabase
            cursor_factory=psycopg2.extras.RealDictCursor # Retorna dados como Dicionário (chave: valor)
        )
    except Exception as e:
        st.error(f"Erro crítico ao conectar no banco: {e}")
        return None

# Função para pegar uma conexão do pool
def get_connection():
    pool = init_connection_pool()
    if pool:
        return pool.getconn()
    return None

# Função para devolver a conexão ao pool (MUITO IMPORTANTE)
def release_connection(conn):
    pool = init_connection_pool()
    if pool and conn:
        pool.putconn(conn)

# Função utilitária para rodar uma query simples e já fechar a conexão
# Ideal para SELECTs rápidos
def run_query(query, params=None):
    conn = get_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            # Se for SELECT, retorna os dados
            if query.strip().upper().startswith("SELECT"):
                return cur.fetchall()
            # Se for INSERT/UPDATE/DELETE, commita e retorna True
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