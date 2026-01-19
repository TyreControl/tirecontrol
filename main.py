import streamlit as st
from streamlit_option_menu import option_menu
import login
import frota
import pneus

# 1. Configuração da Página
st.set_page_config(
    page_title="Tyre Control",
    page_icon="🚚",
    layout="wide"
)

# 2. Carregar CSS
try:
    with open('style.css') as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
except FileNotFoundError:
    st.warning("Arquivo style.css não encontrado.")

# 3. Verificação de Login
if not st.session_state.get('logged_in'):
    login.render_login_page()
    st.stop()

# --- DAQUI PRA BAIXO SÓ APARECE SE ESTIVER LOGADO ---

# 4. Barra Lateral
with st.sidebar:
    st.title("Tyre Control 🚚")
    usuario = st.session_state.get('user_name', 'Usuário')
    perfil = st.session_state.get('user_role', 'Visitante')
    st.write(f"Olá, **{usuario}**!")
    st.caption(f"Perfil: {perfil}")
    st.divider()
    if st.button("Sair / Logout", type="primary"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# 5. Menu Principal
selected = option_menu(
    menu_title=None,
    options=["Dashboard", "Minha Frota", "Gestão de Pneus", "Movimentações"],
    icons=["speedometer2", "truck", "vinyl", "arrow-left-right"],
    default_index=1, # Já começa na frota para agilizar
    orientation="horizontal",
    styles={
        "container": {"padding": "0!important", "background-color": "#fafafa"},
        "icon": {"color": "orange", "font-size": "20px"}, 
        "nav-link": {"font-size": "16px", "text-align": "center", "margin":"0px", "--hover-color": "#eee"},
        "nav-link-selected": {"background-color": "#02ab21"},
    }
)

# 6. Roteamento
if selected == "Dashboard":
    st.title("📊 Visão Geral")
    st.info("Aqui teremos os gráficos gerais da frota.")

elif selected == "Minha Frota":
    frota.render_frota()

elif selected == "Gestão de Pneus":
    pneus.render_pneus()

elif selected == "Movimentações":
    st.title("🔧 Oficina")
    st.write("Em breve: Aqui faremos a montagem dos pneus nos caminhões.")