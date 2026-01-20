import streamlit as st
from streamlit_option_menu import option_menu
import login
import frota
import pneus
import movimentacoes
import analise_cpk
import sistema_alertas
import integracao_recapadora
import relatorios
import cadastro_cliente
from database import get_todos_clientes, get_detalhes_cliente

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
                st.rerun() # Recarrega a página para atualizar os dados
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
        "Minha Frota",
        "Central de Oficina",
        "Gestão de Ativos",
        "CPK Analysis",
        "Alertas",
        "Recapagem",
        "Relatórios",
        "Configurações"
    ],
    icons=[
        "truck",
        "tools",
        "archive",
        "graph-up",
        "exclamation-circle",
        "recycle",
        "file-text",
        "gear"
    ],
    default_index=0,
    orientation="horizontal"
)

# ==================== ROTEADOR DE PÁGINAS ====================
if selected == "Minha Frota":
    frota.render_frota()

elif selected == "Central de Oficina":
    movimentacoes.render_movimentacoes()

elif selected == "Gestão de Ativos":
    pneus.render_pneus()

elif selected == "CPK Analysis":
    analise_cpk.render_analise_cpk()

elif selected == "Alertas":
    sistema_alertas.render_sistema_alertas()

elif selected == "Recapagem":
    integracao_recapadora.render_integracao_recapadora()

elif selected == "Relatórios":
    relatorios.render_relatorios()

elif selected == "Configurações":
    cadastro_cliente.render_cadastro_cliente()