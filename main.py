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

# ==================== SIDEBAR ====================
with st.sidebar:
    st.title("🚚 Tyre Control")
    st.write(f"👤 Gestor: **{st.session_state.get('user_name')}**")
    
    if st.button("🚪 Sair"):
        st.session_state.clear()
        st.rerun()

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
        "Relatórios"
    ],
    icons=[
        "truck",
        "tools",
        "archive",
        "graph-up",
        "exclamation-circle",
        "recycle",
        "file-text"
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
    cliente_id = st.session_state.get('cliente_id')
    if cliente_id:
        analise_cpk.mostrar_cpk_dashboard(cliente_id)
    else:
        st.error("Erro: cliente_id não configurado")

elif selected == "Alertas":
    cliente_id = st.session_state.get('cliente_id')
    if cliente_id:
        sistema_alertas.mostrar_alertas_dashboard(cliente_id)
    else:
        st.error("Erro: cliente_id não configurado")

elif selected == "Recapagem":
    cliente_id = st.session_state.get('cliente_id')
    if cliente_id:
        integracao_recapadora.render_fluxo_recapadora(cliente_id)
    else:
        st.error("Erro: cliente_id não configurado")

elif selected == "Relatórios":
    cliente_id = st.session_state.get('cliente_id')
    if cliente_id:
        relatorios.render_relatorios(cliente_id)
    else:
        st.error("Erro: cliente_id não configurado")
