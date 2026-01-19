import streamlit as st
from streamlit_option_menu import option_menu
import login
import frota
import pneus
import movimentacoes # <--- NOVO IMPORT

st.set_page_config(page_title="Tyre Control", page_icon="🚚", layout="wide")

# Carrega CSS
try:
    with open('style.css') as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
except FileNotFoundError: pass

# Login Check
if not st.session_state.get('logged_in'):
    login.render_login_page()
    st.stop()

# Sidebar
with st.sidebar:
    st.title("Tyre Control 🚚")
    st.write(f"Olá, **{st.session_state.get('user_name')}**!")
    st.divider()
    if st.button("Sair", type="primary"):
        st.session_state.clear()
        st.rerun()

# Menu Superior
selected = option_menu(
    menu_title=None,
    options=["Dashboard", "Minha Frota", "Gestão de Pneus", "Movimentações"],
    icons=["speedometer2", "truck", "vinyl", "tools"],
    default_index=1,
    orientation="horizontal",
    styles={"nav-link-selected": {"background-color": "#02ab21"}}
)

# Roteamento
if selected == "Dashboard":
    st.title("📊 Dashboard Executivo (Em Breve)")
    st.info("Implementaremos os KPIs de CPK e Alertas na próxima etapa.")

elif selected == "Minha Frota":
    frota.render_frota()

elif selected == "Gestão de Pneus":
    pneus.render_pneus()

elif selected == "Movimentações":
    movimentacoes.render_movimentacoes()