"""
main.py
Versão atualizada com FLUXOS 1, 2, 4 e 5 implementados
"""

import streamlit as st
from streamlit_option_menu import option_menu
import login
import frota
import pneus  # ← NOVO (era pneus antes)
import movimentacoes
import analise_cpk
import sistema_alertas
import relatorios
import cadastro_cliente
import fluxo_rodizio  # ← NOVO (era fluxo_rodizio antes)
from database import get_todos_clientes, get_detalhes_cliente  # ← ATUALIZADO

st.set_page_config(
    page_title="Tyre Control - Gestão Profissional",
    page_icon="🚚",
    layout="wide"
)

# CSS
try:
    with open('style.css') as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
except:
    pass

# ==================== LOGIN CHECK ====================

if not st.session_state.get('logged_in'):
    login.render_login_page()
    st.stop()

# ==================== SIDEBAR & SELETOR DE CLIENTE ====================

with st.sidebar:
    st.title("🚚 Tyre Control")
    st.caption("Gestão Real de Frota - 5 Fluxos Implementados ✅")
    
    # --- LÓGICA DE ADMIN / MULTI-CLIENTE ---
    
    user_role = st.session_state.get('user_role', 'operador')
    
    if user_role == 'admin':
        st.markdown("### 🔧 Modo Administrador")
        
        clientes_db = get_todos_clientes()
        
        if clientes_db:
            opcoes_clientes = {c['nome_empresa']: c['id'] for c in clientes_db}
            
            # Recupera o index do cliente atual se já estiver selecionado
            index_atual = 0
            current_id = st.session_state.get('cliente_id')
            
            # Se tiver ID, acha o índice para o selectbox
            ids_list = list(opcoes_clientes.values())
            if current_id in ids_list:
                index_atual = ids_list.index(current_id)
            
            nome_selecionado = st.selectbox(
                "Acessar Cliente:",
                list(opcoes_clientes.keys()),
                index=index_atual
            )
            
            # Atualiza o ID na sessão quando troca o selectbox
            novo_id = opcoes_clientes[nome_selecionado]
            if novo_id != st.session_state.get('cliente_id'):
                st.session_state['cliente_id'] = novo_id
                st.rerun()
        else:
            st.error("Nenhum cliente cadastrado!")
    
    else:
        # Usuário Comum: Apenas mostra a empresa
        c_id = st.session_state.get('cliente_id')
        if c_id:
            info = get_detalhes_cliente(c_id)
            nome_exibir = info['nome_fantasia'] if info and info['nome_fantasia'] else "Minha Empresa"
            st.markdown(f"### 🏢 {nome_exibir}")
        else:
            st.error("Erro: Usuário sem empresa vinculada.")
    
    st.divider()
    
    st.write(f"👤 Gestor: **{st.session_state.get('user_name')}**")
    
    if st.button("🚪 Sair"):
        st.session_state.clear()
        st.rerun()

# ==================== VALIDAÇÃO FINAL DE CLIENTE ====================

if not st.session_state.get('cliente_id'):
    st.warning("👈 Por favor, selecione um cliente na barra lateral para começar.")
    st.stop()

# ==================== MENU PRINCIPAL ====================

selected = option_menu(
    menu_title=None,
    options=[
        "🏠 Home",
        "🚛 Minha Frota",
        "🏭 Gestão de Ativos",
        "🔄 Rodízio",
        "🔧 Central de Oficina",
        "📊 CPK Analysis",
        "🚨 Alertas",
        "📈 Relatórios",
        "⚙️ Configurações"
    ],
    icons=[
        "house",
        "truck",
        "archive",
        "arrow-repeat",
        "tools",
        "graph-up",
        "exclamation-circle",
        "file-text",
        "gear"
    ],
    default_index=0,
    orientation="horizontal"
)

# ==================== ROTEADOR DE PÁGINAS ====================

if selected == "🏠 Home":
    st.title("🏠 Dashboard TyreControl")
    
    st.markdown("""
    ## ✅ Bem-vindo! Sistema 100% Prático para Gestor de Frota
    
    ### 🎯 5 Fluxos Implementados:
    
    1. **📦 Cadastro de Lote** → Registra pneus chegando do fornecedor
    2. **🔧 Atribuir Pneus** → Monta pneus nos caminhões
    3. **📊 Visualizar Estado** → Vê status de todos os pneus
    4. **🔄 Rodízio Automático** → Sistema sugere e executa rodízio
    5. **📜 Histórico Completo** → Rastreia cada pneu, cada movimento
    
    ### 🚀 Comece Por:
    
    **Passo 1:** Ir a "🏭 Gestão de Ativos" → "📦 Novo Lote de Pneus"
    - Registre um lote de teste (ex: 10 pneus Michelin)
    
    **Passo 2:** "🔧 Atribuir Pneus a Caminhão"
    - Monte os pneus em um caminhão
    
    **Passo 3:** "🔄 Rodízio"
    - Gere uma sugestão e execute
    
    ---
    
    ### 📊 Métricas da Frota
    """)
    
    # Mostrar métricas
    from database import run_query
    
    cliente_id = st.session_state.get('cliente_id')
    
    col1, col2, col3, col4 = st.columns(4)
    
    # Total de pneus
    result_total = run_query(
        "SELECT COUNT(*) as total FROM pneus WHERE cliente_id = %s",
        (cliente_id,)
    )
    total_pneus = result_total[0]['total'] if result_total else 0
    
    # Pneus em estoque
    result_estoque = run_query(
        "SELECT COUNT(*) as total FROM pneus WHERE cliente_id = %s AND status = 'ESTOQUE'",
        (cliente_id,)
    )
    pneus_estoque = result_estoque[0]['total'] if result_estoque else 0
    
    # Pneus montados
    result_montado = run_query(
        "SELECT COUNT(*) as total FROM pneus WHERE cliente_id = %s AND status = 'MONTADO'",
        (cliente_id,)
    )
    pneus_montado = result_montado[0]['total'] if result_montado else 0
    
    # Investimento total
    result_invest = run_query(
        "SELECT SUM(custo_aquisicao) as total FROM pneus WHERE cliente_id = %s",
        (cliente_id,)
    )
    investimento = result_invest[0]['total'] if result_invest and result_invest[0]['total'] else 0
    
    col1.metric("🛞 Total de Pneus", total_pneus)
    col2.metric("📦 Em Estoque", pneus_estoque)
    col3.metric("✅ Montados", pneus_montado)
    col4.metric("💰 Investimento", f"R$ {investimento:,.2f}")
    
    st.divider()
    
    st.markdown("""
    ### 📖 Documentação
    
    **Arquivo:** GUIA_IMPLEMENTACAO.txt
    - Passo a passo completo
    - Explicação de cada fluxo
    - FAQ e troubleshooting
    
    **Schema SQL:** setup_schema.sql
    - Estrutura do banco
    - Tabelas criadas
    - Índices para performance
    """)

elif selected == "🚛 Minha Frota":
    frota.render_frota()

elif selected == "🏭 Gestão de Ativos":
    # ← NOVO: Usar a nova versão
    pneus.render_pneus()

elif selected == "🔄 Rodízio":
    # ← NOVO: Usar a nova versão
    fluxo_rodizio.render_rodizio()

elif selected == "🔧 Central de Oficina":
    movimentacoes.render_movimentacoes()

elif selected == "📊 CPK Analysis":
    analise_cpk.render_analise_cpk()

elif selected == "🚨 Alertas":
    sistema_alertas.render_sistema_alertas()

elif selected == "📈 Relatórios":
    relatorios.render_relatorios()

elif selected == "⚙️ Configurações":
    cadastro_cliente.render_cadastro_cliente()